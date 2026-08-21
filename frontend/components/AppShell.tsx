"use client";

import { usePathname } from "next/navigation";
import NavBar from "@/components/NavBar";
import Sidebar from "@/components/Sidebar";

// The v3 "studio" experience (chat + preview, Claude-style sidebar) owns
// its own full-height layout. Every other route keeps the original v2
// NavBar/page layout untouched, so nothing existing breaks while v3 is
// built out incrementally.
export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStudio = pathname?.startsWith("/studio");

  if (isStudio) {
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
