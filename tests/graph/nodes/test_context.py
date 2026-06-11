from unittest.mock import patch

from src.graph.nodes.context import context_node
from src.models.state import initial_state


def test_context_loads_target_specific_rules():
    state = initial_state(
        source_text="张三走了",
        source_language="chinese",
        target_language="en",
        novel_name="novel",
        chapter_number=1,
    )

    with (
        patch("src.graph.nodes.context.load_glossary", return_value={}),
        patch("src.graph.nodes.context.get_active_context", return_value=({}, [], [])),
    ):
        result = context_node(state)

    assert "# Common Translation Rules (All Languages -> English)" in result["translation_rules"]
    assert "# Chinese -> English" in result["translation_rules"]
    assert "All Languages → Vietnamese" not in result["translation_rules"]


def test_context_loads_vietnamese_rules_from_vi_folder():
    state = initial_state(
        source_text="张三走了",
        source_language="chinese",
        target_language="vi",
        novel_name="novel",
        chapter_number=1,
    )

    with (
        patch("src.graph.nodes.context.load_glossary", return_value={}),
        patch("src.graph.nodes.context.get_active_context", return_value=({}, [], [])),
    ):
        result = context_node(state)

    assert "# Common Translation Rules (All Languages → Vietnamese)" in result["translation_rules"]
    assert "# Chinese → Vietnamese" in result["translation_rules"]
