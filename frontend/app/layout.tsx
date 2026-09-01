import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "OpenPresent — Presentations, without the paywall",
  description: "Turn your notes into a real presentation. Free, always, for students. No credit limits, ever.",
};

// ADR-058 — this was missing entirely. Without it, mobile browsers
// render the page at a virtual ~980px desktop viewport and scale the
// whole thing down to fit, which is what actually produced "tiny,
// overlapping text" — every element WAS laid out correctly, just at
// desktop proportions squeezed into a phone screen. This single tag
// is what makes the media queries below have any effect at all.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
