import pytest

from app.core.runtime_config import RuntimeConfigurationError
from app.workers import email_outbox


def test_worker_fails_before_startup_when_runtime_configuration_is_invalid(
    monkeypatch,
):
    def reject_configuration():
        raise RuntimeConfigurationError("invalid test configuration")

    monkeypatch.setattr(
        email_outbox,
        "validate_email_worker_configuration",
        reject_configuration,
    )

    monkeypatch.setattr(
        email_outbox.EmailService,
        "validate_configuration",
        lambda: pytest.fail("SMTP validation must not run"),
    )

    monkeypatch.setattr(
        email_outbox,
        "EmailOutboxWorker",
        lambda: pytest.fail("Worker must not be initialized"),
    )

    with pytest.raises(RuntimeConfigurationError, match="invalid test"):
        email_outbox.main()


def test_worker_stops_cleanly_on_sigterm(monkeypatch):
    import signal as system_signal
    from types import SimpleNamespace

    registered_handlers = {}

    def register_handler(signum, handler):
        registered_handlers[signum] = handler

    fake_signal = SimpleNamespace(
        SIGTERM=system_signal.SIGTERM,
        signal=register_handler,
    )
    monkeypatch.setattr(
        email_outbox, "signal", fake_signal, raising=False
    )
    monkeypatch.setattr(
        email_outbox, "validate_email_worker_configuration", lambda: None
    )
    monkeypatch.setattr(
        email_outbox.EmailService, "validate_configuration", lambda: None
    )

    class FakeWorker:
        def __init__(self):
            self.calls = 0

        def process_one(self):
            self.calls += 1

            handler = registered_handlers.get(fake_signal.SIGTERM)
            if handler is None:
                raise AssertionError("SIGTERM handler was not registered")

            handler(fake_signal.SIGTERM, None)
            return True

    worker = FakeWorker()
    monkeypatch.setattr(
        email_outbox, "EmailOutboxWorker", lambda: worker
    )

    email_outbox.main()

    assert fake_signal.SIGTERM in registered_handlers
    assert worker.calls == 1
