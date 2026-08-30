"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSessionToken, getCurrentUser, logout } from "@/lib/api-client";
import { EXPORT_FORMATS, ExportFormat } from "@/lib/export-formats";

const DEFAULT_FORMAT_KEY = "op_default_export_format";

// ADR-056 — this route existed as a disabled "coming soon" link before
// this page, with no route behind it at all. What's here is
// deliberately small and all genuinely functional: real account info
// (via the new GET /auth/me), a real sign-out, and one real preference
// (default export format) that app/page.tsx actually reads on mount —
// nothing decorative that just looks like a setting without doing
// anything, which is what made the old link worse than just hiding it.
export default function SettingsPage() {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [defaultFormat, setDefaultFormat] = useState<ExportFormat | "">("");
  const [savedJustNow, setSavedJustNow] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!getSessionToken()) {
      router.push("/login");
      return;
    }
    getCurrentUser()
      .then((user) => {
        if (!user) {
          router.push("/login");
          return;
        }
        setEmail(user.email);
      })
      .finally(() => setLoading(false));

    const stored = window.localStorage.getItem(DEFAULT_FORMAT_KEY);
    if (stored) setDefaultFormat(stored as ExportFormat);
  }, [router]);

  function handleFormatChange(format: ExportFormat) {
    setDefaultFormat(format);
    window.localStorage.setItem(DEFAULT_FORMAT_KEY, format);
    setSavedJustNow(true);
    setTimeout(() => setSavedJustNow(false), 1500);
  }

  function handleSignOut() {
    logout();
    router.push("/");
  }

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: 64 }}>
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <div className="container" style={{ paddingTop: 56, paddingBottom: 96, maxWidth: 560 }}>
      <p className="eyebrow" style={{ marginBottom: 10 }}>Your account</p>
      <h1 style={{ fontSize: "2rem" }}>Settings</h1>

      <div className="card" style={{ marginTop: 30 }}>
        <label className="field-label">Signed in as</label>
        <p style={{ fontSize: 15, marginTop: 4 }}>{email}</p>
        <button className="btn btn-secondary" style={{ marginTop: 16 }} onClick={handleSignOut}>
          Sign out
        </button>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <label className="field-label" htmlFor="default-format">Default output format</label>
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, marginBottom: 12 }}>
          New chats on the home screen start with this format selected instead of always
          defaulting to a presentation.
        </p>
        <select
          id="default-format"
          value={defaultFormat}
          onChange={(e) => handleFormatChange(e.target.value as ExportFormat)}
          style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", minWidth: 220 }}
        >
          <option value="" disabled>Choose a format…</option>
          {EXPORT_FORMATS.map((f) => (
            <option key={f.format} value={f.format}>{f.shortLabel}</option>
          ))}
        </select>
        {savedJustNow && (
          <span style={{ marginLeft: 12, fontSize: 13, color: "var(--accent-teal)" }}>Saved</span>
        )}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <label className="field-label">Workspaces &amp; brand profiles</label>
        <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
          Managed from the sidebar on the home screen, not here — each workspace has its own
          brand profile since different workspaces often need different branding.
        </p>
      </div>
    </div>
  );
}
