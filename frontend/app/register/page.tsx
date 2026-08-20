"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register, login } from "@/lib/api-client";

export default function RegisterPage() {
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
      await register(email, password);
      await login(email, password);
      router.push("/dashboard");
    } catch (e: any) {
      setError(e.message || "Could not create your account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container" style={{ paddingTop: 64, maxWidth: 440 }}>
      <p className="eyebrow" style={{ marginBottom: 10 }}>Free, always</p>
      <h1 style={{ fontSize: "2rem" }}>Create your account</h1>
      <p style={{ marginTop: 10, marginBottom: 30 }}>
        Only needed to save and reuse projects later. Generating a presentation never requires this.
      </p>
      <form onSubmit={handleSubmit} className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label className="field-label" htmlFor="email">School email or any email</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="password">Password</label>
          <input id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Creating…" : "Sign up free"}
        </button>
      </form>
      <p style={{ marginTop: 18, fontSize: 14 }}>
        Already have an account? <a href="/login" style={{ color: "var(--accent-teal)", fontWeight: 600 }}>Log in</a>
      </p>
    </div>
  );
}
