"use client";

import { usePathname } from "next/navigation";
import NavBar from "@/components/NavBar";
import Sidebar from "@/components/Sidebar";

// The main product experience (chat + preview, Claude-style sidebar)
// lives at the site root now — it's the primary page, not a sub-route
// (moved here from /studio; that path now just redirects to /). Every
// other route (/login, /register, /dashboard, /projects/[id]) keeps
// the original NavBar/page layout, untouched by this move.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStudioShell = pathname === "/" || pathname?.startsWith("/studio");

  if (isStudioShell) {
    return (
      <div className="op-shell">
        <Sidebar />
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
