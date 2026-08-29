"""
Adapter registry — Codebase Handbook Section 4.

Business logic (engines/) asks the registry for "the current X adapter"
and never imports a specific adapter class directly. Swapping an
implementation is a config change here, never a change to engines/.

Phase 2 config: AI adapter is now config-selectable (OPENPRESENT_AI_ADAPTER
env var: "null" | "local_model"). Defaulting to "null" keeps local dev
free and fast unless someone deliberately opts into AI — consistent
with Constitution Principle 3 (AI is never a routine dependency).

ADR-018: all four persistence-backed ports (Queue, Storage, Auth,
Analytics) now auto-select a Postgres adapter when a DATABASE_URL
environment variable is present, falling back to SQLite otherwise.
Render automatically sets DATABASE_URL when a Postgres instance is
attached to a web service — this is what fixes real user data (accounts,
projects) disappearing on every redeploy, since SQLite files on
Render's free web service disk are not guaranteed to persist across
restarts, while a separate managed Postgres instance is.
"""

import os
import threading
from backend.adapters.ingestion.txt_adapter import TxtIngestionAdapter
from backend.adapters.ingestion.pdf_adapter import PdfIngestionAdapter
from backend.adapters.structure.rule_based import RuleBasedStructureAdapter
from backend.adapters.ai.null_adapter import NullAdapter
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.adapters.ai.gemini_adapter import GeminiAdapter
from backend.adapters.ai.groq_adapter import GroqAdapter
from backend.adapters.ai.openrouter_adapter import OpenRouterAdapter
from backend.adapters.ai.huggingface_adapter import HuggingFaceAdapter
from backend.adapters.ai.composite_adapter import CompositeAIAdapter
from backend.adapters.research.null_research import NullResearchAdapter
from backend.adapters.research.duckduckgo_research import DuckDuckGoResearchAdapter
from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter
from backend.adapters.research.tavily_research import TavilyResearchAdapter
from backend.adapters.research.brave_research import BraveSearchResearchAdapter
from backend.adapters.research.composite_research import CompositeResearchAdapter
from backend.adapters.design.rule_based import RuleBasedDesignAdapter
from backend.adapters.export.pptx_adapter import PptxExportAdapter
from backend.adapters.export.docx_notes_adapter import SpeakerNotesDocxExportAdapter
from backend.adapters.export.document_docx_adapter import DocumentDocxExportAdapter
from backend.adapters.export.document_pdf_adapter import DocumentPdfExportAdapter
from backend.adapters.quota.sqlite_adapter import SqliteQuotaAdapter
from backend.adapters.quota.postgres_quota import PostgresQuotaAdapter
from backend.adapters.workspace.sqlite_adapter import SqliteWorkspaceAdapter
from backend.adapters.workspace.postgres_workspace import PostgresWorkspaceAdapter
from backend.adapters.brand.sqlite_adapter import SqliteBrandAdapter
from backend.adapters.brand.postgres_brand import PostgresBrandAdapter
from backend.adapters.queue.sqlite_adapter import SqliteQueueAdapter
from backend.adapters.queue.postgres_queue import PostgresQueueAdapter
from backend.adapters.storage.sqlite_storage import SqliteStorageAdapter
from backend.adapters.storage.postgres_storage import PostgresStorageAdapter
from backend.adapters.auth.simple_auth import SimpleAuthAdapter
from backend.adapters.auth.postgres_auth import PostgresAuthAdapter
from backend.adapters.analytics.sqlite_analytics import SqliteAnalyticsAdapter
from backend.adapters.analytics.postgres_analytics import PostgresAnalyticsAdapter
from backend.adapters.media.null_media_adapter import NullMediaAdapter
from backend.adapters.media.multi_provider_router import MultiProviderMediaAdapter
from backend.adapters.media.unsplash_adapter import UnsplashProvider
from backend.adapters.media.pexels_adapter import PexelsProvider
from backend.adapters.media.pixabay_adapter import PixabayProvider
from backend.adapters.media.wikimedia_adapter import WikimediaProvider

_INGESTION_ADAPTERS = [TxtIngestionAdapter(), PdfIngestionAdapter()]
_STRUCTURE_ADAPTER = RuleBasedStructureAdapter()
_DESIGN_ADAPTER = RuleBasedDesignAdapter()
_EXPORT_ADAPTERS = {
    "pptx": PptxExportAdapter(),
    # ADR-041 (v3 Phase 3) — a real, standalone selectable format, not
    # just the notes_docx companion (which stays wired directly into
    # export_bundle.py, not this map, since it's never chosen on its own).
    "document_docx": DocumentDocxExportAdapter(),
    # ADR-055 — infographic_svg/diagram_svg/poster_svg (ADR-046/047/048)
    # removed; scope narrowed to pptx/docx/pdf. document_pdf renders
    # directly from the Recipe (no docx->pdf conversion step) and shares
    # document_docx's prose content-shaping, differing only in render.
    "document_pdf": DocumentPdfExportAdapter(),
}

