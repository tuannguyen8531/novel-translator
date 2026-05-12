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


def test_parse_json_object_rejects_arrays():
    with pytest.raises(ValueError):
        parse_json_object('[{"score": 0.8}]')


def test_parse_json_object_raises_when_missing():
    with pytest.raises(json.JSONDecodeError):
        parse_json_object("no json here")
