"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  generateFromTopicAsync,
  generateAsync,
  getJobStatus,
  jobDownloadUrl,
  getProject,
  getSessionToken,
  listWorkspaces,
  WorkspaceSummary,
} from "@/lib/api-client";
import { ExportFormat } from "@/lib/export-formats";

type Mode = "topic" | "document";

type Msg =
  | { kind: "assistant-text"; id: string; text: string }
  | { kind: "user-text"; id: string; text: string }
  | { kind: "job"; id: string; jobId: string; outputFormat: ExportFormat };

const STAGE_LABELS = [
  "Understanding request",
  "Building outline",
  "Generating content",
  "Designing slides",
  "Selecting visuals",
  "Applying design",
];

// Must match the stage strings the backend reports via GET /jobs/{id}
// (backend/engines/ai_generate.py's STAGE_* constants, ADR-040), in order.
const STAGE_KEYS = [
  "understanding_request",
  "building_outline",
  "generating_content",
  "designing_slides",
  "selecting_visuals",
  "applying_design",
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function JobBubble({ jobId, outputFormat }: { jobId: string; outputFormat: ExportFormat }) {
  const [status, setStatus] = useState<"pending" | "running" | "done" | "failed">("pending");
  const [stageIdx, setStageIdx] = useState(0);
  const [result, setResult] = useState<{
    slideCount?: number;
    projectId?: string | null;
    qualityScore?: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slides, setSlides] = useState<{ order: number; title: string }[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    let usingRealStage = false;
    let stageTimer: ReturnType<typeof setInterval> | null = null;

    // Cosmetic fallback progression, only used until (if ever) the
    // backend reports a real stage for this job. Both topic-generation
    // and document-upload jobs report real stages as of ADR-040 (the
    // document path just has 4 of the 6 shared labels, since it's a
    // rule-based-structure-plus-optional-AI-enhancement pipeline, not
    // the topic path's separate outline/content/layout calls) — this
    // timer is only ever seen briefly before the first real stage
    // arrives, or on an older/misbehaving backend that never reports one.
    stageTimer = setInterval(() => {
      if (usingRealStage) return;
      setStageIdx((i) => (i < STAGE_LABELS.length - 1 ? i + 1 : i));
    }, 1600);

    const poll = async () => {
      try {
        const s = await getJobStatus(jobId);
        if (cancelled) return;
        if (s.status === "done") {
          setStatus("done");
          setStageIdx(STAGE_LABELS.length - 1);
          setResult({ slideCount: s.slide_count, projectId: s.project_id, qualityScore: s.quality_score });
          if (stageTimer) clearInterval(stageTimer);
          if (s.project_id) {
            try {
              const proj = await getProject(s.project_id);
              if (!cancelled) setSlides(proj.slides);
            } catch {
              /* preview is best-effort; download still works without it */
            }
          }
          return;
        }
        if (s.status === "failed") {
          setStatus("failed");
          setError(s.error || "Generation failed.");
          if (stageTimer) clearInterval(stageTimer);
          return;
        }
        if (s.stage) {
          const idx = STAGE_KEYS.indexOf(s.stage);
          if (idx >= 0) {
            usingRealStage = true;
            setStageIdx(idx);
          }
        }
        setStatus(s.status as "pending" | "running");
        setTimeout(poll, 1200);
      } catch (e) {
        if (!cancelled) {
          setStatus("failed");
          setError(e instanceof Error ? e.message : "Could not check job status.");
          if (stageTimer) clearInterval(stageTimer);
        }
      }
    };
    poll();

    return () => {
      cancelled = true;
      if (stageTimer) clearInterval(stageTimer);
    };
  }, [jobId]);

  if (status === "failed") {
    return <div className="op-error-bubble">Something went wrong: {error}</div>;
  }

  if (status !== "done") {
    return (
      <div className="op-steps">
        {STAGE_LABELS.map((label, i) => (
          <span key={label} className={`op-step ${i < stageIdx ? "done" : i === stageIdx ? "active" : ""}`}>
            <span className="op-step-dot" />
            {label}
          </span>
        ))}
      </div>
    );
  }

  const FORMAT_CONFIG: Record<ExportFormat, {
    label: string; icon: string; downloadLabel: string; sectionsNoun: string;
  }> = {
    pptx: { label: "presentation", icon: "PPTX", downloadLabel: "Download .zip", sectionsNoun: "slides" },
    document_docx: { label: "document", icon: "DOCX", downloadLabel: "Download .docx", sectionsNoun: "sections" },
    document_pdf: { label: "PDF", icon: "PDF", downloadLabel: "Download .pdf", sectionsNoun: "sections" },
  };
  const cfg = FORMAT_CONFIG[outputFormat];

  // The full slide-by-slide preview (title + content) lives in the
  // right-hand preview panel only (JobBubblePreviewMirror), not
  // duplicated here too — this bubble just confirms the result and
  // gets out of the way, matching how a chat message shouldn't repeat
  // something already visible right next to it.
  return (
    <>
      <div className="op-result-card">
        <div className="op-result-icon">{cfg.icon}</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>
            Your {cfg.label} is ready
          </div>
          <div className="op-result-meta">
            {result?.slideCount ?? slides?.length ?? "—"} {cfg.sectionsNoun}
            {typeof result?.qualityScore === "number" ? ` · quality ${Math.round(result.qualityScore * 100)}%` : ""}
          </div>
        </div>
      </div>
      <div className="op-result-actions">
        <a className="op-pill-btn primary" href={jobDownloadUrl(jobId)} download>
          {cfg.downloadLabel}
        </a>
        {result?.projectId ? (
          <Link className="op-pill-btn" href={`/projects/${result.projectId}`}>
            {outputFormat === "pptx" ? "Edit slide by slide →" : "Edit in project workspace →"}
          </Link>
        ) : (
          <span className="op-pill-btn" style={{ cursor: "default" }}>
            Log in to save &amp; edit this {cfg.label}
          </span>
        )}
      </div>
    </>
  );
}

