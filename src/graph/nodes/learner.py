"""
Learner Node — Extract glossary terms and create chapter summary.

Runs after all chunks are translated. Responsible for:
1. Extracting new terms (character names, place names, special terms)
2. Creating a chapter summary for cross-chapter context
3. Saving both to the glossary JSON file
"""

from src.models.state import TranslationState
from src.services.llm import get_llm
from src.services.glossary import save_glossary, save_chapter_summary, save_source_language, save_characters_batch, save_pronoun_examples
from src.services.logger import log_ai_call, log_error
from src.config import config
from src.domain.terms import MIN_TERM_FREQUENCY, filter_terms_by_frequency
from src.domain.glossary import extract_pronoun_examples, get_character_translated_name
from src.utils.json import parse_json_object
from src.prompts import render_prompt
from src.domain.target_language import target_language_name

KINSHIP_TERMS = {
    # English
    "papa", "mama", "dad", "mom", "father", "mother", "uncle", "aunt",
    "grandpa", "grandma", "grandfather", "grandmother", "brother", "sister",
    "son", "daughter", "child", "children", "husband", "wife", "spouse",
    "boyfriend", "girlfriend", "fiance", "fiancee",
    # Chinese
    "爸爸", "妈妈", "父亲", "母亲", "爹", "娘", "爸", "妈",
    "叔叔", "阿姨", "爷爷", "奶奶", "外公", "外婆", "祖父", "祖母",
    "哥哥", "姐姐", "弟弟", "妹妹", "大哥", "大姐", "小弟", "小妹",
    "儿子", "女儿", "孩子", "丈夫", "妻子", "老公", "老婆",
    # Korean
    "아빠", "엄마", "아버지", "어머니", "할아버지", "할머니",
    "형", "오빠", "누나", "언니", "남동생", "여동생",
    "아들", "딸", "남편", "아내",
    # Japanese
    "お父さん", "お母さん", "父", "母", "パパ", "ママ",
    "おじいさん", "おばあさん", "兄", "姉", "弟", "妹",
    "息子", "娘", "夫", "妻", "旦那", "家内",
    # Generic role descriptors (not proper names)
    "teacher", "student", "master", "servant", "guard", "doctor", "nurse",
    "driver", "cook", "chef", "maid", "butler", "soldier", "general",
    "king", "queen", "prince", "princess", "lord", "lady",
    "先生", "学生", "老师", "师傅", "徒弟", "仆人", "护卫", "医生",
    "护士", "司机", "厨师", "士兵", "将军", "国王", "女王", "王子", "公主",
    "선생님", "학생", "의사", "간호사", "왕", "여왕", "왕자", "공주",
    "先生", "生徒", "医者", "看護師", "王様", "女王", "王子", "王女",
}


ALLOWED_RELATIONSHIP_TYPES = {
    "mother", "father", "parent", "son", "daughter", "child",
    "sibling", "brother", "sister", "half-sibling", "half-brother", "half-sister",
    "husband", "wife", "spouse", "romantic interest", "crush", "ex", "ex-partner",
    "friend", "enemy", "rival", "ally",
    "master", "disciple", "teacher", "student", "classmate", "colleague",
    "servant", "employer", "boss", "employee",
    "acquaintance", "neighbor", "relative", "cousin", "grandparent", "grandchild",
    "adoptive parent", "adoptive child", "adoptive sibling", "step-parent", "step-child", "step-sibling",
    "mentor", "protector", "guardian", "ward",
}


def _is_kinship_or_role(name: str) -> bool:
    """Check if a name is actually a kinship term or role descriptor."""
    return name.strip().lower() in KINSHIP_TERMS


