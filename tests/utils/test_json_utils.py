import json

import pytest

from src.utils.json import parse_json_object


def test_parse_json_object_accepts_plain_json():
    assert parse_json_object('{"score": 0.8}') == {"score": 0.8}


def test_parse_json_object_ignores_surrounding_text():
    assert parse_json_object('Here is the result:\n{"score": 0.8}\nDone.') == {"score": 0.8}


def test_parse_json_object_skips_invalid_brace_blocks():
    text = 'Example: {not json}\nActual:\n{"score": 0.8, "passed": true}'
    assert parse_json_object(text) == {"score": 0.8, "passed": True}


def test_parse_json_object_strips_thinking_blocks():
    text = '<think>{"wrong": true}</think>\n{"score": 0.8}'
    assert parse_json_object(text) == {"score": 0.8}


def test_parse_json_object_reads_markdown_json_fence():
    text = 'Result:\n```json\n{"score": 0.8}\n```'
    assert parse_json_object(text) == {"score": 0.8}


def test_parse_json_object_repairs_trailing_commas():
    assert parse_json_object('{"score": 0.8,}') == {"score": 0.8}


def test_parse_json_object_keeps_braces_inside_strings():
    text = 'Result: {"message": "brace { inside", "score": 1} Done.'
    assert parse_json_object(text) == {"message": "brace { inside", "score": 1}


def test_parse_json_object_rejects_arrays():
    with pytest.raises(ValueError):
        parse_json_object('[{"score": 0.8}]')


def test_parse_json_object_raises_when_missing():
    with pytest.raises(json.JSONDecodeError):
        parse_json_object("no json here")
