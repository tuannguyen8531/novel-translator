"""
Reviewer Node — Evaluate translation quality and decide whether to retry.

Scoring criteria:
- Completeness: all content from source is present
- Naturalness: reads naturally in Vietnamese
- Consistency: follows glossary terms
- Accuracy: meaning preserved correctly
"""

import json

from src.models.state import TranslationState
from src.services.llm import get_llm
from src.services.logger import log_ai_call
from src.config import config
from src.utils.json import parse_json_object
from src.domain.quality import has_blocking_issues, post_check_translation


def reviewer_node(state: TranslationState) -> dict:
    """Review the current translation and score it."""
    chunk_index = state["current_chunk_index"]
    chunk = state["chunks"][chunk_index]
    translation = state["current_translation"]
    total_chunks = len(state["chunks"])

    system_prompt = """You are a professional translation editor.
Evaluate the translation below on 4 criteria (each 0.0-1.0):
1. completeness: All original content is translated, nothing missing
2. naturalness: The translation reads naturally in Vietnamese
3. consistency: Terminology is translated consistently
4. accuracy: Meaning is preserved accurately

Respond with JSON ONLY (no other text):
{
    "score": 0.0-1.0,
    "feedback": "Brief feedback on what needs improvement",
    "completeness": 0.0-1.0,
    "naturalness": 0.0-1.0,
    "consistency": 0.0-1.0,
    "accuracy": 0.0-1.0
}"""

    user_prompt = f"""=== SOURCE TEXT ===
{chunk}

=== TRANSLATION ===
{translation}"""

    response = get_llm().generate(system_prompt, user_prompt, "review")

    # Parse JSON response
    try:
        review_data = parse_json_object(response)
        score = float(review_data.get("score", 0.8))
        feedback = review_data.get("feedback", "")
    except (json.JSONDecodeError, ValueError) as e:
        score = config.review_threshold - 0.1
        feedback = f"Review JSON parse failed — forcing retry. Raw: {response[:200]}"
        log_ai_call(
            "review_parse_error",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=response,
            error=str(e),
            chunk_index=chunk_index,
            total_chunks=total_chunks,
        )

    post_issues = post_check_translation(chunk, translation, state.get("glossary", {}))
    if post_issues:
        issue_feedback = "Post-check issues: " + "; ".join(issue.message for issue in post_issues)
        feedback = f"{feedback}\n{issue_feedback}" if feedback else issue_feedback
        if has_blocking_issues(post_issues):
            score = min(score, config.review_threshold - 0.1)

    log_ai_call(
        "review",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=response,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        score=score,
        feedback=feedback,
        post_check_issues=[issue.code for issue in post_issues],
    )

    return {
        "review_score": score,
        "review_feedback": feedback,
        "post_check_issues": [issue.code for issue in post_issues],
    }
