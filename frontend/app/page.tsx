"use client";

import { useRef, useState } from "react";
import { generateSync, generateFromTopicSync } from "@/lib/api-client";

type Mode = "topic" | "document";
type Status = "idle" | "working" | "done" | "error";

const AUDIENCES = [
  { value: "general", label: "General audience" },
  { value: "student_school", label: "School / classroom" },
  { value: "business", label: "Business / meeting" },
  { value: "academic", label: "Academic / conference" },
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "pt", label: "Portuguese" },
  { value: "de", label: "German" },
];

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}

export default function HomePage() {
  const [mode, setMode] = useState<Mode>("topic");

  return (
    <div className="container" style={{ paddingTop: 64, paddingBottom: 96 }}>
      <p className="eyebrow" style={{ marginBottom: 14 }}>AI-first, still no credits to count</p>
      <h1 style={{ maxWidth: 700 }}>
        Describe your presentation. Get a <span className="highlight">real, styled deck</span>. Free.
      </h1>
      <p style={{ maxWidth: 560, marginTop: 18, fontSize: 17 }}>
        Type a topic and OpenPresent plans, writes, and designs the whole thing — title
        slide to closing slide, speaker notes included. Have a document instead? Upload
        it and we'll structure that. No account required. No "3 free generations" timer. Ever.
      </p>

      <div className="mode-tabs" style={{ marginTop: 40 }}>
        <button
          className={`mode-tab ${mode === "topic" ? "active" : ""}`}
          onClick={() => setMode("topic")}
        >
          Generate from a topic
        </button>
        <button
          className={`mode-tab ${mode === "document" ? "active" : ""}`}
          onClick={() => setMode("document")}
        >
          Upload a document instead
        </button>
      </div>

      {mode === "topic" ? <TopicForm /> : <DocumentForm />}

      <section style={{ marginTop: 88, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>
        <FeatureNote
          eyebrow="AI-first, not AI-only"
          text="A real inference pipeline plans, drafts, and reviews your deck. No AI configured yet? A rule-based generator still produces a usable deck — never a dead end."
        />
        <FeatureNote
          eyebrow="No credit anxiety"
          text="Generate as many presentations as you actually need. Nothing counts down."
        />
        <FeatureNote
          eyebrow="Your work, reusable"
          text="Save a project once, regenerate it as a different version later — a summary, a different theme, anything."
        />
      </section>
    </div>
  );
}

function TopicForm() {
  const [topic, setTopic] = useState("");
  const [slideCount, setSlideCount] = useState(10);
  const [audienceType, setAudienceType] = useState("general");
  const [language, setLanguage] = useState("en");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleGenerate() {
    if (!topic.trim()) return;
    setStatus("working");
    setErrorMsg("");
    try {
      const blob = await generateFromTopicSync({
        topic, slideCount, audienceType, language, exportFormat: "pptx",
      });
      downloadBlob(blob, "presentation.pptx");
      setStatus("done");
    } catch (e: any) {
      setStatus("error");
      setErrorMsg(e.message || "Something went wrong");
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <label className="field-label" htmlFor="topic-input">What's the presentation about?</label>
      <textarea
        id="topic-input"
        rows={3}
        placeholder="e.g. The causes and effects of the French Revolution"
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 16 }}>
        <div>
          <label className="field-label" htmlFor="slide-count">Slides</label>
          <input
            id="slide-count"
            type="number"
            min={3}
            max={30}
            value={slideCount}
            onChange={(e) => setSlideCount(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="language">Language</label>
          <select id="language" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label className="field-label" htmlFor="audience">Audience</label>
          <select id="audience" value={audienceType} onChange={(e) => setAudienceType(e.target.value)}>
            {AUDIENCES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </div>
      </div>

      <div style={{ marginTop: 18, display: "flex", gap: 12, alignItems: "center" }}>
        <button
          className="btn btn-primary"
          disabled={!topic.trim() || status === "working"}
          onClick={handleGenerate}
        >
          {status === "working" ? "Planning and designing your deck…" : "Generate presentation"}
        </button>
        {status === "done" && <span style={{ fontSize: 14, color: "var(--accent-teal)" }}>Downloaded ✓</span>}
      </div>
      {status === "error" && <p className="error-text" style={{ marginTop: 10 }}>{errorMsg}</p>}
      <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 14, marginBottom: 0 }}>
        Larger decks take longer to plan — if generation feels slow, try fewer slides first.{" "}
        <a href="/register" style={{ color: "var(--accent-teal)", fontWeight: 600 }}>Create a free account</a>{" "}
        to save and revisit what you generate.
      </p>
    </div>
  );
}

function DocumentForm() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleGenerate() {
    if (!file) return;
    setStatus("working");
    setErrorMsg("");
    try {
      const blob = await generateSync(file, "pptx");
      downloadBlob(blob, "presentation.pptx");
      setStatus("done");
    } catch (e: any) {
      setStatus("error");
      setErrorMsg(e.message || "Something went wrong");
    }
  }

  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <label className="field-label" htmlFor="file-upload">Your document (.txt or .pdf)</label>
      <input
        id="file-upload"
        ref={inputRef}
        type="file"
        accept=".txt,.md,.pdf"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
        <button
          className="btn btn-primary"
          disabled={!file || status === "working"}
          onClick={handleGenerate}
        >
          {status === "working" ? "Building your deck…" : "Generate presentation"}
        </button>
        {status === "done" && <span style={{ fontSize: 14, color: "var(--accent-teal)" }}>Downloaded ✓</span>}
      </div>
      {status === "error" && <p className="error-text" style={{ marginTop: 10 }}>{errorMsg}</p>}
      <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 14, marginBottom: 0 }}>
        We'll structure and design a deck from what's already in your document — AI improves
        it further when available, but a good deck comes out either way.
      </p>
    </div>
  );
}

function FeatureNote({ eyebrow, text }: { eyebrow: string; text: string }) {
  return (
    <div>
      <p className="eyebrow" style={{ marginBottom: 8 }}>{eyebrow}</p>
      <p style={{ fontSize: 15 }}>{text}</p>
    </div>
  );
}
