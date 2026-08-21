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
} from "@/lib/api-client";

type Mode = "topic" | "document";

type Msg =
  | { kind: "assistant-text"; id: string; text: string }
  | { kind: "user-text"; id: string; text: string }
  | { kind: "job"; id: string; jobId: string };

const STAGE_LABELS = [
  "Understanding request",
  "Building outline",
  "Generating content",
  "Designing slides",
  "Selecting visuals",
  "Applying design",
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function JobBubble({ jobId }: { jobId: string }) {
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
    let stageTimer: ReturnType<typeof setInterval> | null = null;

    // Cosmetic stage progression while the job runs — the backend only
    // reports pending/running/done/failed, not which of the five real
    // pipeline stages is active, so this advances on a timer rather than
    // live telemetry (the real 5-stage pipeline is documented in
    // ARCHITECTURE_DECISIONS.md).
    stageTimer = setInterval(() => {
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
        setStatus(s.status as "pending" | "running");
        setTimeout(poll, 1500);
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

  return (
    <>
      <div className="op-result-card">
        <div className="op-result-icon">PPTX</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13.5 }}>Your presentation is ready</div>
          <div className="op-result-meta">
            {result?.slideCount ?? slides?.length ?? "—"} slides
            {typeof result?.qualityScore === "number" ? ` · quality ${Math.round(result.qualityScore * 100)}%` : ""}
          </div>
        </div>
      </div>
      <div className="op-result-actions">
        <a className="op-pill-btn primary" href={jobDownloadUrl(jobId)} download>
          Download .zip
        </a>
        {result?.projectId ? (
          <Link className="op-pill-btn" href={`/projects/${result.projectId}`}>
            Edit slide by slide →
          </Link>
        ) : (
          <span className="op-pill-btn" style={{ cursor: "default" }}>
            Log in to save &amp; edit slides
          </span>
        )}
      </div>
      {slides && slides.length > 0 && (
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
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const signedIn = typeof window !== "undefined" && !!getSessionToken();

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (busy) return;
    if (mode === "topic" && !input.trim()) return;
    if (mode === "document" && !file) return;

    const userLabel = mode === "topic" ? input.trim() : `Uploaded: ${file?.name}`;
    setMessages((m) => [...m, { kind: "user-text", id: uid(), text: userLabel }]);
    setBusy(true);

    try {
      let job: { job_id: string };
      if (mode === "topic") {
        job = await generateFromTopicAsync({ topic: input.trim() });
      } else {
        job = await generateAsync(file as File);
      }
      setInput("");
      setFile(null);
      setMessages((m) => [...m, { kind: "job", id: uid(), jobId: job.job_id }]);
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
                <JobBubble jobId={m.jobId} />
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
              Upload a document
            </button>
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
            {mode === "topic" ? "Enter to send, Shift+Enter for a new line." : "Documents are enhanced with AI when a provider is configured, deterministic fallback otherwise."}
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
