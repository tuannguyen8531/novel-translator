"""Tests for API logging format."""

import json
from pathlib import Path

from src.services import logger as logger_module


def test_log_api_request_writes_separate_request_and_response_records(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(logger_module, "LOG_DIR", log_dir)
    monkeypatch.setattr(logger_module, "LOG_API_FILE", log_dir / "translation_api.log")
    monkeypatch.setattr(logger_module, "_redact_secrets", lambda data: data)
    monkeypatch.setattr(logger_module, "datetime", type("DummyDateTime", (), {"now": staticmethod(lambda: type("DummyNow", (), {"strftime": staticmethod(lambda _fmt: "2026-05-07 15:00:00")})())}))
    monkeypatch.setattr(logger_module, "uuid4", type("DummyUUID4", (), {"hex": "abc123"}))

    call_id = logger_module.log_api_request_sent(
        call_type="translate",
        provider="gemini",
        url="https://example.test/api",
        request_body={"foo": "bar"},
        chunk_index=0,
    )

    logger_module.log_api_request_received(
        call_id=call_id,
        call_type="translate",
        provider="gemini",
        url="https://example.test/api",
        response_body={"ok": True},
        status_code=200,
        duration_ms=12.34,
        chunk_index=0,
    )

    lines = (log_dir / "translation_api.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0].split(" ", 2)[2])
    second = json.loads(lines[1].split(" ", 2)[2])

    assert first["type"] == "request"
    assert second["type"] == "response"
    assert first["provider"] == "gemini"
    assert second["provider"] == "gemini"
    assert first["call_type"] == "translate"
    assert second["call_type"] == "translate"
    assert first["call_id"] == "abc123"
    assert second["call_id"] == "abc123"
    assert first["request"] == {"foo": "bar"}
    assert second["response"] == {"ok": True}
    assert "response" not in first
    assert "request" not in second
