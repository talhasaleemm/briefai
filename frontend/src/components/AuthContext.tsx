import React, { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { api, setAccessToken } from "../api/client";

interface User {
  id: number;
  email: string;
  username: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Attempt session recovery on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const res = await api.post("/auth/refresh");
        const { access_token } = res.data;
        setAccessToken(access_token);
        
        // Fetch current user details or profile if token is valid
        // But wait! We can decode token or fetch Alice details.
        // Let's create an endpoint or query Alice profile?
        // Actually, we can get user info or we can just fetch it from a test endpoint
        // Let's add a GET /auth/me endpoint in our backend auth router to get user details!
        // Yes! That's extremely standard and clean. Let's make sure we implement GET /auth/me.
        const userRes = await api.get("/auth/me");
        setUser(userRes.data);
      } catch (err) {
        // Safe to ignore on initial load (not logged in)
        setAccessToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkSession();
  }, []);

  // Listen to session expiry events from Axios interceptor
  useEffect(() => {
    const handleSessionExpired = () => {
      setUser(null);
      setAccessToken(null);
    };

    window.addEventListener("auth:session-expired", handleSessionExpired);
    return () => {
      window.removeEventListener("auth:session-expired", handleSessionExpired);
    };
  }, []);

  const login = async (usernameOrEmail: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.post("/auth/login", {
        username_or_email: usernameOrEmail,
        password,
      });
      const { access_token } = res.data;
      setAccessToken(access_token);

      const userRes = await api.get("/auth/me");
      setUser(userRes.data);
    } catch (err) {
      setUser(null);
      setAccessToken(null);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, username: string, password: string) => {
    setIsLoading(true);
    try {
      // 1. Create account
      await api.post("/auth/register", { email, username, password });
      
      // 2. Perform auto-login immediately for premium UX
      await login(username, password);
    } catch (err) {
      setIsLoading(false);
      throw err;
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      setUser(null);
      setAccessToken(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
