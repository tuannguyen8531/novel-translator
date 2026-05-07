"""
AI Call Logger — Logs every LLM invocation with full request/response details.

Two log files:
- logs/translation.log      — Summary (1 line per call, compact JSON)
- logs/translation_api.log  — API-level JSON log (actual HTTP request/response)
"""

import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "translation.log"
LOG_API_FILE = LOG_DIR / "translation_api.log"

_verbose = False


def set_verbose(enabled: bool):
    """Enable/disable console output of AI calls."""
    global _verbose
    _verbose = enabled


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text for console display."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... ({len(text)} chars total)"


def log_api_request(
    call_type: str,
    provider: str,
    url: str,
    request_body: dict,
    response_body: dict,
    status_code: int,
    duration_ms: float,
    **kwargs,
):
    """Log the raw HTTP request/response to the API log file.

    Format: <timestamp> <json>  (same as translation.log)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    safe_body = _redact_secrets(request_body)
    safe_response = _redact_secrets(response_body)

    entry = {
        "type": call_type,
        "provider": provider,
        "url": url,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 1),
        "request": safe_body,
        "response": safe_response,
        **kwargs,
    }
    with open(LOG_API_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {json.dumps(entry, ensure_ascii=False)}\n")


def _redact_secrets(data: dict) -> dict:
    """Recursively redact API keys and sensitive fields."""
    redact_keys = {"key", "api_key", "authorization", "token", "secret"}
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        if k.lower() in redact_keys:
            result[k] = "***REDACTED***"
        elif isinstance(v, dict):
            result[k] = _redact_secrets(v)
        elif isinstance(v, list):
            result[k] = [_redact_secrets(item) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def log_ai_call(
    call_type: str,
    system_prompt: str = "",
    user_prompt: str = "",
    response: str = "",
    **kwargs,
):
    """
    Log an AI call to both summary and API log files.

    Args:
        call_type: Type of call (e.g., "translate", "review", "learn_terms", "learn_summary")
        system_prompt: The full system prompt sent to the LLM
        user_prompt: The full user prompt sent to the LLM
        response: The full response from the LLM
        **kwargs: Additional metadata fields to log
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Summary log (compact, 1 line per call) ---
    summary_entry = {
        "type": call_type,
        "system_prompt_len": len(system_prompt),
        "user_prompt_len": len(user_prompt),
        "response_len": len(response),
        **kwargs,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {json.dumps(summary_entry, ensure_ascii=False)}\n")

    # --- Console output (verbose mode only) ---
    if _verbose:
        label = call_type.upper()
        if "chunk_index" in kwargs:
            total = kwargs.get("total_chunks", "?")
            label += f" (chunk {kwargs['chunk_index'] + 1}/{total})"
        elif "chapter" in kwargs:
            label += f" (chapter {kwargs['chapter']})"

        print(f"\n{'═' * 60}")
        print(f"[{timestamp}] {label}")
        print(f"{'═' * 60}")
        print(f"--- SYSTEM ({len(system_prompt)} chars) ---")
        print(_truncate(system_prompt))
        print(f"--- USER ({len(user_prompt)} chars) ---")
        print(_truncate(user_prompt))
        print(f"--- RESPONSE ({len(response)} chars) ---")
        print(_truncate(response))
        print(f"{'═' * 60}\n")
