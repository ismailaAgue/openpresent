"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavBar from "@/components/NavBar";
import Sidebar from "@/components/Sidebar";

const SIDEBAR_KEY = "op_sidebar_open";

// The main product experience (chat + preview, Claude-style sidebar)
// lives at the site root now — it's the primary page, not a sub-route
// (moved here from /studio; that path now just redirects to /). Every
// other route (/login, /register, /dashboard, /projects/[id]) keeps
// the original NavBar/page layout, untouched by this move.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStudioShell = pathname === "/" || pathname?.startsWith("/studio");
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
        {sidebarOpen && <Sidebar onClose={toggleSidebar} />}
        {!sidebarOpen && (
          <button className="op-sidebar-open-btn" onClick={toggleSidebar} title="Open sidebar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M9 4v16" />
            </svg>
          </button>
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
