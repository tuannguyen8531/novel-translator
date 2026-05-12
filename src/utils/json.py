"""JSON parsing helpers."""

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from text that may contain extra LLM chatter."""
    decoder = json.JSONDecoder()
    stripped = text.strip()

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(value, dict):
            return value
        raise ValueError("Expected a JSON object")

    first_error: json.JSONDecodeError | None = None
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError as e:
            if first_error is None:
                first_error = e
            continue
        if isinstance(value, dict):
            return value
        raise ValueError("Expected a JSON object")

    if first_error is not None:
        raise first_error
    raise json.JSONDecodeError("No JSON object found", text, 0)