def _is_english(text: str) -> bool:
    """Check if text contains only ASCII characters (basic English check)."""
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _normalize_relationship(rel_type: str) -> str:
    """Normalize relationship type to closest allowed English type."""
    rel_lower = rel_type.strip().lower()

    if rel_lower in ALLOWED_RELATIONSHIP_TYPES:
        return rel_lower

    mapping = {
        # Vietnamese
        "mẹ": "mother", "cha": "father", "bố": "father", "ba": "father",
        "con trai": "son", "con gái": "daughter", "con": "child",
        "anh em": "sibling", "chị em": "sibling", "anh trai": "brother",
        "chị gái": "sister", "em trai": "brother", "em gái": "sister",
        "vợ": "wife", "chồng": "husband",
        "bạn": "friend", "kẻ thù": "enemy", "đối thủ": "rival",
        "thầy": "teacher", "trò": "disciple", "bạn học": "classmate",
        "ông chủ": "boss", "người hầu": "servant",
        "người quen": "acquaintance", "hàng xóm": "neighbor",
        "ông nội": "grandparent", "bà nội": "grandparent",
        "ông ngoại": "grandparent", "bà ngoại": "grandparent",
        "cháu": "grandchild", "họ hàng": "relative",
        # Chinese
        "母亲": "mother", "妈妈": "mother", "妈": "mother",
        "父亲": "father", "爸爸": "father", "爸": "father",
        "儿子": "son", "女儿": "daughter", "孩子": "child",
        "兄弟": "sibling", "姐妹": "sibling", "哥哥": "brother",
        "姐姐": "sister", "弟弟": "brother", "妹妹": "sister",
        "妻子": "wife", "老婆": "wife", "丈夫": "husband", "老公": "husband",
        "朋友": "friend", "敌人": "enemy", "对手": "rival",
        "老师": "teacher", "学生": "student", "同学": "classmate",
        "老板": "boss", "仆人": "servant",
        "熟人": "acquaintance", "邻居": "neighbor",
        "祖父母": "grandparent", "孙子": "grandchild", "孙女": "grandchild",
        # Korean
        "어머니": "mother", "엄마": "mother",
        "아버지": "father", "아빠": "father",
        "아들": "son", "딸": "daughter",
        "형제": "sibling", "자매": "sibling",
        "아내": "wife", "남편": "husband",
        "친구": "friend", "적": "enemy", "ライバル": "rival",
        "선생님": "teacher", "제자": "disciple", "동창": "classmate",
        # Japanese
        "母": "mother", "お母さん": "mother",
        "父": "father", "お父さん": "father",
        "息子": "son", "娘": "daughter",
        "兄弟": "sibling", "姉妹": "sibling",
        "妻": "wife", "夫": "husband",
        "友達": "friend", "敵": "enemy",
        "先生": "teacher", "弟子": "disciple", "同級生": "classmate",
    }

    if rel_lower in mapping:
        return mapping[rel_lower]

    if _is_english(rel_type):
        return rel_lower

    return rel_type


def _build_existing_chars_str(entities: dict, edges: list) -> str:
    """Build existing characters context string for the learner prompt."""
    if not entities:
        return "(none)"

    entity_parts = []
    for name_orig, info in entities.items():
        translated_name = get_character_translated_name(info)
        role = info.get("role", "")
        pronoun = info.get("pronoun", "")
        pronoun_str = f' pronoun="{pronoun}"' if pronoun else ""
        entity_parts.append(f"  {name_orig}" + (f" ({translated_name})" if translated_name else "") + (f" [{role}{pronoun_str}]" if role or pronoun else ""))

    if edges:
        edge_parts = []
        for edge in edges:
            if len(edge) >= 3:
                from_name = get_character_translated_name(entities.get(edge[0], {})) or edge[0]
                to_name = get_character_translated_name(entities.get(edge[1], {})) or edge[1]
                edge_parts.append(f"  {from_name}({edge[2]})->{to_name}")
        return "Entities:\n" + "\n".join(entity_parts) + "\nRelations:\n" + "\n".join(edge_parts)

    return "Entities:\n" + "\n".join(entity_parts)


