import React, { useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  Lock,
  LogIn,
  Mail,
  User,
  UserPlus,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

const Login = ({ onSuccess }) => {
  const [mode, setMode] = useState("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login, signup } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccessMessage("");
    setIsLoading(true);

    try {
      if (mode === "login") {
        await login(email, password);
        if (onSuccess) onSuccess();
      } else {
        await signup(email, password, fullName, null);
        setSuccessMessage(
          "Account created. Please confirm your email before logging in.",
        );
        setFullName("");
        setEmail("");
        setPassword("");
        setTimeout(() => {
          setMode("login");
          setSuccessMessage("");
        }, 5000);
      }
    } catch (err) {
      setError(err.message || "Something went wrong, please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] text-[var(--accent)]">
          {mode === "login" ? <LogIn className="h-6 w-6" /> : <UserPlus className="h-6 w-6" />}
        </div>
        <h2 className="type-h3">{mode === "login" ? "Welcome back" : "Create account"}</h2>
        <p className="mt-2 type-small text-[var(--text-secondary)]">
          {mode === "login"
            ? "Sign in to keep your conversation history."
            : "Create an account to save and revisit your chats."}
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-[12px] border border-[#d9b4b4] bg-[#f8ecec] p-3 text-sm text-[var(--danger)]">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {successMessage && (
        <div className="mb-4 flex items-start gap-2 rounded-[12px] border border-[#bdd6c5] bg-[#edf7f1] p-3 text-sm text-[var(--success)]">
          <CheckCircle className="mt-0.5 h-4 w-4" />
          <span>{successMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "signup" && (
          <label className="block space-y-1.5">
            <span className="type-small flex items-center gap-1.5 text-[var(--text-secondary)]">
              <User className="h-4 w-4" />
              Full Name (optional)
            </span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Jane Doe"
              className="w-full rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 py-2.5 text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
            />
          </label>
        )}

        <label className="block space-y-1.5">
          <span className="type-small flex items-center gap-1.5 text-[var(--text-secondary)]">
            <Mail className="h-4 w-4" />
            Email
          </span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 py-2.5 text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
          />
        </label>

        <label className="block space-y-1.5">
          <span className="type-small flex items-center gap-1.5 text-[var(--text-secondary)]">
            <Lock className="h-4 w-4" />
            Password
          </span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 py-2.5 text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
          />
        </label>

        <button type="submit" disabled={isLoading} className="btn-primary w-full px-5">
          {isLoading
            ? "Processing..."
            : mode === "login"
              ? "Sign In"
              : "Create Account"}
        </button>
      </form>

      <div className="mt-6 border-t border-[var(--border-soft)] pt-4 text-center type-small text-[var(--text-secondary)]">
        {mode === "login" ? (
          <>
            Need an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError("");
                setSuccessMessage("");
              }}
              className="font-semibold text-[var(--accent)] underline"
            >
              Sign up
            </button>
          </>
        ) : (
          <>
            Already registered?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError("");
                setSuccessMessage("");
              }}
              className="font-semibold text-[var(--accent)] underline"
            >
              Log in
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default Login;
