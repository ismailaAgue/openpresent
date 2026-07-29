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
from backend.adapters.ingestion.txt_adapter import TxtIngestionAdapter
from backend.adapters.ingestion.pdf_adapter import PdfIngestionAdapter
from backend.adapters.structure.rule_based import RuleBasedStructureAdapter
from backend.adapters.ai.null_adapter import NullAdapter
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.adapters.design.rule_based import RuleBasedDesignAdapter
from backend.adapters.export.pptx_adapter import PptxExportAdapter
from backend.adapters.queue.sqlite_adapter import SqliteQueueAdapter
from backend.adapters.queue.postgres_queue import PostgresQueueAdapter
from backend.adapters.storage.sqlite_storage import SqliteStorageAdapter
from backend.adapters.storage.postgres_storage import PostgresStorageAdapter
from backend.adapters.auth.simple_auth import SimpleAuthAdapter
from backend.adapters.auth.postgres_auth import PostgresAuthAdapter
from backend.adapters.analytics.sqlite_analytics import SqliteAnalyticsAdapter
from backend.adapters.analytics.postgres_analytics import PostgresAnalyticsAdapter

_INGESTION_ADAPTERS = [TxtIngestionAdapter(), PdfIngestionAdapter()]
_STRUCTURE_ADAPTER = RuleBasedStructureAdapter()
_DESIGN_ADAPTER = RuleBasedDesignAdapter()
_EXPORT_ADAPTERS = {"pptx": PptxExportAdapter()}

_ai_adapter_instance = None
_queue_adapter_instance = None
_storage_adapter_instance = None
_auth_adapter_instance = None
_analytics_adapter_instance = None


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
    """Config-driven selection. Defaults to NullAdapter ($0 cost, no
    dependency) unless OPENPRESENT_AI_ADAPTER=local_model is explicitly set."""
    global _ai_adapter_instance
    if _ai_adapter_instance is None:
        choice = os.environ.get("OPENPRESENT_AI_ADAPTER", "null")
        if choice == "local_model":
            base_url = os.environ.get("OPENPRESENT_AI_BASE_URL", "http://localhost:11434")
            model = os.environ.get("OPENPRESENT_AI_MODEL", "qwen2.5:3b")
            _ai_adapter_instance = LocalModelAdapter(base_url=base_url, model=model)
        else:
            _ai_adapter_instance = NullAdapter()
    return _ai_adapter_instance


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
