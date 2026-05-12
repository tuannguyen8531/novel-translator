from src.domain.glossary import (
    format_glossary_for_prompt,
    format_recent_summaries,
    format_relationships_shorthand,
    merge_character_context,
    select_active_character_context,
)


def test_format_glossary_for_prompt():
    terms = {"李白": "Lý Bạch", "杜甫": "Đỗ Phủ"}
    result = format_glossary_for_prompt(terms)
    assert "GLOSSARY" in result
    assert "李白 → Lý Bạch" in result
    assert "杜甫 → Đỗ Phủ" in result
    assert "END GLOSSARY" in result


def test_format_empty_glossary():
    assert format_glossary_for_prompt({}) == ""


def test_format_recent_summaries_keeps_recent_order():
    summaries = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth"}
    result = format_recent_summaries(summaries, current_chapter=5, max_count=3)
    assert result == "Chapter 2: Second\n\nChapter 3: Third\n\nChapter 4: Fourth"


def test_select_active_character_context_includes_first_degree_neighbors():
    entities = {
        "李明": {"name_vi": "Lý Minh", "role": "protagonist"},
        "张伟": {"name_vi": "Trương Vĩ", "role": "supporting"},
        "王芳": {"name_vi": "Vương Phương", "role": "minor"},
    }
    edges = [["李明", "张伟", "friend", 1], ["王芳", "张伟", "sibling", 2]]

    active_entities, active_edges = select_active_character_context(entities, edges, "李明，走进房间。")

    assert set(active_entities) == {"李明", "张伟"}
    assert active_edges == [["李明", "张伟", "friend", 1]]


def test_merge_character_context_keeps_first_pronoun_and_dedupes_reverse_edges():
    data = {
        "entities": {"李明": {"name_vi": "Lý Minh", "role": "minor", "pronoun": "cậu"}},
        "edges": [["李明", "张伟", "friend", 1]],
    }

    result = merge_character_context(
        data,
        {"李明": {"name_vi": "Lý Minh", "role": "protagonist", "pronoun": "anh ấy"}},
        [["张伟", "李明", "rival"]],
        chapter=3,
    )

    assert result["entities"]["李明"]["role"] == "protagonist"
    assert result["entities"]["李明"]["pronoun"] == "cậu"
    assert result["edges"] == [["李明", "张伟", "friend", 1]]


def test_format_relationships_shorthand():
    entities = {
        "李明": {"name_vi": "Lý Minh", "role": "protagonist", "pronoun": "cậu"},
        "张伟": {"name_vi": "Trương Vĩ", "role": "supporting"},
    }
    edges = [["李明", "张伟", "friend", 1]]

    result = format_relationships_shorthand(entities, edges)

    assert "=== CHARACTERS ===" in result
    assert 'Lý Minh[protagonist, pronoun="cậu"]' in result
    assert "Lý Minh(friend)->Trương Vĩ" in result
