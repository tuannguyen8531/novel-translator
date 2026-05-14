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
from src.domain.glossary import extract_pronoun_examples
from src.utils.json import parse_json_object


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

    # Map common non-English or variant terms to allowed types
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

    # If it's already ASCII/English but not in allowed list, return as-is
    # (LLM may use valid but unlisted terms)
    if _is_english(rel_type):
        return rel_lower

    # Fallback: return original (will be caught by validation)
    return rel_type


def learner_node(state: TranslationState) -> dict:
    """Extract terms and create summary from the translated chapter."""
    novel_name = state["novel_name"]
    chapter_number = state["chapter_number"]
    language = state["source_language"]

    # Combine all translated chunks
    full_translation = "\n\n".join(state["translated_chunks"])
    # Also need source for term extraction
    source_text = state["source_text"]

    # --- 1. Extract terms + character relationships (single call) ---
    existing_glossary = state.get("glossary", {})
    existing_terms_str = "\n".join(f"  {k} → {v}" for k, v in existing_glossary.items()) if existing_glossary else "(none)"

    existing_characters = state.get("characters", {})
    existing_entities = existing_characters.get("entities", {})
    existing_edges = existing_characters.get("edges", [])
    existing_chars_str = "(none)"
    if existing_entities:
        entity_parts = []
        for name_orig, info in existing_entities.items():
            name_vi = info.get("name_vi", "")
            role = info.get("role", "")
            pronoun = info.get("pronoun", "")
            pronoun_str = f' pronoun="{pronoun}"' if pronoun else ""
            entity_parts.append(f"  {name_orig}" + (f" ({name_vi})" if name_vi else "") + (f" [{role}{pronoun_str}]" if role or pronoun else ""))
        if existing_edges:
            edge_parts = []
            for edge in existing_edges:
                if len(edge) >= 3:
                    from_vi = existing_entities.get(edge[0], {}).get("name_vi", edge[0])
                    to_vi = existing_entities.get(edge[1], {}).get("name_vi", edge[1])
                    edge_parts.append(f"  {from_vi}({edge[2]})->{to_vi}")
            existing_chars_str = "Entities:\n" + "\n".join(entity_parts) + "\nRelations:\n" + "\n".join(edge_parts)
        else:
            existing_chars_str = "Entities:\n" + "\n".join(entity_parts)

    learn_system_prompt = f"""You are analyzing a novel chapter. Extract important terms AND character relationships.

=== TERMS ===
STRICT CRITERIA — only include terms that meet ALL of these:
1. Character names (people, beings with names)
2. Place names (locations, realms, organizations with names)
3. Special recurring terms (unique skills, cultivation levels, world-specific concepts that will appear repeatedly)

EXCLUDE:
- Common words, verbs, adjectives, descriptive phrases
- One-off terms that appear only once or twice
- Generic terms like "sword", "fire", "mountain" unless they are proper names
- Translated dialogue fragments or idioms
- Terms already in the existing glossary

Existing terms (DO NOT repeat):
{existing_terms_str}

=== CHARACTERS ===
Identify characters that appear in this chapter and their relationships to each other.

EXISTING CHARACTERS (update relationships if new ones are discovered):
{existing_chars_str}

RULES FOR ENTITIES:
- Only extract characters with PROPER NAMES (e.g. "陆远秋", "白清夏")
- NEVER extract kinship terms or role descriptors as character names:
  papa, mama, dad, mom, father, mother, uncle, aunt, grandma, grandpa, brother, sister,
  爸爸, 妈妈, 父亲, 母亲, 叔叔, 阿姨, 爷爷, 奶奶, 哥哥, 姐姐, 弟弟, 妹妹,
  teacher, student, master, servant, guard, doctor, etc.
- These kinship/role terms describe relationships TO named characters, they are NOT characters themselves
- If a character is only referred to as "Papa" or "Mama" without a real name being revealed, skip them
- Only include characters that actually appear or are mentioned in this chapter
- Assign a consistent Vietnamese pronoun for each character based on age, gender, status,
  and relationship dynamics. Examples: "cậu", "anh ấy", "ông", "bà", "cô ấy", "chị ấy",
  "hắn", "y", "nó", "ta", "quý ngài", "tiểu thư". Use the SAME pronoun across all chapters.

RULES FOR EDGES (RELATIONSHIPS):
- Relationship types MUST be in ENGLISH ONLY — never Vietnamese or other languages
- Use ONLY these allowed relationship types:
  mother, father, parent, son, daughter, child, sibling, brother, sister,
  husband, wife, spouse, romantic interest, crush, ex,
  friend, enemy, rival, ally,
  master, disciple, teacher, student, classmate, colleague,
  servant, master (employer), boss, employee,
  acquaintance, neighbor, relative, cousin, grandparent, grandchild
- If a relationship does not fit the list, use the closest English equivalent
- Avoid vague relationships like "knows", "met", "connected"
- Store each relationship ONCE — do NOT add both A→B and B→A for the same pair
  (e.g. if you add [A, B, "mother"], do NOT also add [B, A, "son"])
- If a character's role is unclear, use "minor"

Respond with JSON ONLY (no other text):
{{
    "terms": {{
        "original term": "Vietnamese translation"
    }},
    "characters": {{
        "entities": {{
            "original name": {{
                "name_vi": "Vietnamese name",
                "role": "protagonist | antagonist | supporting | minor",
                "pronoun": "Vietnamese pronoun (e.g. cậu, anh ấy, cô ấy, hắn)"
            }}
        }},
        "edges": [
            ["from_original_name", "to_original_name", "relationship_type_in_english"]
        ]
    }}
}}"""

    learn_user_prompt = f"""=== SOURCE TEXT ({language}) ===
{source_text[:4000]}

=== VIETNAMESE TRANSLATION ===
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
        # Skip edges where from or to is a kinship term
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
        summary_system_prompt = """Write a very concise summary of this chapter in 2-3 sentences (max 50 words).
Include ONLY: key events, main characters involved, and any important plot developments.
Write in Vietnamese. Output ONLY the summary, nothing else."""

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
