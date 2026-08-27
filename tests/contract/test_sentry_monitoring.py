from backend.monitoring.sentry_setup import capture_exception, add_breadcrumb, capture_message, init_sentry


def test_capture_exception_never_raises_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    capture_exception(RuntimeError("simulated"), tags={"stage": "test"})  # must not raise


def test_add_breadcrumb_never_raises_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    add_breadcrumb("test_category", "test message", data={"key": "value"})  # must not raise


def test_capture_message_never_raises_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    capture_message("test message")  # must not raise


def test_init_sentry_returns_false_without_dsn(monkeypatch):
    import backend.monitoring.sentry_setup as mod
    mod._initialized = False
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False
    mod._initialized = False  # reset for other tests


def test_capture_exception_always_logs_to_stdout_even_without_sentry(monkeypatch, caplog):
    """Regression test: without this, an AI pipeline failure was
    completely invisible whenever Sentry was unreachable/unconfigured
    — this is what actually lets a deployer diagnose a silent
    fallback-to-deterministic via Render's Logs tab alone."""
    import logging
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    with caplog.at_level(logging.ERROR, logger="openpresent"):
        capture_exception(RuntimeError("simulated Gemini 404"), tags={"stage": "ai_pipeline"})
    assert any("simulated Gemini 404" in record.message for record in caplog.records)
    assert any("stage=ai_pipeline" in record.message for record in caplog.records)


def test_add_breadcrumb_always_logs_to_stdout(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="openpresent"):
        add_breadcrumb("ai_pipeline", "strategy generated", data={"narrative_style": "Classic"})
    assert any("strategy generated" in record.message for record in caplog.records)
