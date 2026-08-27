"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getSessionToken, listProjects, logout, ProjectSummary,
  listWorkspaces, createWorkspace, deleteWorkspace, getWorkspace, WorkspaceSummary,
  getBrandProfile, setBrandProfile, deleteBrandProfile, BrandProfile,
} from "@/lib/api-client";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/dashboard", label: "Recent presentations", icon: "clock" },
  { href: "/templates", label: "Templates", icon: "grid", comingSoon: true },
  { href: "/brand", label: "Brand kits", icon: "palette", comingSoon: true },
  { href: "/assets", label: "Assets", icon: "image", comingSoon: true },
];

function Icon({ name }: { name: string }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "home":
      return <svg {...common}><path d="M3 11.5 12 4l9 7.5" /><path d="M5 10v9h14v-9" /></svg>;
    case "clock":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></svg>;
    case "grid":
      return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>;
    case "palette":
      return <svg {...common}><path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-1 2-2 0-.6-.3-1-.6-1.4-.3-.4-.5-.8-.1-1.3.4-.5 1-.3 1.6-.3A5 5 0 0 0 20 11c0-4.4-3.6-8-8-8Z" /><circle cx="7.5" cy="11.5" r="1" fill="currentColor" /><circle cx="9.5" cy="7.5" r="1" fill="currentColor" /><circle cx="14.5" cy="7.5" r="1" fill="currentColor" /></svg>;
    case "image":
      return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="m21 15-5-5-9 9" /></svg>;
    case "plus":
      return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
    case "folder":
      return <svg {...common}><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" /></svg>;
    case "chevron":
      return <svg {...common} style={{ transition: "transform 0.12s ease" }}><path d="m9 6 6 6-6 6" /></svg>;
    case "trash":
      return <svg {...common}><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-9 0 1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12" /></svg>;
    case "settings":
      return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>;
    default:
      return null;
  }
}

