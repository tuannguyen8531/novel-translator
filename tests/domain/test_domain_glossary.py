from src.domain.glossary import (
    audit_term_usage,
    format_address_rules,
    format_glossary_for_prompt,
    format_recent_summaries,
    format_relationships_shorthand,
    merge_character_context,
    normalize_address_rules,
    normalize_character_edges,
    normalize_glossary_data,
    select_active_address_rules,
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
        "address_rules": [{"speaker": "李明", "listener": "张伟", "self": "ta", "other": "ngươi", "since": 1}],
        "chapter_summaries": {"1": "Summary"},
    }

    issues = validate_glossary_data(data)

    assert "edge 0 references unknown character '张伟'" in issues
    assert "address rule 0 references unknown listener '张伟'" in issues
    assert len(issues) == 2


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
        "address_rules": [{"speaker": "李明", "listener": "", "self": 1, "since": "1"}],
        "chapter_summaries": {"one": 1},
    })

    assert "terms contains an empty or non-string source term" in issues
    assert "term '' has an empty or non-string translation" in issues
    assert "entity '李明'.translated_name must be a string" in issues
    assert "edge 0 must be [from, to, relationship, since_chapter?]" in issues
    assert "address rule 0 has an invalid listener" in issues
    assert "address rule 0.self must be a string" in issues
    assert "address rule 0.since must be an integer" in issues
    assert "chapter summary key 'one' must be a numeric string" in issues
    assert "chapter summary 'one' must be a string" in issues


def test_validate_glossary_data_reports_bad_character_aliases():
    issues = validate_glossary_data({
        "entities": {
            "李明": {"translated_name": "Lý Minh", "aliases": ["", 123]},
            "张伟": {"translated_name": "Trương Vĩ", "aliases": "伟"},
        },
    })

    assert "entity '李明'.aliases contains an empty or non-string alias" in issues
    assert "entity '张伟'.aliases must be a list" in issues


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
        "entities": {
            "李明": {"translated_name": "Lý Minh", "role": "minor", "pronoun": "cậu"},
            "张伟": {"translated_name": "Trương Vĩ", "role": "supporting", "pronoun": ""},
        },
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


def test_normalize_character_edges_resolves_translated_names_and_dedupes():
    entities = {
        "카일 윈프레드": {"translated_name": "Kyle Winfred"},
        "이사벨 유스티아": {"translated_name": "Isabelle Justia"},
    }
    edges = [
        ["카일 윈프레드", "이사벨 유스티아", "romantic interest", 1],
        ["Kyle Winfred", "Isabelle Justia", "ex", 13],
        ["Unknown", "Kyle Winfred", "friend", 13],
    ]

    assert normalize_character_edges(edges, entities) == [
        ["카일 윈프레드", "이사벨 유스티아", "romantic interest", 1],
    ]


def test_normalize_glossary_data_drops_pronoun_examples():
    data = {
        "entities": {"李明": {"name_vi": "Lý Minh", "role": "minor", "pronoun": "cậu"}},
        "edges": [["Lý Minh", "missing", "friend", 1]],
        "pronoun_examples": {"李明": ["Cậu bước vào phòng."]},
    }

    result = normalize_glossary_data(data)

    assert result["entities"]["李明"]["translated_name"] == "Lý Minh"
    assert result["edges"] == []
    assert result["address_rules"] == []
    assert "pronoun_examples" not in result


def test_normalize_address_rules_resolves_names_and_dedupes():
    entities = {
        "카일": {"translated_name": "Kyle"},
        "이사벨": {"translated_name": "Isabelle"},
    }
    rules = [
        {"speaker": "Kyle", "listener": "Isabelle", "self": "ta", "other": "nàng", "since": "3"},
        {"speaker": "카일", "listener": "이사벨", "self": "", "other": "em", "since": 3, "notes": "warmer later"},
        {"speaker": "Unknown", "listener": "Kyle", "self": "ta", "other": "ngươi", "since": 3},
    ]

    result = normalize_address_rules(rules, entities, chapter=2)

    assert result == [
        {
            "speaker": "카일",
            "listener": "이사벨",
            "self": "ta",
            "other": "em",
            "since": 3,
            "notes": "warmer later",
        }
    ]


def test_select_active_address_rules_filters_by_pair_and_chapter():
    active_entities = {
        "李明": {"translated_name": "Lý Minh"},
        "张伟": {"translated_name": "Trương Vĩ"},
    }
    rules = [
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 1, "until": 3},
        {"speaker": "张伟", "listener": "李明", "self": "tao", "other": "mày", "since": 5},
        {"speaker": "李明", "listener": "王芳", "self": "tôi", "other": "cô", "since": 1},
    ]

    assert select_active_address_rules(rules, active_entities, current_chapter=2) == [rules[0]]
    assert select_active_address_rules(rules, active_entities, current_chapter=5) == [rules[1]]


