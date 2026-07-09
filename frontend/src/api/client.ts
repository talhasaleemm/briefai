import axios from "axios";

let accessToken: string | null = null;

/**
 * Update the in-memory access token used for request authorization.
 */
export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

/**
 * Retrieve the current in-memory access token.
 */
export const getAccessToken = () => accessToken;

/**
 * Pre-configured Axios instance for API queries.
 */
export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true, // Crucial: automatically attach HTTP-only cookies
});

// Request interceptor: Inject JWT authorization header if present
api.interceptors.request.use(
  (config) => {
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Flag and queue to manage concurrent token refreshing
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (token) {
      prom.resolve(token);
    } else {
      prom.reject(error);
    }
  });
  failedQueue = [];
};

// Response interceptor: intercept 401s and transparently refresh token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Check if error is unauthorized (401) and request has not been retried yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry auth lifecycle endpoints to prevent infinite loops
      if (
        originalRequest.url?.includes("/auth/refresh") ||
        originalRequest.url?.includes("/auth/login") ||
        originalRequest.url?.includes("/auth/register")
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Enqueue request while another refresh call is active
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Exchange HTTP-only refresh cookie for a new access token
        const res = await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
        const { access_token } = res.data;
        
        setAccessToken(access_token);
        processQueue(null, access_token);
        
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        setAccessToken(null);
        // Notify the app context that the session has expired
        window.dispatchEvent(new Event("auth:session-expired"));
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
