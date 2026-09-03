"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  generateFromTopicAsync,
  generateAsync,
  getJobStatus,
  jobDownloadUrl,
  getProject,
  getProjectPreview,
  getSessionToken,
  listWorkspaces,
  WorkspaceSummary,
} from "@/lib/api-client";
import { ExportFormat } from "@/lib/export-formats";

type Mode = "topic" | "document";

// ADR-060 — `language` was already accepted end-to-end by every
// generation call and the AI prompts themselves; there was just never
// a UI control to set it away from the "en" default. Matches
// backend/validation/quality_validator.py's CLOSING_SLIDE_TEXT table —
// if a language is added there, it should be addable here too.
const LANGUAGE_OPTIONS = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Português" },
  { code: "nl", label: "Nederlands" },
  { code: "sv", label: "Svenska" },
  { code: "pl", label: "Polski" },
];

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
  // ADR-060 — language was already a real, fully-wired parameter all
  // the way through generateFromTopicAsync -> the AI prompt -> the
  // closing-slide language fix, but the composer never exposed a way
  // to set it away from the "en" default — this is that missing UI.
  const [language, setLanguage] = useState("en");
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
        job = await generateFromTopicAsync({ topic: input.trim(), exportFormat: outputFormat, workspaceId, language });
      } else {
        job = await generateAsync(file as File, { exportFormat: outputFormat, workspaceId, language });
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
                <select
                  className="op-workspace-select"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  title="Language to generate in"
                >
                  {LANGUAGE_OPTIONS.map((l) => (
                    <option key={l.code} value={l.code}>{l.label}</option>
                  ))}
                </select>
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
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.pdf"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setFile(f);
                  setMode(f ? "document" : "topic");
                }}
              />
              {/* Attach button, ChatGPT/Claude-style, instead of a separate
                  "upload a document" mode the person has to switch into
                  first — attaching a file IS the mode switch now. */}
              <button
                className="op-attach-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Attach a .txt or .pdf to generate from"
                type="button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.44 11.05 12.25 20.24a5.5 5.5 0 0 1-7.78-7.78l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95L9.41 17.41a1.5 1.5 0 0 1-2.12-2.12l8.49-8.49" />
                </svg>
              </button>

              {file ? (
                <div className="op-attachment-chip">
                  <span className="op-attachment-name">{file.name}</span>
                  <button
                    className="op-attachment-remove"
                    onClick={() => { setFile(null); setMode("topic"); }}
                    title="Remove attachment"
                    type="button"
                  >
                    ×
                  </button>
                </div>
              ) : (
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
function JobBubblePreviewMirror({ jobId, onProjectId }: { jobId: string; onProjectId?: (id: string) => void }) {
  const [previewSlides, setPreviewSlides] = useState<{ order: number; svg: string }[] | null>(null);
  const [doneNoProject, setDoneNoProject] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const s = await getJobStatus(jobId);
        if (cancelled) return;
        if (s.status === "done") {
          if (s.project_id) {
            // ADR-061 — real, themed slide previews (server-rendered
            // SVG matching PptxExportAdapter's actual design
            // decisions), not a generic title+bullets text mockup.
            // See lib/api-client.ts's getProjectPreview for exactly
            // what this does and doesn't match pixel-for-pixel.
            const preview = await getProjectPreview(s.project_id);
            if (!cancelled) {
              setPreviewSlides(preview.slides);
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

  if (!previewSlides && !doneNoProject) {
    return <div className="op-preview-empty">Generating…</div>;
  }
  if (doneNoProject) {
    return <div className="op-preview-empty">Log in before generating to see a live slide preview here — anonymous generations are download-only.</div>;
  }

  return (
    <div className="op-preview-deck">
      {previewSlides!.map((s) => (
        <div
          key={s.order}
          className="op-preview-slide-svg"
          // The backend renders trusted, server-generated SVG markup
          // from the person's own project data — not arbitrary
          // user-supplied HTML, so this is the same trust boundary as
          // any other authenticated API response rendered in the UI.
          dangerouslySetInnerHTML={{ __html: s.svg }}
        />
      ))}
    </div>
  );
}