def learner_node(state: TranslationState) -> dict:
    """Extract terms and create summary from the translated chapter."""
    novel_name = state["novel_name"]
    chapter_number = state["chapter_number"]
    language = state["source_language"]
    target_language = state.get("target_language", "vi")
    target_name = target_language_name(target_language)

    full_translation = "\n\n".join(state["translated_chunks"])
    source_text = state["source_text"]

    # --- 1. Extract terms + character relationships (single call) ---
    existing_glossary = state.get("glossary", {})
    existing_terms_str = "\n".join(f"  {k} → {v}" for k, v in existing_glossary.items()) if existing_glossary else "(none)"

    existing_characters = state.get("characters", {})
    existing_entities = existing_characters.get("entities", {})
    existing_edges = existing_characters.get("edges", [])
    existing_chars_str = _build_existing_chars_str(existing_entities, existing_edges)

    learn_system_prompt = render_prompt(
        "learner_extract",
        target_language=target_language,
        target_name=target_name,
        existing_terms_str=existing_terms_str,
        existing_chars_str=existing_chars_str,
    )

    learn_user_prompt = f"""=== SOURCE TEXT ({language}) ===
{source_text[:4000]}

=== {target_name.upper()} TRANSLATION ===
{full_translation[:4000]}"""

    new_terms = {}
    new_characters = {}
    learn_response = ""
    try:
        learn_response = get_llm().generate(learn_system_prompt, learn_user_prompt, "learn")

        learn_data = parse_json_object(learn_response)
        new_terms = learn_data.get("terms", {})
        new_characters = learn_data.get("characters", {})
    except Exception as e:
        log_error("Failed to extract terms and characters", e, chapter=chapter_number)
        print(f"\n  [Warning] Failed to extract terms and characters: {e}")

    # Filter out kinship terms and role descriptors from entities
    new_entities = new_characters.get("entities", {})
    filtered_entities = {}
    for name, info in new_entities.items():
        if not _is_kinship_or_role(name):
            filtered_entities[name] = info
        else:
            print(f"  ⚠ Skipped kinship/role term as entity: {name}")
    new_characters["entities"] = filtered_entities

    # Normalize and validate edge relationship types
    new_edges = new_characters.get("edges", [])
    cleaned_edges = []
    for edge in new_edges:
        if len(edge) < 3:
            continue
        from_char, to_char, rel_type = edge[0], edge[1], edge[2]
        if _is_kinship_or_role(from_char) or _is_kinship_or_role(to_char):
            print(f"  ⚠ Skipped edge with kinship term: {from_char} -> {to_char}")
            continue
        normalized_rel = _normalize_relationship(rel_type)
        cleaned_edges.append([from_char, to_char, normalized_rel] + edge[3:])
    new_characters["edges"] = cleaned_edges

    # Filter: only keep terms that appear at least MIN_TERM_FREQUENCY times
    if new_terms:
        new_terms = filter_terms_by_frequency(source_text, new_terms, MIN_TERM_FREQUENCY)

    if new_terms:
        save_glossary(novel_name, new_terms)

    new_entities = new_characters.get("entities", {})
    new_edges = new_characters.get("edges", [])

    if new_entities or new_edges:
        save_characters_batch(novel_name, new_entities, new_edges, chapter=chapter_number)
        print(f"  📝 Updated {len(new_entities)} character(s), {len(new_edges)} relationship(s)")

    # Extract and save pronoun usage examples from this chapter's translation
    all_entities = new_characters.get("entities", {})
    pronoun_examples = extract_pronoun_examples(full_translation, all_entities)
    if pronoun_examples:
        save_pronoun_examples(novel_name, pronoun_examples)
        total_examples = sum(len(exs) for exs in pronoun_examples.values())
        print(f"  💬 Saved {total_examples} pronoun example(s) for {len(pronoun_examples)} character(s)")

    save_source_language(novel_name, state["source_language"])

    log_ai_call(
        "learn",
        system_prompt=learn_system_prompt,
        user_prompt=learn_user_prompt,
        response=learn_response,
        chapter=chapter_number,
        new_terms_count=len(new_terms),
        terms=new_terms,
        characters_count=len(new_characters),
    )

    # --- 2. Create chapter summary ---
    if not config.enable_summary:
        summary_response = ""
    else:
        summary_system_prompt = render_prompt("learner_summary", target_language=target_language, target_name=target_name)
        summary_user_prompt = f"Summarize chapter {chapter_number}:\n\n{full_translation[:4000]}"

        try:
            summary_response = get_llm().generate(summary_system_prompt, summary_user_prompt, "learn_summary")
            save_chapter_summary(novel_name, chapter_number, summary_response)

            log_ai_call(
                "learn_summary",
                system_prompt=summary_system_prompt,
                user_prompt=summary_user_prompt,
                response=summary_response,
                chapter=chapter_number,
                summary_length=len(summary_response),
            )
        except Exception as e:
            log_error("Failed to generate summary", e, chapter=chapter_number)
            print(f"\n  [Warning] Failed to generate summary: {e}")
            summary_response = ""

    return {
        "new_terms": new_terms,
        "new_characters": new_characters,
        "chapter_summary": summary_response,
        "final_translation": full_translation,
    }
