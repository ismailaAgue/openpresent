"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api-client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      // ADR-060 — was "/dashboard". Landing straight on a project list
      // read as a jarring old-page detour rather than a continuation
      // of signing in; "/" drops the person back into the actual
      // studio (now signed in) instead, matching how sign-out from
      // Settings already returns to "/" (ADR-057).
      router.push("/");
    } catch (e: any) {
      setError(e.message || "Could not log in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container" style={{ paddingTop: 64, maxWidth: 440 }}>
      <h1 style={{ fontSize: "2rem" }}>Log in</h1>
      <form onSubmit={handleSubmit} className="card" style={{ marginTop: 30, display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label className="field-label" htmlFor="email">Email</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="password">Password</label>
          <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p style={{ marginTop: 18, fontSize: 14 }}>
        No account yet? <a href="/register" style={{ color: "var(--accent-teal)", fontWeight: 600 }}>Sign up free</a>
      </p>
    </div>
  );
}