export default function StudioPage() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      kind: "assistant-text",
      id: "welcome",
      text: "Tell me what you'd like to present — a topic, an idea, or upload a document — and I'll build the deck.",
    },
  ]);
  const [mode, setMode] = useState<Mode>("topic");
  const [outputFormat, setExportFormat] = useState<ExportFormat>("pptx");
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");  // "" = ungrouped
  const [previewOpen, setPreviewOpen] = useState(true);
  const [previewTab, setPreviewTab] = useState<"preview" | "edit">("preview");
  const [previewProjectId, setPreviewProjectId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const signedIn = typeof window !== "undefined" && !!getSessionToken();

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!signedIn) return;
    listWorkspaces().then(setWorkspaces).catch(() => setWorkspaces([]));
  }, [signedIn]);

  useEffect(() => {
    // Settings page (ADR-056) writes a preferred default format here;
    // applied once on mount only, so switching formats mid-session via
    // the composer pills is never silently overridden.
    const preferred = window.localStorage.getItem("op_default_export_format");
    if (preferred && ["pptx", "document_docx", "document_pdf"].includes(preferred)) {
      setExportFormat(preferred as ExportFormat);
    }
  }, []);

  async function handleSend() {
    if (busy) return;
    if (mode === "topic" && !input.trim()) return;
    if (mode === "document" && !file) return;

    const userLabel = mode === "topic" ? input.trim() : `Uploaded: ${file?.name}`;
    setMessages((m) => [...m, { kind: "user-text", id: uid(), text: userLabel }]);
    setBusy(true);

    try {
      let job: { job_id: string };
      const workspaceId = selectedWorkspaceId || undefined;  // ADR-044
      if (mode === "topic") {
        job = await generateFromTopicAsync({ topic: input.trim(), exportFormat: outputFormat, workspaceId });
      } else {
        job = await generateAsync(file as File, { exportFormat: outputFormat, workspaceId });
      }
      setInput("");
      setFile(null);
      setMessages((m) => [...m, { kind: "job", id: uid(), jobId: job.job_id, outputFormat }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { kind: "assistant-text", id: uid(), text: `Couldn't start generation: ${e instanceof Error ? e.message : "unknown error"}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const latestJob = [...messages].reverse().find((m): m is Extract<Msg, { kind: "job" }> => m.kind === "job");

  return (
    <div className="op-studio">
      <div className="op-chat-col">
        <div className="op-chat-header">New chat</div>
        <div className="op-chat-thread" ref={threadRef}>
          {messages.map((m) => {
            if (m.kind === "assistant-text") {
              return (
                <div key={m.id} className="op-bubble op-bubble-assistant op-bubble-row">
                  <span className="op-bubble-avatar" />
                  <span>{m.text}</span>
                </div>
              );
            }
            if (m.kind === "user-text") {
              return (
                <div key={m.id} className="op-bubble op-bubble-user">
                  {m.text}
                </div>
              );
            }
            return (
              <div key={m.id}>
                <div className="op-bubble op-bubble-assistant op-bubble-row" style={{ marginBottom: 0 }}>
                  <span className="op-bubble-avatar" />
                  <span>Working on it…</span>
                </div>
                <JobBubble jobId={m.jobId} outputFormat={m.outputFormat} />
              </div>
            );
          })}
        </div>

        {!signedIn && (
          <div className="op-composer-hint" style={{ padding: "0 24px 8px 24px" }}>
            <Link href="/login" style={{ color: "var(--op-violet)", fontWeight: 600 }}>
              Log in
            </Link>{" "}
            to save this as an editable project — generation without an account still works, you just get a download only.
          </div>
        )}

        <div className="op-composer">
          <div className="op-mode-row">
            <button className={`op-mode-pill ${mode === "topic" ? "active" : ""}`} onClick={() => setMode("topic")}>
              Describe a topic
            </button>
            <button className={`op-mode-pill ${mode === "document" ? "active" : ""}`} onClick={() => setMode("document")}>
              Upload a source document
            </button>
            <span style={{ width: 1, alignSelf: "stretch", background: "var(--op-border)", margin: "0 4px" }} />
            <button
              className={`op-mode-pill ${outputFormat === "pptx" ? "active" : ""}`}
              onClick={() => setExportFormat("pptx")}
              title="Generate a slide deck (.pptx)"
            >
              → Slides
            </button>
                <button
                  className={`op-mode-pill ${outputFormat === "document_docx" ? "active" : ""}`}
                  onClick={() => setExportFormat("document_docx")}
                  title="Generate a Word document (.docx) instead of a deck"
                >
                  → Document
                </button>
                <button
                  className={`op-mode-pill ${outputFormat === "document_pdf" ? "active" : ""}`}
                  onClick={() => setExportFormat("document_pdf")}
                  title="Generate a PDF document (.pdf) instead of a deck"
                >
                  → PDF
                </button>
                {signedIn && workspaces.length > 0 && (
                  <select
                    className="op-workspace-select"
                    value={selectedWorkspaceId}
                    onChange={(e) => setSelectedWorkspaceId(e.target.value)}
                    title="Save this generation into a workspace"
                  >
                    <option value="">No workspace</option>
                    {workspaces.map((w) => (
                      <option key={w.workspace_id} value={w.workspace_id}>{w.name}</option>
                    ))}
                  </select>
            )}
          </div>

          <div className="op-composer-box">
              {mode === "topic" ? (
                <textarea
                  rows={1}
                  placeholder="e.g. Create a 10-slide investor pitch deck for an AI healthcare startup"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
              ) : (
                <div style={{ flex: 1, fontSize: 14.5, color: file ? "var(--op-text)" : "var(--op-text-muted)", padding: "6px 0" }}>
                  {file ? file.name : "Choose a .txt or .pdf file…"}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.pdf"
                    style={{ display: "none" }}
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                  <button
                    className="op-pill-btn"
                    style={{ marginLeft: 10, padding: "3px 10px", fontSize: 12 }}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Browse
                  </button>
                </div>
              )}
              <button className="op-send-btn" onClick={handleSend} disabled={busy || (mode === "topic" ? !input.trim() : !file)}>
                →
              </button>
          </div>
          <div className="op-composer-hint">
            {mode === "topic" && "Enter to send, Shift+Enter for a new line."}
            {mode === "document" && "Documents are enhanced with AI when a provider is configured, deterministic fallback otherwise."}
            {outputFormat === "document_docx" ? " Building a Word document, not a slide deck." : ""}
          </div>
        </div>
      </div>

      <div className={`op-preview-col ${previewOpen ? "" : "closed"}`}>
        {previewOpen ? (
          <>
            <div className="op-preview-tabs">
              <button
                className={`op-preview-tab ${previewTab === "preview" ? "active" : ""}`}
                onClick={() => setPreviewTab("preview")}
              >
                Preview
              </button>
              {previewProjectId ? (
                <Link href={`/projects/${previewProjectId}`} className="op-preview-tab" title="Full slide-by-slide editing">
                  Edit
                </Link>
              ) : (
                <span
                  className="op-preview-tab disabled"
                  title="Available once this generation is saved to a project (log in, then generate)"
                >
                  Edit
                </span>
              )}
              <button className="op-preview-close-btn" onClick={() => setPreviewOpen(false)} title="Close preview">
                ×
              </button>
            </div>
            {!latestJob ? (
              <div className="op-preview-empty">
                <div style={{ fontSize: 28 }}>◇</div>
                Your slides will appear here once generation starts.
              </div>
            ) : (
              <div style={{ padding: 4 }}>
                {/* The JobBubble already renders the slide grid inline in the
                    thread; this column mirrors it for the currently-active job
                    so the layout matches the reference design. */}
                <JobBubblePreviewMirror key={latestJob.jobId} jobId={latestJob.jobId} onProjectId={setPreviewProjectId} />
              </div>
            )}
          </>
        ) : (
          <button className="op-preview-reopen-btn" onClick={() => setPreviewOpen(true)} title="Show preview">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M15 4v16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

// Small dedicated fetch for the right-hand preview column so it doesn't
// depend on the chat bubble's internal state.
// Mirrors backend/adapters/export/pptx_adapter.py's _COLOR_SETS (title/
// accent/background only — text color isn't needed here since this is
// a compact preview, not a full render). Kept as a small, deliberate
// duplication rather than a shared source of truth across languages;
// if a color set is added on the backend, add its match here too.
const THEME_COLORS: Record<string, { title: string; accent: string; background: string }> = {
  neutral: { title: "#222222", accent: "#2E5C8A", background: "#F7F7F4" },
  blue_academic: { title: "#1B3A5C", accent: "#C86B2E", background: "#F1F4F8" },
  warm_editorial: { title: "#3D251A", accent: "#D96C2E", background: "#FBF3EA" },
  modern_dark: { title: "#F2F2F0", accent: "#5DC9B0", background: "#1E2124" },
};

function JobBubblePreviewMirror({ jobId, onProjectId }: { jobId: string; onProjectId?: (id: string) => void }) {
  const [slides, setSlides] = useState<{ order: number; title: string; bullets: string[] }[] | null>(null);
  const [colorSetId, setColorSetId] = useState("neutral");
  const [doneNoProject, setDoneNoProject] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const s = await getJobStatus(jobId);
        if (cancelled) return;
        if (s.status === "done") {
          if (s.project_id) {
            const proj = await getProject(s.project_id);
            if (!cancelled) {
              setSlides(proj.slides);
              setColorSetId(proj.theme?.color_set_id || "neutral");
              onProjectId?.(s.project_id);
            }
          } else {
            setDoneNoProject(true);
          }
          return;
        }
        if (s.status === "failed") return;
        setTimeout(check, 1500);
      } catch {
        /* silent — chat thread already surfaces the error */
      }
    };
    check();
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  if (!slides && !doneNoProject) {
    return <div className="op-preview-empty">Generating…</div>;
  }
  if (doneNoProject) {
    return <div className="op-preview-empty">Log in before generating to see a live slide preview here — anonymous generations are download-only.</div>;
  }

  const colors = THEME_COLORS[colorSetId] || THEME_COLORS.neutral;

  // Real content (title + a couple of real bullet lines), styled with
  // the deck's actual theme colors — this is what actually answers
  // "what does the deck look like" without downloading it, versus the
  // title-only chips this replaced.
  return (
    <div className="op-preview-deck">
      {slides!.map((s) => (
        <div
          key={s.order}
          className="op-preview-slide-card"
          style={{ background: colors.background, borderColor: colors.accent }}
        >
          <div className="op-preview-slide-num" style={{ color: colors.accent }}>{s.order}</div>
          <div className="op-preview-slide-title" style={{ color: colors.title }}>{s.title}</div>
          {s.bullets.slice(0, 3).map((b, i) => (
            <div key={i} className="op-preview-slide-bullet" style={{ color: colors.title }}>
              <span style={{ color: colors.accent }}>—</span> {b}
            </div>
          ))}
          {s.bullets.length > 3 && (
            <div className="op-preview-slide-more">+{s.bullets.length - 3} more</div>
          )}
        </div>
      ))}
    </div>
  );
}
