"""JSON parsing helpers."""

import json
import re
from typing import Any


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_THINK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _strip_thinking_blocks(text: str) -> str:
    return _THINK_RE.sub("", text)


def _repair_json(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", text.strip())


def _parse_candidate(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = json.loads(_repair_json(text))

    if isinstance(value, dict):
        return value
    raise ValueError("Expected a JSON object")


def _iter_balanced_objects(text: str):
    for start, char in enumerate(text):
        if char != "{":
            continue

        in_string = False
        escaped = False
        depth = 0
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue

            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : index + 1]
                    break


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from text that may contain extra LLM chatter."""
    stripped = _strip_thinking_blocks(text).strip()

    first_error: json.JSONDecodeError | None = None
    try:
        return _parse_candidate(stripped)
    except json.JSONDecodeError as e:
        first_error = e
        pass

    for match in _CODE_FENCE_RE.finditer(stripped):
        try:
            return _parse_candidate(match.group(1).strip())
        except json.JSONDecodeError as e:
            if first_error is None:
                first_error = e
            continue

    for candidate in _iter_balanced_objects(stripped):
        try:
            return _parse_candidate(candidate)
        except json.JSONDecodeError as e:
            if first_error is None:
                first_error = e
            continue

    if first_error is not None:
        raise first_error
    raise json.JSONDecodeError("No JSON object found", stripped, 0)
