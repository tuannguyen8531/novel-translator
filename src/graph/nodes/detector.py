"""
Detector Node — Detect source language if not specified.

Uses Unicode heuristic first (fast, no LLM call).
Falls back to LLM detection only if heuristic returns "unknown".
"""

from src.models.state import TranslationState
from src.utils.text import detect_language_heuristic
from src.services.llm import llm
from src.services.logger import log_ai_call


def detector_node(state: TranslationState) -> dict:
    """Detect the source language of the text."""
    # If user already specified language, skip detection
    if state.get("source_language") and state["source_language"] != "":
        return {}

    text_sample = state["source_text"][:500]  # Sample first 500 chars
    detected = detect_language_heuristic(text_sample)

    if detected == "unknown":
        # Fallback to LLM detection
        sys_prompt = "You are a language detector. Respond with ONLY one word: chinese, korean, or japanese."
        usr_prompt = f"What language is this text written in?\n\n{text_sample}"
        response = llm.generate(system_prompt=sys_prompt, user_prompt=usr_prompt)
        detected = response.strip().lower()
        log_ai_call("detect_language", system_prompt=sys_prompt, user_prompt=usr_prompt, response=response, result=detected, method="llm")

        # Validate
        if detected not in ("chinese", "korean", "japanese"):
            detected = "chinese"  # Default fallback
    else:
        log_ai_call("detect_language", result=detected, method="heuristic")

    print(f"  📝 Detected language: {detected}")
    return {"source_language": detected}
