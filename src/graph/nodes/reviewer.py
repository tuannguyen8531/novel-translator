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
from src.services.llm import llm
from src.services.logger import log_ai_call
from src.config import config


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

    response = llm.generate(system_prompt, user_prompt)

    # Parse JSON response
    try:
        # Try to find JSON in the response (LLM might add extra text)
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            review_data = json.loads(response[json_start:json_end])
        else:
            review_data = json.loads(response)

        score = float(review_data.get("score", 0.8))
        feedback = review_data.get("feedback", "")
    except (json.JSONDecodeError, ValueError):
        # If parsing fails, assume decent quality to avoid infinite retries
        score = 0.8
        feedback = "Review parse failed — assuming acceptable quality"

    log_ai_call(
        "review",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=response,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        score=score,
        feedback=feedback,
    )

    print(f"  📊 Review score: {score:.2f}" + (f" — {feedback}" if feedback else ""))

    return {
        "review_score": score,
        "review_feedback": feedback,
    }