function WorkspaceBrandForm({ workspaceId }: { workspaceId: string }) {
  const [fields, setFields] = useState<Omit<BrandProfile, "workspace_id" | "updated_at">>({
    name: "", colors: "", tone: "", audience: "", visual_style: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    getBrandProfile(workspaceId)
      .then((p) => {
        if (cancelled) return;
        setFields({ name: p.name, colors: p.colors, tone: p.tone, audience: p.audience, visual_style: p.visual_style });
      })
      .catch(() => { /* treat a load failure the same as "nothing set yet" */ })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [workspaceId]);

  async function handleSave() {
    setSaving(true);
    try {
      await setBrandProfile(workspaceId, fields);
      setSavedAt(Date.now());
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Could not save brand profile");
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    if (!window.confirm("Clear this workspace's brand profile? Future generations here go back to unbranded.")) return;
    setSaving(true);
    try {
      await deleteBrandProfile(workspaceId);
      setFields({ name: "", colors: "", tone: "", audience: "", visual_style: "" });
      setSavedAt(Date.now());
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Could not clear brand profile");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="op-projects-empty">Loading brand profile…</div>;

  return (
    <div className="op-brand-form" onClick={(e) => e.stopPropagation()}>
      <input
        className="op-brand-input" placeholder="Brand / organization name"
        value={fields.name} onChange={(e) => setFields((f) => ({ ...f, name: e.target.value }))}
      />
      <input
        className="op-brand-input" placeholder="Colors (e.g. Blue and purple, modern)"
        value={fields.colors} onChange={(e) => setFields((f) => ({ ...f, colors: e.target.value }))}
      />
      <input
        className="op-brand-input" placeholder="Tone (e.g. Professional but approachable)"
        value={fields.tone} onChange={(e) => setFields((f) => ({ ...f, tone: e.target.value }))}
      />
      <input
        className="op-brand-input" placeholder="Usual audience (e.g. Enterprise investors)"
        value={fields.audience} onChange={(e) => setFields((f) => ({ ...f, audience: e.target.value }))}
      />
      <input
        className="op-brand-input" placeholder="Visual style (e.g. Minimal and clean)"
        value={fields.visual_style} onChange={(e) => setFields((f) => ({ ...f, visual_style: e.target.value }))}
      />
      <div className="op-brand-form-actions">
        <button className="op-pill-btn primary" style={{ padding: "5px 12px", fontSize: 12 }} onClick={handleSave} disabled={saving}>
          Save
        </button>
        <button className="op-pill-btn" style={{ padding: "5px 12px", fontSize: 12 }} onClick={handleClear} disabled={saving}>
          Clear
        </button>
        {savedAt && <span style={{ fontSize: 11.5, color: "var(--op-text-muted)" }}>Saved</span>}
      </div>
      <div className="op-composer-hint" style={{ padding: 0, marginTop: 6 }}>
        Applied to future generations in this workspace — informs tone, not a hard color/layout constraint.
      </div>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [signedIn, setSignedIn] = useState(false);
  const [recent, setRecent] = useState<ProjectSummary[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedProjects, setExpandedProjects] = useState<{ project_id: string; title: string }[] | null>(null);
  const [expandedLoading, setExpandedLoading] = useState(false);
  const [brandFormOpenId, setBrandFormOpenId] = useState<string | null>(null);

  useEffect(() => {
    setSignedIn(!!getSessionToken());
  }, []);

  const refreshWorkspaces = () => {
    listWorkspaces().then(setWorkspaces).catch(() => setWorkspaces([]));
  };

  useEffect(() => {
    if (!signedIn) return;
    listProjects()
      .then((projects) => setRecent(projects.slice(0, 5)))
      .catch(() => setRecent([]));
    refreshWorkspaces();
  }, [signedIn]);

  async function toggleWorkspace(workspaceId: string) {
    if (expandedId === workspaceId) {
      setExpandedId(null);
      setExpandedProjects(null);
      return;
    }
    setExpandedId(workspaceId);
    setExpandedProjects(null);
    setExpandedLoading(true);
    try {
      const detail = await getWorkspace(workspaceId);
      setExpandedProjects(detail.projects);
    } catch {
      setExpandedProjects([]);
    } finally {
      setExpandedLoading(false);
    }
  }

  async function handleCreateWorkspace() {
    // ADR-044 MVP: a plain prompt() rather than a styled modal — real,
    // functional, honest about being a first cut rather than dressing
    // up a text input as more polished than it is.
    const name = window.prompt("Name this workspace:");
    if (!name || !name.trim()) return;
    try {
      await createWorkspace(name.trim());
      refreshWorkspaces();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Could not create workspace");
    }
  }

  async function handleDeleteWorkspace(e: React.MouseEvent, workspaceId: string, name: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`Delete "${name}"? Its projects will stay, just ungrouped.`)) return;
    try {
      await deleteWorkspace(workspaceId);
      if (expandedId === workspaceId) {
        setExpandedId(null);
        setExpandedProjects(null);
      }
      refreshWorkspaces();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Could not delete workspace");
    }
  }

  return (
    <aside className="op-sidebar">
      <div className="op-sidebar-top">
        <Link href="/" className="op-brand">
          <Image src="/logo.png" alt="OpenPresent" width={28} height={28} className="op-brand-mark" />
          <span>OpenPresent</span>
        </Link>

        <Link href="/?new=1" className="op-new-btn">
          <Icon name="plus" />
          New presentation
        </Link>

        <nav className="op-nav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.comingSoon ? "#" : item.href}
              className={`op-nav-item ${pathname === item.href ? "active" : ""} ${item.comingSoon ? "disabled" : ""}`}
              onClick={(e) => item.comingSoon && e.preventDefault()}
              title={item.comingSoon ? "Coming soon in v3" : undefined}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.comingSoon && <span className="op-soon">soon</span>}
            </Link>
          ))}
        </nav>

        {signedIn && (
          <div className="op-projects">
            <div className="op-projects-label">Recent</div>
            {recent.length === 0 && <div className="op-projects-empty">No projects yet</div>}
            {recent.map((p) => (
              <Link key={p.project_id} href={`/projects/${p.project_id}`} className="op-project-item">
                {p.title || "Untitled presentation"}
              </Link>
            ))}
          </div>
        )}

        {signedIn && (
          <div className="op-projects">
            <div className="op-projects-label-row">
              <div className="op-projects-label">Workspaces</div>
              <button className="op-workspace-add-btn" onClick={handleCreateWorkspace} title="New workspace">
                <Icon name="plus" />
              </button>
            </div>
            {workspaces.length === 0 && <div className="op-projects-empty">No workspaces yet</div>}
            {workspaces.map((w) => (
              <div key={w.workspace_id}>
                <div className="op-workspace-row" onClick={() => toggleWorkspace(w.workspace_id)}>
                  <span style={{ transform: expandedId === w.workspace_id ? "rotate(90deg)" : "none", display: "flex" }}>
                    <Icon name="chevron" />
                  </span>
                  <Icon name="folder" />
                  <span className="op-workspace-name">{w.name}</span>
                  <button
                    className="op-workspace-delete-btn"
                    onClick={(e) => handleDeleteWorkspace(e, w.workspace_id, w.name)}
                    title="Delete workspace"
                  >
                    <Icon name="trash" />
                  </button>
                </div>
                {expandedId === w.workspace_id && (
                  <div className="op-workspace-projects">
                    {expandedLoading && <div className="op-projects-empty">Loading…</div>}
                    {!expandedLoading && expandedProjects?.length === 0 && (
                      <div className="op-projects-empty">Empty — generate into this workspace from the composer below</div>
                    )}
                    {expandedProjects?.map((p) => (
                      <Link key={p.project_id} href={`/projects/${p.project_id}`} className="op-project-item">
                        {p.title || "Untitled"}
                      </Link>
                    ))}
                    <button
                      className="op-brand-toggle-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setBrandFormOpenId(brandFormOpenId === w.workspace_id ? null : w.workspace_id);
                      }}
                    >
                      <Icon name="palette" />
                      {brandFormOpenId === w.workspace_id ? "Hide brand profile" : "Brand profile"}
                    </button>
                    {brandFormOpenId === w.workspace_id && <WorkspaceBrandForm workspaceId={w.workspace_id} />}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="op-sidebar-bottom">
        <Link href="/settings" className="op-nav-item disabled" title="Coming soon in v3" onClick={(e) => e.preventDefault()}>
          <Icon name="settings" />
          <span>Settings</span>
        </Link>
        {signedIn ? (
          <button
            className="op-account"
            onClick={() => {
              logout();
              setSignedIn(false);
              setRecent([]);
            }}
          >
            <span className="op-avatar">•</span>
            <span>Sign out</span>
          </button>
        ) : (
          <Link href="/login" className="op-account">
            <span className="op-avatar">•</span>
            <span>Log in</span>
          </Link>
        )}
      </div>
    </aside>
  );
}
