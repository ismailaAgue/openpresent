"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getSessionToken, listProjects, logout, ProjectSummary } from "@/lib/api-client";

const NAV_ITEMS = [
  { href: "/studio", label: "Home", icon: "home" },
  { href: "/dashboard", label: "Recent presentations", icon: "clock" },
  { href: "/studio/templates", label: "Templates", icon: "grid", comingSoon: true },
  { href: "/studio/brand", label: "Brand kits", icon: "palette", comingSoon: true },
  { href: "/studio/assets", label: "Assets", icon: "image", comingSoon: true },
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
    case "settings":
      return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>;
    default:
      return null;
  }
}

export default function Sidebar() {
  const pathname = usePathname();
  const [signedIn, setSignedIn] = useState(false);
  const [recent, setRecent] = useState<ProjectSummary[]>([]);

  useEffect(() => {
    setSignedIn(!!getSessionToken());
  }, []);

  useEffect(() => {
    if (!signedIn) return;
    listProjects()
      .then((projects) => setRecent(projects.slice(0, 5)))
      .catch(() => setRecent([]));
  }, [signedIn]);

  return (
    <aside className="op-sidebar">
      <div className="op-sidebar-top">
        <Link href="/studio" className="op-brand">
          <Image src="/logo.png" alt="OpenPresent" width={28} height={28} className="op-brand-mark" />
          <span>OpenPresent</span>
        </Link>

        <Link href="/studio?new=1" className="op-new-btn">
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
      </div>

      <div className="op-sidebar-bottom">
        <Link href="/studio/settings" className="op-nav-item disabled" title="Coming soon in v3" onClick={(e) => e.preventDefault()}>
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
