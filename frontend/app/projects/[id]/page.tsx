"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  getProject, exportProject, getSlide, editSlide, regenerateSlide, SlideDetail,
} from "@/lib/api-client";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Awaited<ReturnType<typeof getProject>> | null>(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null);

  function loadProject() {
    getProject(projectId)
      .then(setProject)
      .catch((e) => {
        if (e.message === "UNAUTHENTICATED") {
          window.location.href = "/login";
        } else {
          setError(e.message);
        }
      });
  }

  useEffect(loadProject, [projectId]);

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
      <p style={{ fontSize: 14, color: "var(--muted)", marginTop: 8 }}>
        Click any slide to edit it directly, or ask AI to rewrite it — every other slide stays
        exactly as it is.
      </p>

      <div style={{ marginTop: 30, display: "flex", flexDirection: "column", gap: 10 }}>
        {project.slides.map((s) => (
          <SlideRow
            key={s.order}
            projectId={projectId}
            order={s.order}
            title={s.title}
            expanded={expandedOrder === s.order}
            onToggle={() => setExpandedOrder(expandedOrder === s.order ? null : s.order)}
            onSaved={(newTitle) => {
              setProject((p) => p && {
                ...p,
                slides: p.slides.map((sl) => sl.order === s.order ? { ...sl, title: newTitle } : sl),
              });
            }}
          />
        ))}
      </div>

      <button className="btn btn-primary" style={{ marginTop: 32 }} onClick={handleExport} disabled={exporting}>
        {exporting ? "Building file…" : "Export as PowerPoint"}
      </button>
    </div>
  );
}

function SlideRow({
  projectId, order, title, expanded, onToggle, onSaved,
}: {
  projectId: string;
  order: number;
  title: string;
  expanded: boolean;
  onToggle: () => void;
  onSaved: (newTitle: string) => void;
}) {
  const [detail, setDetail] = useState<SlideDetail | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editBullets, setEditBullets] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [instructions, setInstructions] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "regenerating">("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!expanded) return;
    setError("");
    getSlide(projectId, order)
      .then((d) => {
        setDetail(d);
        setEditTitle(d.title);
        setEditBullets(d.bullets.join("\n"));
        setEditNotes(d.notes);
      })
      .catch((e) => setError(e.message || "Could not load this slide"));
  }, [expanded, projectId, order]);

  async function handleSave() {
    setStatus("saving");
    setError("");
    try {
      const bullets = editBullets.split("\n").map((b) => b.trim()).filter(Boolean);
      const updated = await editSlide(projectId, order, { title: editTitle, bullets, notes: editNotes });
      setDetail(updated);
      onSaved(updated.title);
    } catch (e: any) {
      setError(e.message || "Could not save your edit");
    } finally {
      setStatus("idle");
    }
  }

  async function handleRegenerate() {
    setStatus("regenerating");
    setError("");
    try {
      const updated = await regenerateSlide(projectId, order, instructions || undefined);
      setDetail(updated);
      setEditTitle(updated.title);
      setEditBullets(updated.bullets.join("\n"));
      setEditNotes(updated.notes);
      onSaved(updated.title);
    } catch (e: any) {
      setError(e.message || "Regeneration failed");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <div className="index-card" style={{ padding: 14 }}>
      <div
        style={{ display: "flex", gap: 14, alignItems: "baseline", cursor: "pointer" }}
        onClick={onToggle}
      >
        <span className="eyebrow" style={{ fontSize: 12, minWidth: 24 }}>{order}</span>
        <span style={{ fontWeight: 500, flex: 1 }}>{detail ? editTitle || title : title}</span>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>{expanded ? "Close" : "Edit"}</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {!detail && !error && <p style={{ fontSize: 14, color: "var(--muted)" }}>Loading…</p>}

          {detail && (
            <>
              <div>
                <label className="field-label" htmlFor={`title-${order}`}>Title</label>
                <input id={`title-${order}`} value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor={`bullets-${order}`}>
                  Bullets <span style={{ color: "var(--muted)", fontWeight: 400 }}>(one per line)</span>
                </label>
                <textarea
                  id={`bullets-${order}`}
                  rows={4}
                  value={editBullets}
                  onChange={(e) => setEditBullets(e.target.value)}
                />
              </div>
              <div>
                <label className="field-label" htmlFor={`notes-${order}`}>Speaker notes</label>
                <textarea
                  id={`notes-${order}`}
                  rows={2}
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", gap: 10 }}>
                <button className="btn btn-primary" onClick={handleSave} disabled={status !== "idle"}>
                  {status === "saving" ? "Saving…" : "Save changes"}
                </button>
              </div>

              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: 4 }}>
                <label className="field-label" htmlFor={`instructions-${order}`}>
                  Or ask AI to rewrite this slide <span style={{ color: "var(--muted)", fontWeight: 400 }}>(optional instructions)</span>
                </label>
                <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
                  <input
                    id={`instructions-${order}`}
                    placeholder="e.g. make this more concise"
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="btn btn-secondary" onClick={handleRegenerate} disabled={status !== "idle"}>
                    {status === "regenerating" ? "Regenerating…" : "Regenerate with AI"}
                  </button>
                </div>
              </div>
            </>
          )}

          {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
        </div>
      )}
    </div>
  );
}
