"""
Detector Node — Detect source language if not specified.

Uses Unicode heuristic first (fast, no LLM call).
Falls back to LLM detection only if heuristic returns "unknown".
Saves detected language to glossary immediately.
"""

from src.models.state import TranslationState
from src.domain.language import detect_language_heuristic
from src.services.llm import get_llm
from src.services.glossary import save_source_language
from src.services.logger import log_ai_call
from src.prompts import render_prompt


def detector_node(state: TranslationState) -> dict:
    """Detect the source language of the text."""
    if state.get("source_language") and state["source_language"] != "":
        return {}

    text_sample = state["source_text"][:500]
    detected = detect_language_heuristic(text_sample)

    if detected == "unknown":
        sys_prompt = render_prompt("detector")
        usr_prompt = f"What language is this text written in?\n\n{text_sample}"
        response = get_llm().generate(system_prompt=sys_prompt, user_prompt=usr_prompt, call_type="detect_language")
        detected = response.strip().lower()
        log_ai_call("detect_language", system_prompt=sys_prompt, user_prompt=usr_prompt, response=response, result=detected, method="llm")

        if detected not in ("chinese", "korean", "japanese"):
            detected = "chinese"
    else:
        log_ai_call("detect_language", result=detected, method="heuristic")

    save_source_language(state["novel_name"], detected)

    print(f"  📝 Language: {detected}")
    return {"source_language": detected}
