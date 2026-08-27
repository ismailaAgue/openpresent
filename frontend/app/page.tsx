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
  askDocument,
} from "@/lib/api-client";
import { ExportFormat } from "@/lib/export-formats";

type Mode = "topic" | "document" | "ask";

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
    label: string; icon: string; downloadLabel: string; sectionsNoun: string; isSvg: boolean;
  }> = {
    pptx: { label: "presentation", icon: "PPTX", downloadLabel: "Download .zip", sectionsNoun: "slides", isSvg: false },
    document_docx: { label: "document", icon: "DOCX", downloadLabel: "Download .docx", sectionsNoun: "sections", isSvg: false },
    infographic_svg: { label: "infographic", icon: "SVG", downloadLabel: "Download .svg", sectionsNoun: "sections", isSvg: true },
    diagram_svg: { label: "diagram", icon: "SVG", downloadLabel: "Download .svg", sectionsNoun: "steps", isSvg: true },
    poster_svg: { label: "poster", icon: "SVG", downloadLabel: "Download .svg", sectionsNoun: "highlights", isSvg: true },
  };
  const cfg = FORMAT_CONFIG[outputFormat];

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
      {cfg.isSvg && (
        <div className="op-infographic-preview">
          <img src={jobDownloadUrl(jobId)} alt={`Generated ${cfg.label}`} />
        </div>
      )}
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
      {!cfg.isSvg && slides && slides.length > 0 && (
        <div className="op-slide-grid" style={{ paddingLeft: 32, gridTemplateColumns: "repeat(3, 1fr)" }}>
          {slides.slice(0, 6).map((s) => (
            <div key={s.order} className="op-slide-thumb">
              <span className="op-slide-thumb-num">{s.order}</span>
              {s.title}
            </div>
          ))}
        </div>
      )}
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

  async function handleSend() {
    if (busy) return;
    if (mode === "topic" && !input.trim()) return;
    if (mode === "document" && !file) return;
    if (mode === "ask" && (!file || !input.trim())) return;

    const userLabel =
      mode === "topic" ? input.trim() :
      mode === "ask" ? `Asked about ${file?.name}: ${input.trim()}` :
      `Uploaded: ${file?.name}`;
    setMessages((m) => [...m, { kind: "user-text", id: uid(), text: userLabel }]);
    setBusy(true);

    try {
      if (mode === "ask") {
        // Synchronous — no job/polling, unlike generation (ADR-050).
        const result = await askDocument(file as File, input.trim());
        setInput("");
        setFile(null);
        setMessages((m) => [...m, { kind: "assistant-text", id: uid(), text: result.answer }]);
        return;
      }

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
      const verb = mode === "ask" ? "get an answer" : "start generation";
      setMessages((m) => [
        ...m,
        { kind: "assistant-text", id: uid(), text: `Couldn't ${verb}: ${e instanceof Error ? e.message : "unknown error"}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const latestJob = [...messages].reverse().find((m): m is Extract<Msg, { kind: "job" }> => m.kind === "job");

  return (
    <div className="op-studio">
      <div className="op-chat-col">
        <div className="op-chat-header">New presentation</div>
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
            <button className={`op-mode-pill ${mode === "ask" ? "active" : ""}`} onClick={() => setMode("ask")}>
              Ask a question about a document
            </button>
            {mode !== "ask" && (
              <>
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
                  className={`op-mode-pill ${outputFormat === "infographic_svg" ? "active" : ""}`}
                  onClick={() => setExportFormat("infographic_svg")}
                  title="Generate a single-page visual summary (.svg) instead of a deck"
                >
                  → Infographic
                </button>
                <button
                  className={`op-mode-pill ${outputFormat === "diagram_svg" ? "active" : ""}`}
                  onClick={() => setExportFormat("diagram_svg")}
                  title="Generate a process-flow diagram (.svg) instead of a deck"
                >
                  → Diagram
                </button>
                <button
                  className={`op-mode-pill ${outputFormat === "poster_svg" ? "active" : ""}`}
                  onClick={() => setExportFormat("poster_svg")}
                  title="Generate a shareable poster (.svg) instead of a deck"
                >
                  → Poster
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
              </>
            )}
          </div>

          {mode === "ask" ? (
            <div className="op-ask-box">
              <div className="op-ask-file-row">
                {file ? file.name : "Choose a .txt or .pdf file to ask about…"}
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
              <div className="op-composer-box">
                <textarea
                  rows={1}
                  placeholder="e.g. What does this document say about pricing?"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button className="op-send-btn" onClick={handleSend} disabled={busy || !file || !input.trim()}>
                  →
                </button>
              </div>
            </div>
          ) : (
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
          )}
          <div className="op-composer-hint">
            {mode === "topic" && "Enter to send, Shift+Enter for a new line."}
            {mode === "document" && "Documents are enhanced with AI when a provider is configured, deterministic fallback otherwise."}
            {mode === "ask" && "Answers are grounded in the uploaded document only — not general knowledge."}
            {mode !== "ask" && outputFormat === "document_docx" ? " Building a Word document, not a slide deck." : ""}
          </div>
        </div>
      </div>

      <div className="op-preview-col">
        <div className="op-preview-tabs">
          <span className="op-preview-tab active">Preview</span>
          <span className="op-preview-tab" title="Full slide-by-slide editing lives in the saved project view">
            Edit
          </span>
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
            <JobBubblePreviewMirror jobId={latestJob.jobId} />
          </div>
        )}
      </div>
    </div>
  );
}

// Small dedicated fetch for the right-hand preview column so it doesn't
// depend on the chat bubble's internal state.
function JobBubblePreviewMirror({ jobId }: { jobId: string }) {
  const [slides, setSlides] = useState<{ order: number; title: string }[] | null>(null);
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
            if (!cancelled) setSlides(proj.slides);
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
  return (
    <div className="op-slide-grid">
      {slides!.map((s) => (
        <div key={s.order} className="op-slide-thumb">
          <span className="op-slide-thumb-num">{s.order}</span>
          {s.title}
        </div>
      ))}
    </div>
  );
}