_ai_adapter_instance = None
_queue_adapter_instance = None
_storage_adapter_instance = None
_auth_adapter_instance = None
_analytics_adapter_instance = None
_media_adapter_instance = None
_research_adapter_instance = None
_quota_adapter_instance = None
_workspace_adapter_instance = None
_brand_adapter_instance = None

# ADR-042: guards get_queue_adapter()'s lazy singleton init specifically.
# The plain "if X is None: X = ..." pattern every get_*_adapter() here
# uses is a classic non-atomic check-then-set race under real threading
# — normally harmless (production has exactly one long-lived worker
# thread created once at startup), but became a real, reproducible
# source of test flakiness once multiple worker threads could exist
# briefly at once (see the fix in api/main.py's _lifespan/_in_process_
# worker_loop for why that no longer happens either — this lock is
# belt-and-suspenders on top of that, not a replacement for it). Scoped
# to just the queue adapter, the one actually implicated by a real
# failure, rather than every getter in this file speculatively — the
# same race is structurally possible on the others too if a future
# caller ever creates adapters from more than one thread, worth
# revisiting then rather than guessing at the shape of that now.
_queue_adapter_lock = threading.Lock()
# ADR-043 — same lazy-singleton race the queue getter had (ADR-042),
# guarded from the start this time instead of discovered via a flaky
# test, since it's the same pattern with the same known failure mode.
_quota_adapter_lock = threading.Lock()
_workspace_adapter_lock = threading.Lock()
_brand_adapter_lock = threading.Lock()


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def get_ingestion_adapter(filename: str):
    ext = filename[filename.rfind("."):].lower() if "." in filename else ""
    for adapter in _INGESTION_ADAPTERS:
        if ext in adapter.supported_extensions():
            return adapter
    from backend.ports.ingestion import UnsupportedFileTypeError
    raise UnsupportedFileTypeError(f"No ingestion adapter supports '{ext}' files")


def get_structure_adapter():
    return _STRUCTURE_ADAPTER


def get_ai_adapter():
    """Config-driven selection, revised ADR-030 (multi-provider
    composite with cascading fallback):

    - OPENPRESENT_AI_ADAPTER=<local_model|gemini|groq|openrouter|
      huggingface|null> forces exactly that single provider — useful
      for testing/debugging one provider in isolation.
    - Left unset (the default) -> AUTO: every provider with credentials
      configured is wired into a CompositeAIAdapter, in priority order
      local_model (only if OPENPRESENT_AI_BASE_URL is explicitly set —
      never assumed present) -> gemini -> groq -> openrouter ->
      huggingface. A stage failing on one provider cascades to the
      next configured one before falling back to the fully
      deterministic path (spec Section 6: "changing inference backends
      should not require application rewrites" — this is what makes
      that concretely true operationally, not just architecturally).
    - No provider configured at all -> NullAdapter ($0, no dependency).

    Same instance is used for both AIPort (document-upload enhancement)
    and AIPipelinePort (topic-first generation) — see
    get_ai_pipeline_adapter() below.
    """
    global _ai_adapter_instance
    if _ai_adapter_instance is None:
        choice = os.environ.get("OPENPRESENT_AI_ADAPTER", "auto")

        if choice == "local_model":
            _ai_adapter_instance = _build_local_model_adapter()
        elif choice == "gemini":
            _ai_adapter_instance = GeminiAdapter(api_key=os.environ.get("GEMINI_API_KEY", ""))
        elif choice == "groq":
            _ai_adapter_instance = GroqAdapter(api_key=os.environ.get("GROQ_API_KEY", ""))
        elif choice == "openrouter":
            _ai_adapter_instance = OpenRouterAdapter(api_key=os.environ.get("OPENROUTER_API_KEY", ""))
        elif choice == "huggingface":
            _ai_adapter_instance = HuggingFaceAdapter(api_key=os.environ.get("HUGGINGFACE_API_KEY", ""))
        elif choice == "null":
            _ai_adapter_instance = NullAdapter()
        else:
            configured = []
            if os.environ.get("OPENPRESENT_AI_BASE_URL"):
                configured.append(_build_local_model_adapter())
            if os.environ.get("GEMINI_API_KEY"):
                configured.append(GeminiAdapter(api_key=os.environ["GEMINI_API_KEY"]))
            if os.environ.get("GROQ_API_KEY"):
                configured.append(GroqAdapter(api_key=os.environ["GROQ_API_KEY"]))
            if os.environ.get("OPENROUTER_API_KEY"):
                configured.append(OpenRouterAdapter(api_key=os.environ["OPENROUTER_API_KEY"]))
            if os.environ.get("HUGGINGFACE_API_KEY"):
                configured.append(HuggingFaceAdapter(api_key=os.environ["HUGGINGFACE_API_KEY"]))
            _ai_adapter_instance = CompositeAIAdapter(configured) if configured else NullAdapter()
    return _ai_adapter_instance


