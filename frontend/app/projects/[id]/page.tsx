"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getProject, exportProject } from "@/lib/api-client";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Awaited<ReturnType<typeof getProject>> | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    getProject(projectId)
      .then(setProject)
      .catch((e) => {
        if (e.message === "UNAUTHENTICATED") {
          window.location.href = "/login";
        } else {
          setError(e.message);
        }
      });
  }, [projectId]);

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await exportProject(projectId, "pptx");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "presentation.pptx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e.message || "Export failed");
    } finally {
      setExporting(false);
    }
  }

  if (error) {
    return (
      <div className="container" style={{ paddingTop: 64 }}>
        <p className="error-text">{error}</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="container" style={{ paddingTop: 64 }}>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="container" style={{ paddingTop: 56, paddingBottom: 96, maxWidth: 640 }}>
      <p className="eyebrow" style={{ marginBottom: 10 }}>
        {project.slide_count} slides &middot; {project.audience_type.replace("_", " ")}
      </p>
      <h1 style={{ fontSize: "2rem" }}>Presentation outline</h1>

      <div style={{ marginTop: 30, display: "flex", flexDirection: "column", gap: 10 }}>
        {project.slides.map((s) => (
          <div key={s.order} className="index-card" style={{ display: "flex", gap: 14, alignItems: "baseline" }}>
            <span className="eyebrow" style={{ fontSize: 12, minWidth: 24 }}>{s.order}</span>
            <span style={{ fontWeight: 500 }}>{s.title}</span>
          </div>
        ))}
      </div>

      <button className="btn btn-primary" style={{ marginTop: 32 }} onClick={handleExport} disabled={exporting}>
        {exporting ? "Building file…" : "Export as PowerPoint"}
      </button>
    </div>
  );
}
