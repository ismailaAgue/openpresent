"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listProjects, ProjectSummary } from "@/lib/api-client";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => {
        if (e.message === "UNAUTHENTICATED") {
          window.location.href = "/login";
        } else {
          setError(e.message);
        }
      });
  }, []);

  return (
    <div className="container" style={{ paddingTop: 56, paddingBottom: 96 }}>
      <p className="eyebrow" style={{ marginBottom: 10 }}>Your work</p>
      <h1 style={{ fontSize: "2rem" }}>Saved projects</h1>
      <p style={{ marginTop: 10 }}>
        Every project here can be turned into a different version later — a summary,
        a different theme, anything. Nothing here ever expires or gets deleted for being unused.
      </p>

      {error && <p className="error-text" style={{ marginTop: 20 }}>{error}</p>}

      {projects && projects.length === 0 && (
        <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
          <p style={{ margin: 0 }}>
            Nothing saved yet. <Link href="/" style={{ color: "var(--accent-teal)", fontWeight: 600 }}>Generate a presentation</Link>{" "}
            while logged in and it'll show up here.
          </p>
        </div>
      )}

      {projects && projects.length > 0 && (
        <div style={{ marginTop: 36, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 26 }}>
          {projects.map((p) => (
            <Link key={p.project_id} href={`/projects/${p.project_id}`} style={{ textDecoration: "none" }}>
              <div className="index-card">
                <p className="eyebrow" style={{ marginBottom: 8, fontSize: 11 }}>
                  {new Date(p.updated_at * 1000).toLocaleDateString()}
                </p>
                <h3 style={{ fontSize: "1.1rem", color: "var(--pencil)" }}>{p.title}</h3>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
