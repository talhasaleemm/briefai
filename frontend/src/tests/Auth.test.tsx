import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { AuthScreen } from "../screens/AuthScreen";
import { useAuth } from "../components/AuthContext";
import App from "../App";

// Mock the AuthContext hook behavior
vi.mock("../components/AuthContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../components/AuthContext")>();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// Mock api client to prevent real networking
vi.mock("../api/client", () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
  setAccessToken: vi.fn(),
  getAccessToken: vi.fn(() => "mock-token"),
}));

describe("Frontend Auth Integration & Workspace Guard Tests", () => {
  let mockLogin: any;
  let mockRegister: any;
  let mockLogout: any;

  beforeEach(() => {
    mockLogin = vi.fn().mockResolvedValue(undefined);
    mockRegister = vi.fn().mockResolvedValue(undefined);
    mockLogout = vi.fn().mockResolvedValue(undefined);

    (useAuth as any).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: mockLogin,
      register: mockRegister,
      logout: mockLogout,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the glassmorphic login screen when unauthenticated", () => {
    render(<AuthScreen />);

    // Verify Sign In title and input fields are present
    expect(screen.getByRole("heading", { name: /BriefAI/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Username or Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Email address/i)).not.toBeInTheDocument(); // Only shown during register
  });

  it("switches to registration form when clicking 'Create Account'", async () => {
    render(<AuthScreen />);

    const switchBtn = screen.getByRole("button", { name: /Create Account/i });
    
    await act(async () => {
      fireEvent.click(switchBtn);
    });

    // Check that email field appears and subtitle/button text updates
    expect(screen.getByLabelText(/Email address/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign Up/i })).toBeInTheDocument();
  });

  it("submits the form and calls the login callback", async () => {
    render(<AuthScreen />);

    const usernameInput = screen.getByLabelText(/Username or Email/i);
    const passwordInput = screen.getByLabelText(/Password/i);
    const submitBtn = screen.getByRole("button", { name: /Sign In/i });

    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "mysecurepassword" } });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    expect(mockLogin).toHaveBeenCalledWith("testuser", "mysecurepassword");
  });

  it("Workspace Guard: redirects unauthenticated users to the login screen", () => {
    // Render the main App. When useAuth returns isAuthenticated: false, App must render AuthScreen
    render(<App />);

    // Confirm that the workspace controls are hidden, and the Login screen is shown instead
    expect(screen.getByRole("heading", { name: /BriefAI/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Username or Email/i)).toBeInTheDocument();
    expect(screen.queryByText(/⚡ Process Transcript/i)).not.toBeInTheDocument();
  });
});