def _build_local_model_adapter():
    base_url = os.environ.get("OPENPRESENT_AI_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OPENPRESENT_AI_MODEL", "qwen2.5:3b")
    return LocalModelAdapter(base_url=base_url, model=model)


def get_ai_pipeline_adapter():
    """The AIPipelinePort view of whatever get_ai_adapter() resolved to
    (GeminiAdapter and LocalModelAdapter both implement it). NullAdapter
    doesn't — topic-first generation without any AI adapter configured
    falls back to the deterministic template
    (backend/pipeline/deterministic_topic_outline.py), handled by the
    engine, not by a Null implementation of this port, to keep
    NullAdapter itself a pure no-op/pass-through (see its docstring)."""
    adapter = get_ai_adapter()
    # Structural check rather than isinstance(adapter, AIPipelinePort):
    # Protocol isinstance checks require @runtime_checkable, which only
    # verifies method names exist anyway (not signatures) — this is
    # equally correct and doesn't require decorating the Protocol.
    if hasattr(adapter, "generate_strategy"):
        return adapter
    return _NullPipelineAdapter()


class _NullPipelineAdapter:
    """is_available() is always False — callers must fall back to the
    deterministic topic template. Exists only so engines/ai_generate.py
    always has a uniform object to call .is_available() on."""

    def is_available(self) -> bool:
        return False


def get_design_adapter():
    return _DESIGN_ADAPTER


def get_export_adapter(format_id: str):
    if format_id not in _EXPORT_ADAPTERS:
        from backend.ports.export import UnsupportedFormatError
        raise UnsupportedFormatError(f"No export adapter for format '{format_id}'")
    return _EXPORT_ADAPTERS[format_id]


def get_queue_adapter():
    global _queue_adapter_instance
    if _queue_adapter_instance is None:
        with _queue_adapter_lock:
            if _queue_adapter_instance is None:  # re-check: lost the race while acquiring the lock
                db_url = _database_url()
                if db_url:
                    _queue_adapter_instance = PostgresQueueAdapter(db_url)
                else:
                    db_path = os.environ.get("OPENPRESENT_QUEUE_DB", ":memory:")
                    _queue_adapter_instance = SqliteQueueAdapter(db_path)
    return _queue_adapter_instance


def get_storage_adapter():
    global _storage_adapter_instance
    if _storage_adapter_instance is None:
        db_url = _database_url()
        if db_url:
            _storage_adapter_instance = PostgresStorageAdapter(db_url)
        else:
            db_path = os.environ.get("OPENPRESENT_STORAGE_DB", ":memory:")
            _storage_adapter_instance = SqliteStorageAdapter(db_path)
    return _storage_adapter_instance


def get_auth_adapter():
    global _auth_adapter_instance
    if _auth_adapter_instance is None:
        db_url = _database_url()
        if db_url:
            _auth_adapter_instance = PostgresAuthAdapter(db_url)
        else:
            db_path = os.environ.get("OPENPRESENT_AUTH_DB", ":memory:")
            _auth_adapter_instance = SimpleAuthAdapter(db_path)
    return _auth_adapter_instance


def get_analytics_adapter():
    global _analytics_adapter_instance
    if _analytics_adapter_instance is None:
        db_url = _database_url()
        if db_url:
            _analytics_adapter_instance = PostgresAnalyticsAdapter(db_url)
        else:
            db_path = os.environ.get("OPENPRESENT_ANALYTICS_DB", ":memory:")
            _analytics_adapter_instance = SqliteAnalyticsAdapter(db_path)
    return _analytics_adapter_instance


def get_media_adapter():
    """ADR-030: multi-provider router. Every provider with a key set
    (or, for Wikimedia, always) is wired into MultiProviderMediaAdapter
    in priority order — Unsplash, Pexels, Pixabay, Wikimedia. Falls
    back to NullMediaAdapter ($0, no images) only if literally none of
    the keyed providers are configured (Wikimedia needs no key, so in
    practice at least one provider is always available — Wikimedia is
    the guaranteed universal fallback)."""
    global _media_adapter_instance
    if _media_adapter_instance is None:
        providers = []

        unsplash_key = os.environ.get("OPENPRESENT_UNSPLASH_ACCESS_KEY", "")
        if unsplash_key:
            providers.append(UnsplashProvider(access_key=unsplash_key))

        pexels_key = os.environ.get("OPENPRESENT_PEXELS_API_KEY", "")
        if pexels_key:
            providers.append(PexelsProvider(api_key=pexels_key))

        pixabay_key = os.environ.get("OPENPRESENT_PIXABAY_API_KEY", "")
        if pixabay_key:
            providers.append(PixabayProvider(api_key=pixabay_key))

        if os.environ.get("OPENPRESENT_DISABLE_WIKIMEDIA", "").lower() != "true":
            providers.append(WikimediaProvider())  # no key needed — always-on fallback

        if providers:
            _media_adapter_instance = MultiProviderMediaAdapter(providers=providers)
        else:
            _media_adapter_instance = NullMediaAdapter()
    return _media_adapter_instance


