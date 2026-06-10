from src.domain.glossary import (
    audit_term_usage,
    extract_pronoun_examples,
    format_glossary_for_prompt,
    format_pronoun_examples,
    format_recent_summaries,
    format_relationships_shorthand,
    merge_character_context,
    merge_pronoun_examples,
    select_active_character_context,
    upsert_relationship,
    validate_glossary_data,
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


def test_validate_glossary_data_accepts_current_schema():
    data = {
        "terms": {"李明": "Lý Minh"},
        "source_language": "chinese",
        "entities": {"李明": {"translated_name": "Lý Minh", "role": "protagonist", "pronoun": "cậu"}},
        "edges": [["李明", "张伟", "friend", 1]],
        "chapter_summaries": {"1": "Summary"},
    }

    issues = validate_glossary_data(data)

    assert "edge 0 references unknown character '张伟'" in issues
    assert len(issues) == 1


def test_validate_glossary_data_accepts_legacy_name_vi():
    data = {
        "entities": {"李明": {"name_vi": "Lý Minh", "role": "protagonist", "pronoun": "cậu"}},
    }

    assert validate_glossary_data(data) == []


def test_validate_glossary_data_reports_bad_shapes():
    issues = validate_glossary_data({
        "terms": {"": ""},
        "entities": {"李明": {"translated_name": 123}},
        "edges": [["李明"]],
        "chapter_summaries": {"one": 1},
    })

    assert "terms contains an empty or non-string source term" in issues
    assert "term '' has an empty or non-string translation" in issues
    assert "entity '李明'.translated_name must be a string" in issues
    assert "edge 0 must be [from, to, relationship, since_chapter?]" in issues
    assert "chapter summary key 'one' must be a numeric string" in issues
    assert "chapter summary 'one' must be a string" in issues


def test_audit_term_usage_reports_missing_translation_and_source_leak():
    issues = audit_term_usage(
        {"李明": "Lý Minh", "张伟": "Trương Vĩ"},
        "李明 gặp 张伟.",
        "李明 gặp Trương Vĩ.",
    )

    assert issues == [
        {"term": "李明", "expected": "Lý Minh", "issue": "missing_translation"},
        {"term": "李明", "expected": "Lý Minh", "issue": "source_term_leaked"},
    ]


def test_format_recent_summaries_keeps_recent_order():
    summaries = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth"}
    result = format_recent_summaries(summaries, current_chapter=5, max_count=3)
    assert result == "Chapter 2: Second\n\nChapter 3: Third\n\nChapter 4: Fourth"


def test_select_active_character_context_includes_first_degree_neighbors():
    entities = {
        "李明": {"translated_name": "Lý Minh", "role": "protagonist"},
        "张伟": {"translated_name": "Trương Vĩ", "role": "supporting"},
        "王芳": {"translated_name": "Vương Phương", "role": "minor"},
    }
    edges = [["李明", "张伟", "friend", 1], ["王芳", "张伟", "sibling", 2]]

    active_entities, active_edges = select_active_character_context(entities, edges, "李明，走进房间。")

    assert set(active_entities) == {"李明", "张伟"}
    assert active_edges == [["李明", "张伟", "friend", 1]]


def test_merge_character_context_keeps_first_pronoun_and_dedupes_reverse_edges():
    data = {
        "entities": {"李明": {"translated_name": "Lý Minh", "role": "minor", "pronoun": "cậu"}},
        "edges": [["李明", "张伟", "friend", 1]],
    }

    result = merge_character_context(
        data,
        {"李明": {"translated_name": "Lý Minh", "role": "protagonist", "pronoun": "anh ấy"}},
        [["张伟", "李明", "rival"]],
        chapter=3,
    )

    assert result["entities"]["李明"]["role"] == "protagonist"
    assert result["entities"]["李明"]["translated_name"] == "Lý Minh"
    assert "name_vi" not in result["entities"]["李明"]
    assert result["entities"]["李明"]["pronoun"] == "cậu"
    assert result["edges"] == [["李明", "张伟", "friend", 1]]


def test_merge_character_context_migrates_legacy_name_vi():
    data = {
        "entities": {"李明": {"name_vi": "Lý Minh", "role": "minor", "pronoun": "cậu"}},
    }

    result = merge_character_context(data, {}, [], chapter=1)

    assert result["entities"]["李明"] == {
        "translated_name": "Lý Minh",
        "role": "minor",
        "pronoun": "cậu",
    }


def test_upsert_relationship_updates_reverse_pair():
    data = {"edges": [["李明", "张伟", "friend", 1]]}

    result = upsert_relationship(data, "张伟", "李明", "rival", since_chapter=5)

    assert result["edges"] == [["张伟", "李明", "rival", 5]]


def test_upsert_relationship_preserves_since_when_not_supplied():
    data = {"edges": [["李明", "张伟", "friend", 1]]}

    result = upsert_relationship(data, "李明", "张伟", "rival")

    assert result["edges"] == [["李明", "张伟", "rival", 1]]


def test_format_relationships_shorthand():
    entities = {
        "李明": {"translated_name": "Lý Minh", "role": "protagonist", "pronoun": "cậu"},
        "张伟": {"translated_name": "Trương Vĩ", "role": "supporting"},
    }
    edges = [["李明", "张伟", "friend", 1]]

    result = format_relationships_shorthand(entities, edges)

    assert "=== CHARACTERS ===" in result
    assert 'Lý Minh[protagonist, pronoun="cậu"]' in result
    assert "Lý Minh(friend)->Trương Vĩ" in result


def test_extract_pronoun_examples():
    translation = "Lý Minh bước vào phòng. Cậu nhìn xung quanh. Cậu thấy Trương Vĩ đang ngồi đó. Trương Vĩ mỉm cười với cậu."
    entities = {
        "李明": {"translated_name": "Lý Minh", "pronoun": "cậu"},
        "张伟": {"translated_name": "Trương Vĩ", "pronoun": "anh ấy"},
    }

    result = extract_pronoun_examples(translation, entities)

    assert "李明" in result
    assert any("cậu" in ex for ex in result["李明"])


def test_extract_pronoun_examples_no_pronoun():
    translation = "Lý Minh bước vào phòng."
    entities = {
        "李明": {"translated_name": "Lý Minh", "pronoun": ""},
    }

    result = extract_pronoun_examples(translation, entities)
    assert result == {}


def test_merge_pronoun_examples_deduplicates():
    existing = {"李明": ["Cậu bước vào phòng.", "Cậu nhìn xung quanh."]}
    new = {"李明": ["Cậu nhìn xung quanh.", "Cậu thấy vui."]}

    result = merge_pronoun_examples(existing, new)

    assert result["李明"] == ["Cậu bước vào phòng.", "Cậu nhìn xung quanh.", "Cậu thấy vui."]


def test_merge_pronoun_examples_keeps_recent():
    existing = {"李明": ["Ex1", "Ex2", "Ex3"]}
    new = {"李明": ["Ex4"]}

    result = merge_pronoun_examples(existing, new)

    assert len(result["李明"]) == 3
    assert result["李明"] == ["Ex2", "Ex3", "Ex4"]


def test_format_pronoun_examples():
    entities = {
        "李明": {"translated_name": "Lý Minh", "pronoun": "cậu"},
        "张伟": {"translated_name": "Trương Vĩ", "pronoun": "anh ấy"},
    }
    examples = {
        "李明": ["Cậu bước vào phòng.", "Cậu mỉm cười."],
    }

    result = format_pronoun_examples(entities, examples)

    assert "=== PRONOUN USAGE" in result
    assert 'Lý Minh → use "cậu"' in result
    assert "Cậu bước vào phòng." in result
    assert "Trương Vĩ" not in result  # No examples for this character


def test_format_pronoun_examples_empty():
    result = format_pronoun_examples({}, {})
    assert result == ""


def test_validate_glossary_data_pronoun_examples():
    data = {
        "pronoun_examples": {
            "李明": ["Cậu bước vào phòng.", "Cậu mỉm cười."],
        },
    }
    issues = validate_glossary_data(data)
    assert issues == []


def test_validate_glossary_data_bad_pronoun_examples():
    issues = validate_glossary_data({
        "pronoun_examples": {"": ["valid"]},
    })
    assert "pronoun_examples contains an empty or non-string character name" in issues

    issues = validate_glossary_data({
        "pronoun_examples": {"李明": "not a list"},
    })
    assert "pronoun_examples['李明'] must be a list" in issues