def test_normalize_address_rules_builds_non_overlapping_pair_timeline():
    entities = {
        "李明": {"translated_name": "Lý Minh"},
        "张伟": {"translated_name": "Trương Vĩ"},
    }
    rules = [
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 1},
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 2},
        {"speaker": "李明", "listener": "张伟", "self": "tao", "other": "mày", "since": 5},
    ]

    assert normalize_address_rules(rules, entities) == [
        {
            "speaker": "李明",
            "listener": "张伟",
            "self": "tôi",
            "other": "cậu",
            "since": 1,
            "until": 4,
        },
        {"speaker": "李明", "listener": "张伟", "self": "tao", "other": "mày", "since": 5},
    ]


def test_normalize_address_rules_drops_names_and_one_off_insults():
    entities = {
        "李明": {"translated_name": "Lý Minh"},
        "张伟": {"translated_name": "Trương Vĩ"},
        "王芳": {"translated_name": "Vương Phương"},
    }
    rules = [
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "Vĩ", "since": 1},
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "đồ ngốc", "since": 2},
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "Phương", "since": 3},
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 4},
    ]

    assert normalize_address_rules(rules, entities) == [
        {"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 4},
    ]


def test_normalize_address_rules_keeps_common_references_that_prefix_entity_names():
    entities = {
        "陆远秋": {"translated_name": "Lục Viễn Thu"},
        "白清夏": {"translated_name": "Bạch Thanh Hạ"},
        "强哥": {"translated_name": "anh Cường"},
        "梁先生": {"translated_name": "ông Lương"},
        "丽姐": {"translated_name": "chị Lệ"},
        "刘老师": {"translated_name": "Cô Lưu"},
        "白颂哲": {"translated_name": "Bác Bạch"},
        "陆城": {"translated_name": "Bác cả"},
    }
    rules = [
        {"speaker": "白清夏", "listener": "陆远秋", "self": "em", "other": "anh", "since": 1},
        {"speaker": "陆远秋", "listener": "梁先生", "self": "cháu", "other": "ông", "since": 2},
        {"speaker": "陆远秋", "listener": "丽姐", "self": "em", "other": "chị", "since": 3},
        {"speaker": "白清夏", "listener": "刘老师", "self": "em", "other": "cô", "since": 4},
        {"speaker": "陆远秋", "listener": "白颂哲", "self": "cháu", "other": "bác Bạch", "since": 5},
        {"speaker": "陆远秋", "listener": "陆城", "self": "con", "other": "bác cả", "since": 6},
    ]

    assert normalize_address_rules(rules, entities) == rules


def test_normalize_glossary_merges_clear_short_full_name_aliases():
    data = {
        "entities": {
            "아테나": {"translated_name": "Athena", "role": "minor", "pronoun": "cô ấy"},
            "아테나 바바라": {
                "translated_name": "Athena Barbara",
                "role": "supporting",
                "pronoun": "cô ấy",
            },
            "금태양": {"translated_name": "Kim Tae Yang", "role": "protagonist"},
        },
        "edges": [["아테나", "금태양", "friend", 1]],
        "address_rules": [
            {"speaker": "아테나", "listener": "금태양", "self": "em", "other": "anh", "since": 1},
        ],
    }

    result = normalize_glossary_data(data)

    assert "아테나" not in result["entities"]
    assert result["entities"]["아테나 바바라"]["aliases"] == ["아테나"]
    assert result["edges"] == [["아테나 바바라", "금태양", "friend", 1]]
    assert result["address_rules"][0]["speaker"] == "아테나 바바라"


def test_character_alias_activates_canonical_entity():
    entities = {
        "아테나 바바라": {
            "translated_name": "Athena Barbara",
            "aliases": ["아테나"],
        },
        "금태양": {"translated_name": "Kim Tae Yang"},
    }
    edges = [["아테나 바바라", "금태양", "friend", 1]]

    active_entities, _ = select_active_character_context(entities, edges, "아테나가 웃었다.")

    assert set(active_entities) == {"아테나 바바라", "금태양"}


def test_upsert_relationship_updates_reverse_pair():
    data = {"edges": [["李明", "张伟", "friend", 1]]}

    result = upsert_relationship(data, "张伟", "李明", "rival", since_chapter=5)

    assert result["edges"] == [["张伟", "李明", "rival", 5]]


def test_upsert_relationship_preserves_since_when_not_supplied():
    data = {
        "entities": {
            "李明": {"translated_name": "Lý Minh"},
            "张伟": {"translated_name": "Trương Vĩ"},
        },
        "edges": [["李明", "张伟", "friend", 1]],
    }

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


def test_format_address_rules():
    entities = {
        "李明": {"translated_name": "Lý Minh"},
        "张伟": {"translated_name": "Trương Vĩ"},
    }
    rules = [{"speaker": "李明", "listener": "张伟", "self": "tôi", "other": "cậu", "since": 2}]

    result = format_address_rules(entities, rules, target_language="vi")

    assert "=== ADDRESS RULES ===" in result
    assert 'Lý Minh -> Trương Vĩ: xưng hô; self="tôi", other="cậu", since chapter 2' in result


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
