"""
Structured monitoring — ADR-030/031, spec Section 16 ("Monitoring
should remain independent of business logic").

Built on the `sentry_sdk` Python package (see requirements.txt), which
speaks the standard Sentry event-ingestion protocol — it works
unmodified against ANY protocol-compatible backend, not only Sentry's
own SaaS: self-hosted or hosted Sentry, GlitchTip, or Bugsink (what
this deployment actually uses, chosen for its higher hosted event
quota and lighter self-host footprint — ADR-031 addendum). Switching
between any of them is a SENTRY_DSN value change, never a code change.
`SENTRY_TRACES_SAMPLE_RATE` should be set to 0 for Bugsink specifically
— it doesn't process performance-tracing data, so there's no reason to
generate and send it.

Every function here is a no-op when either the package isn't installed
or SENTRY_DSN isn't configured, so a deployment with no error-tracking
backend set up behaves exactly as before this module existed. This IS
the "independent of business logic" requirement in code: nothing in
engines/, adapters/, or api/ needs to know or care whether monitoring
is actually active, or which backend is receiving it — they call
capture_exception/add_breadcrumb unconditionally, same as they'd log
to nowhere.

Wired in at the boundaries the spec explicitly lists (Section 16):
AI provider failures, image provider failures, rendering failures,
export failures, retry frequency, and any other unexpected exception —
see the call sites in backend/engines/ai_generate.py,
backend/engines/generate.py, backend/workers/generation_worker.py,
and backend/api/main.py's global exception handler.

ALWAYS logs to stdout too (via the standard `logging` module),
regardless of whether a backend is configured or reachable — this is
what actually let a real production bug get diagnosed when the
originally-configured Sentry SaaS became unreachable from the
deployer's network; Render's own Logs tab needs no external service at
all.
"""


import os
import logging
import traceback

logger = logging.getLogger("openpresent")
if not logger.handlers:
    _handler = logging.StreamHandler()  # stdout — Render's Logs tab captures this
    # regardless of Sentry reachability, which is the whole point: Sentry can be
    # unreachable (blocked network, region, whatever) and diagnosis must still work.
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

try:
    import sentry_sdk
    _SENTRY_SDK_INSTALLED = True
except ImportError:
    _SENTRY_SDK_INSTALLED = False

_initialized = False


def init_sentry() -> bool:
    """Call once at process startup (API and worker both call this).
    Returns True if Sentry is actually active, False if it's a no-op
    (package missing or DSN unset) — callers can use this for a
    /health field, but nothing depends on the return value."""
    global _initialized
    if _initialized:
        return _SENTRY_SDK_INSTALLED and bool(os.environ.get("SENTRY_DSN"))

    dsn = os.environ.get("SENTRY_DSN", "")
    if _SENTRY_SDK_INSTALLED and dsn:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.environ.get("OPENPRESENT_ENV", "production"),
        )
    _initialized = True
    return _SENTRY_SDK_INSTALLED and bool(dsn)


def capture_exception(exc: Exception, tags: dict | None = None) -> None:
    """Never raises, regardless of Sentry's own state — a monitoring
    failure must never become a generation failure. ALWAYS logs to
    stdout (visible in Render's Logs tab with zero setup, zero network
    dependency) — Sentry, when configured and reachable, is additive
    on top of that, never a replacement for it."""
    tag_str = " ".join(f"{k}={v}" for k, v in (tags or {}).items())
    logger.error("EXCEPTION [%s] %s: %s\n%s", tag_str, type(exc).__name__, exc,
                 "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    try:
        if _SENTRY_SDK_INSTALLED and os.environ.get("SENTRY_DSN"):
            with sentry_sdk.push_scope() as scope:
                for k, v in (tags or {}).items():
                    scope.set_tag(k, v)
                sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def add_breadcrumb(category: str, message: str, data: dict | None = None) -> None:
    """Structured breadcrumbs (spec: 'retry frequency, unexpected
    exceptions') — pipeline-stage-level trail so a Sentry error report
    shows exactly which stages succeeded before the one that failed,
    not just a bare stack trace. Also always logged to stdout (INFO
    level) for the same reason as capture_exception above."""
    logger.info("[%s] %s %s", category, message, data or {})
    try:
        if _SENTRY_SDK_INSTALLED and os.environ.get("SENTRY_DSN"):
            sentry_sdk.add_breadcrumb(category=category, message=message, data=data or {})
    except Exception:
        pass


def capture_message(message: str, level: str = "info", tags: dict | None = None) -> None:
    tag_str = " ".join(f"{k}={v}" for k, v in (tags or {}).items())
    getattr(logger, level if hasattr(logger, level) else "info")("[%s] %s", tag_str, message)
    try:
        if _SENTRY_SDK_INSTALLED and os.environ.get("SENTRY_DSN"):
            with sentry_sdk.push_scope() as scope:
                for k, v in (tags or {}).items():
                    scope.set_tag(k, v)
                sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass


def is_active() -> bool:
    """For /health — reports whether Sentry is actually capturing,
    without re-running init logic."""
    return _SENTRY_SDK_INSTALLED and bool(os.environ.get("SENTRY_DSN"))
