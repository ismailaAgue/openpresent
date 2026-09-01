"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavBar from "@/components/NavBar";
import Sidebar from "@/components/Sidebar";

const SIDEBAR_KEY = "op_sidebar_open";
const MOBILE_QUERY = "(max-width: 860px)";

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
  const [isMobile, setIsMobile] = useState(false);

  // Persisted per-browser, not per-account — a closed sidebar should
  // stay closed across reloads/navigation within the studio shell,
  // the same way a collapsed panel would in any other app, rather
  // than resetting open every time the page remounts. On a phone-sized
  // screen with no stored preference yet (first visit), default to
  // closed — an always-open 260px+ drawer covering most of a phone's
  // width on first load is the opposite of a good first impression.
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const applyMobile = (mobile: boolean) => {
      setIsMobile(mobile);
      const stored = window.localStorage.getItem(SIDEBAR_KEY);
      if (stored !== null) {
        setSidebarOpen(stored !== "closed");
      } else if (mobile) {
        setSidebarOpen(false);
      }
    };
    applyMobile(mq.matches);
    mq.addEventListener("change", (e) => applyMobile(e.matches));
  }, []);

  function toggleSidebar() {
    setSidebarOpen((open) => {
      const next = !open;
      window.localStorage.setItem(SIDEBAR_KEY, next ? "open" : "closed");
      return next;
    });
  }

  // On mobile, the sidebar is a drawer over the content, not a
  // permanent column — navigating anywhere from it should close it
  // automatically, the same way any mobile nav drawer behaves,
  // instead of leaving it covering the page you just tapped through to.
  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (isStudioShell) {
    return (
      <div className="op-shell">
        {sidebarOpen ? (
          <>
            <Sidebar onClose={toggleSidebar} />
            {isMobile && <div className="op-shell-backdrop" onClick={toggleSidebar} />}
          </>
        ) : (
          // A slim strip that's part of the normal flex row, not a
          // floating overlay — the previous position:absolute button
          // sat on top of page content instead of making room for
          // itself, which is what "misplaced" meant in practice
          // (it could visually collide with whatever was underneath).
          // On mobile this same markup becomes a small fixed button
          // instead (see the .op-sidebar-collapsed media query) —
          // reserving 48px of a 375px-wide screen for a permanent
          // strip is a worse trade than it is on desktop.
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
