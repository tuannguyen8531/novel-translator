"""
AI Call Logger — Logs every LLM invocation with full request/response details.

Two log files:
- logs/translation.log      — Summary log (1 line per call, compact)
- logs/translation_full.log — Full log (system_prompt, user_prompt, response)

Full log format per entry:
    ════════════════════════════════════════
    [2026-05-07 09:12:30] TRANSLATE (chunk 1/3)
    ════════════════════════════════════════
    --- SYSTEM PROMPT ---
    You are a professional translator...
    --- USER PROMPT ---
    Translate the following...
    --- RESPONSE ---
    Chương 389: ...
    --- META ---
    {"provider": "gemini", "chunk_length": 1500, ...}
    ════════════════════════════════════════
"""

import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "translation.log"
LOG_FULL_FILE = LOG_DIR / "translation_full.log"

SEPARATOR = "═" * 60


def log_ai_call(
    call_type: str,
    system_prompt: str = "",
    user_prompt: str = "",
    response: str = "",
    **kwargs,
):
    """
    Log an AI call to both summary and full log files.

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

    # --- Full log (detailed, human-readable) ---
    label = call_type.upper()
    # Add extra context to the label if available
    if "chunk_index" in kwargs:
        total = kwargs.get("total_chunks", "?")
        label += f" (chunk {kwargs['chunk_index'] + 1}/{total})"
    elif "chapter" in kwargs:
        label += f" (chapter {kwargs['chapter']})"

    meta_str = json.dumps(kwargs, ensure_ascii=False, indent=2) if kwargs else "{}"

    full_entry = f"""
{SEPARATOR}
[{timestamp}] {label}
{SEPARATOR}
--- SYSTEM PROMPT ---
{system_prompt}
--- USER PROMPT ---
{user_prompt}
--- RESPONSE ---
{response}
--- META ---
{meta_str}
{SEPARATOR}
"""
    with open(LOG_FULL_FILE, "a", encoding="utf-8") as f:
        f.write(full_entry)
