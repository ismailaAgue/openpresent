"use client";

import { useEffect, useState } from "react";

// Single source of truth for "is this viewport mobile" for the studio
// page's preview-panel default (see ADR-069). AppShell's sidebar keeps
// its own inline copy of this same breakpoint rather than switching to
// this hook — its mobile-detection effect applies the sidebar's default
// synchronously, within the same effect call that reads matchMedia, to
// avoid a one-render-late gap; wiring it through a separate hook plus a
// second effect keyed on the hook's return value would reintroduce
// exactly that gap in code that's already been through two rounds of
// real mobile bugs (ADR-058, ADR-063). A stated, deliberate duplication
// of one breakpoint constant, not an oversight — worth reconciling
// later if AppShell's sidebar logic ever gets rewritten anyway, not
// worth the risk of forcing it now for this fix.
export const MOBILE_QUERY = "(max-width: 860px)";

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return isMobile;
}
