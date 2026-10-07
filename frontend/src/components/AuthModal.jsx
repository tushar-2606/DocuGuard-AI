import { useState } from "react";
import { api, setStoredToken } from "../services/api";

export default function AuthModal({ isOpen, onClose, onAuthSuccess, initialMode = "login" }) {
  const [mode, setMode] = useState(initialMode);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Please fill in all required fields.");
      return;
    }

    if (mode === "signup") {
      if (!fullName.trim()) {
        setError("Please enter your full name.");
        return;
      }
      if (password.length < 6) {
        setError("Password must be at least 6 characters long.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setLoading(true);
    try {
      let res;
      if (mode === "signup") {
        res = await api.register(fullName.trim(), email.trim(), password, confirmPassword);
      } else {
        res = await api.login(email.trim(), password);
      }

      setStoredToken(res.access_token);
      onAuthSuccess(res.user);
      onClose();
    } catch (err) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode) => {
    setMode(newMode);
    setError("");
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-copy">
            <span className="section-kicker">DOCUGUARD WORKSPACE</span>
            <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
            <p>
              {mode === "login"
                ? "Sign in to access your saved documents, tasks, and deadlines."
                : "Join DocuGuard AI for automated document intelligence and compliance."}
            </p>
          </div>
          <button className="modal-close" onClick={onClose} type="button" aria-label="Close modal">
            ✕
          </button>
        </div>

        <div className="auth-tab-row">
          <button
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => switchMode("login")}
            type="button"
          >
            Sign In
          </button>
          <button
            className={`auth-tab ${mode === "signup" ? "active" : ""}`}
            onClick={() => switchMode("signup")}
            type="button"
          >
            Create Account
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {error && (
            <div className="auth-error-banner" role="alert">
              <span>⚠</span>
              <p>{error}</p>
            </div>
          )}

          {mode === "signup" && (
            <div className="form-group">
              <label htmlFor="auth-name">Full Name</label>
              <input
                id="auth-name"
                type="text"
                placeholder="e.g. Tushar Patel"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                autoFocus
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="auth-email">Work or Institutional Email</label>
            <input
              id="auth-email"
              type="email"
              placeholder="name@organization.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus={mode === "login"}
            />
          </div>

          <div className="form-group">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {mode === "signup" && (
            <div className="form-group">
              <label htmlFor="auth-confirm">Confirm Password</label>
              <input
                id="auth-confirm"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
          )}

          <button className="auth-submit-button" type="submit" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" />
                <span>{mode === "login" ? "Signing in…" : "Creating account…"}</span>
              </>
            ) : (
              <span>{mode === "login" ? "Sign In to Workspace" : "Get Started Free"}</span>
            )}
          </button>

          <div className="auth-switch-footer">
            {mode === "login" ? (
              <p>
                Don't have an account yet?{" "}
                <button type="button" onClick={() => switchMode("signup")}>
                  Create one now
                </button>
              </p>
            ) : (
              <p>
                Already have an account?{" "}
                <button type="button" onClick={() => switchMode("login")}>
                  Sign in instead
                </button>
              </p>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
