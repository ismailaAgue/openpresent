"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavBar from "@/components/NavBar";
import Sidebar from "@/components/Sidebar";

const SIDEBAR_KEY = "op_sidebar_open";

// The main product experience (chat + preview, Claude-style sidebar)
// lives at the site root now — it's the primary page, not a sub-route
// (moved here from /studio; that path now just redirects to /).
// ADR-057 — /dashboard, /settings, and /projects/[id] now keep the
// same sidebar shell too, rather than dropping into the old plain
// NavBar/page layout: navigating to any of them from inside the
// sidebar previously felt like being bounced out to a completely
// different, older-looking product, which was the actual "sends you
// to the old page" bug being reported. Only /login and /register keep
// the plain layout — a centered auth form doesn't need the sidebar,
// and there's no "recent projects" context to show before signing in.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStudioShell = pathname === "/" || pathname?.startsWith("/studio")
    || pathname === "/dashboard" || pathname === "/settings" || pathname?.startsWith("/projects/");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Persisted per-browser, not per-account — a closed sidebar should
  // stay closed across reloads/navigation within the studio shell,
  // the same way a collapsed panel would in any other app, rather
  // than resetting open every time the page remounts.
  useEffect(() => {
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    if (stored !== null) setSidebarOpen(stored !== "closed");
  }, []);

  function toggleSidebar() {
    setSidebarOpen((open) => {
      const next = !open;
      window.localStorage.setItem(SIDEBAR_KEY, next ? "open" : "closed");
      return next;
    });
  }

  if (isStudioShell) {
    return (
      <div className="op-shell">
        {sidebarOpen ? (
          <Sidebar onClose={toggleSidebar} />
        ) : (
          // A slim strip that's part of the normal flex row, not a
          // floating overlay — the previous position:absolute button
          // sat on top of page content instead of making room for
          // itself, which is what "misplaced" meant in practice
          // (it could visually collide with whatever was underneath).
          <div className="op-sidebar-collapsed">
            <button className="op-sidebar-open-btn" onClick={toggleSidebar} title="Open sidebar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="16" rx="2" />
                <path d="M9 4v16" />
              </svg>
            </button>
          </div>
        )}
        <div className="op-shell-content">{children}</div>
      </div>
    );
  }

  return (
    <>
      <NavBar />
      <main>{children}</main>
    </>
  );
}