def get_research_adapter():
    """ADR-032: on by default now, not opt-in — CompositeResearchAdapter
    merges facts from every configured provider: Tavily (if
    TAVILY_API_KEY set — best quality, purpose-built for LLM grounding),
    Brave (if BRAVE_SEARCH_API_KEY set — live web index), and Wikipedia
    (always, no key needed — replaces the old DuckDuckGo-HTML-scraping
    default with a real, documented, stable API). DuckDuckGo scraping
    is no longer included by default (it was always explicitly
    best-effort) but remains available as an extra free source via
    OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH=true.

    Set OPENPRESENT_RESEARCH_ADAPTER=null to disable the Research stage
    entirely (matches every other capability's rollback pattern in this
    codebase — see DEPLOYMENT.md's rollback table)."""
    global _research_adapter_instance
    if _research_adapter_instance is None:
        choice = os.environ.get("OPENPRESENT_RESEARCH_ADAPTER", "auto")

        if choice == "null":
            _research_adapter_instance = NullResearchAdapter()
        elif choice == "duckduckgo":
            # Explicit single-provider override for testing/debugging —
            # bypasses the composite entirely, same escape hatch pattern
            # as OPENPRESENT_AI_ADAPTER.
            _research_adapter_instance = DuckDuckGoResearchAdapter()
        else:
            providers = []
            tavily_key = os.environ.get("TAVILY_API_KEY", "")
            if tavily_key:
                providers.append(TavilyResearchAdapter(api_key=tavily_key))

            brave_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
            if brave_key:
                providers.append(BraveSearchResearchAdapter(api_key=brave_key))

            providers.append(WikipediaResearchAdapter())  # always — no key needed

            if os.environ.get("OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH", "").lower() == "true":
                providers.append(DuckDuckGoResearchAdapter())

            _research_adapter_instance = CompositeResearchAdapter(providers)
    return _research_adapter_instance


def get_quota_adapter():
    """ADR-043 — cost circuit breaker. Same Postgres-if-DATABASE_URL-set,
    SQLite-otherwise pattern as get_queue_adapter(), including the
    double-checked-locking fix from ADR-042 applied from the start here."""
    global _quota_adapter_instance
    if _quota_adapter_instance is None:
        with _quota_adapter_lock:
            if _quota_adapter_instance is None:
                db_url = _database_url()
                if db_url:
                    _quota_adapter_instance = PostgresQuotaAdapter(db_url)
                else:
                    db_path = os.environ.get("OPENPRESENT_QUOTA_DB", ":memory:")
                    _quota_adapter_instance = SqliteQuotaAdapter(db_path)
    return _quota_adapter_instance


def get_workspace_adapter():
    """ADR-044 — Project Workspace. Same Postgres-if-DATABASE_URL-set,
    SQLite-otherwise pattern, with the double-checked-locking fix
    applied from the start (ADR-042/043 precedent)."""
    global _workspace_adapter_instance
    if _workspace_adapter_instance is None:
        with _workspace_adapter_lock:
            if _workspace_adapter_instance is None:
                db_url = _database_url()
                if db_url:
                    _workspace_adapter_instance = PostgresWorkspaceAdapter(db_url)
                else:
                    db_path = os.environ.get("OPENPRESENT_WORKSPACE_DB", ":memory:")
                    _workspace_adapter_instance = SqliteWorkspaceAdapter(db_path)
    return _workspace_adapter_instance


def get_brand_adapter():
    """ADR-045 — Brand Memory. Same Postgres-if-DATABASE_URL-set,
    SQLite-otherwise pattern, with the double-checked-locking fix
    applied from the start (ADR-042/043/044 precedent)."""
    global _brand_adapter_instance
    if _brand_adapter_instance is None:
        with _brand_adapter_lock:
            if _brand_adapter_instance is None:
                db_url = _database_url()
                if db_url:
                    _brand_adapter_instance = PostgresBrandAdapter(db_url)
                else:
                    db_path = os.environ.get("OPENPRESENT_BRAND_DB", ":memory:")
                    _brand_adapter_instance = SqliteBrandAdapter(db_path)
    return _brand_adapter_instance
