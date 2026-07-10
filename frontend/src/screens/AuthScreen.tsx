import React, { useState } from "react";
import { useAuth } from "../components/AuthContext";

export const AuthScreen: React.FC = () => {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState<boolean>(true);
  const [email, setEmail] = useState<string>("");
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isLogin) {
        // Log in using username or email
        await login(username, password);
      } else {
        // Register using email, username, password
        if (!email.includes("@")) {
          throw new Error("Please enter a valid email address.");
        }
        await register(email, username, password);
      }
    } catch (err: any) {
      console.error(err);
      // Handle both FastAPI shape {"detail": "..."} and slowapi shape {"error": "..."}
      // plus generic network/unknown errors so nothing is ever silently swallowed.
      const data = err.response?.data;
      const message =
        (typeof data?.detail === "string" ? data.detail : null) ||
        (typeof data?.error === "string" ? data.error : null) ||
        (typeof data === "string" ? data : null) ||
        err.message ||
        "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-glow-bg">
        <div className="auth-glow-circle circle-1"></div>
        <div className="auth-glow-circle circle-2"></div>
      </div>
      
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">
            <span className="logo-icon">✦</span>
            <h1>BriefAI</h1>
          </div>
          <p className="auth-subtitle">
            {isLogin 
              ? "Real-time meeting intelligence platform" 
              : "Create your secure account to start transcribing"
            }
          </p>
        </div>

        {error && <div className="auth-error-box">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          {!isLogin && (
            <div className="input-group">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                placeholder="alice@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
          )}

          <div className="input-group">
            <label htmlFor="username">
              {isLogin ? "Username or Email" : "Username"}
            </label>
            <input
              id="username"
              type="text"
              placeholder={isLogin ? "alice or alice@example.com" : "alice"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          </div>

          <div className="input-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? "Processing..." : isLogin ? "Sign In" : "Sign Up"}
          </button>
        </form>

        <div className="auth-footer">
          <span>
            {isLogin ? "New to BriefAI?" : "Already have an account?"}
          </span>
          <button
            type="button"
            className="auth-switch-btn"
            onClick={() => {
              setIsLogin(!isLogin);
              setError(null);
            }}
          >
            {isLogin ? "Create Account" : "Sign In"}
          </button>
        </div>
      </div>
    </div>
  );
};
