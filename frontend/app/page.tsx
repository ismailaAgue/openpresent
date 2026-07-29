"use client";

import { useRef, useState } from "react";
import { generateSync } from "@/lib/api-client";

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "working" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleGenerate() {
    if (!file) return;
    setStatus("working");
    setErrorMsg("");
    try {
      const blob = await generateSync(file, "pptx");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "presentation.pptx";
      a.click();
      window.URL.revokeObjectURL(url);
      setStatus("done");
    } catch (e: any) {
      setStatus("error");
      setErrorMsg(e.message || "Something went wrong");
    }
  }

  return (
    <div className="container" style={{ paddingTop: 64, paddingBottom: 96 }}>
      <p className="eyebrow" style={{ marginBottom: 14 }}>For students, at 11pm, before a deadline</p>
      <h1 style={{ maxWidth: 700 }}>
        Turn your notes into a <span className="highlight">real presentation</span>. Free. No credits to count.
      </h1>
      <p style={{ maxWidth: 560, marginTop: 18, fontSize: 17 }}>
        Upload an essay, a report, or rough notes. Get back a structured, styled deck.
        No account required to try it. No "3 free generations" timer. Ever.
      </p>

      <div className="card" style={{ marginTop: 40, maxWidth: 520 }}>
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
          Want to save this and turn it into other formats later?{" "}
          <a href="/register" style={{ color: "var(--accent-teal)", fontWeight: 600 }}>Create a free account</a> —
          still no limits, just lets you come back to it.
        </p>
      </div>

      <section style={{ marginTop: 88, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>
        <FeatureNote
          eyebrow="No credit anxiety"
          text="Generate as many presentations as you actually need for school. Nothing counts down."
        />
        <FeatureNote
          eyebrow="Works with zero AI"
          text="A real, well-structured deck comes from smart rules, not a black box. AI only makes it better when it's available."
        />
        <FeatureNote
          eyebrow="Your work, reusable"
          text="Save a project once, regenerate it as a different version later — a summary, a different theme, anything."
        />
      </section>
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
