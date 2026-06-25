You are analyzing a novel chapter. Extract important terms AND character relationships.

=== TERMS ===
Extract only named/proper terms that need exact consistency across chapters:
1. Named places, organizations, realms, sects, clans, schools, companies
2. Named artifacts, techniques, systems, events, titles/ranks tied to a named concept
3. Recurring named concepts whose translation should stay fixed

DO NOT include:
- Character names here; put named people in characters.entities instead
- Common nouns, verbs, adjectives, descriptive phrases, or everyday setting terms
- Generic role/kinship/address words unless they are part of a unique proper name
- One-off mentions, dialogue fragments, idioms, jokes, insults, or tone/style rules
- Generic terms like "sword", "fire", "mountain" unless they are proper names
- Terms already in the existing glossary

Existing terms (DO NOT repeat):
{{existing_terms_str}}

=== CHARACTERS ===
Identify characters that appear in this chapter and their relationships to each other.

EXISTING CHARACTERS (update relationships if new ones are discovered):
{{existing_chars_str}}

RULES FOR ENTITIES:
- Only extract characters with PROPER NAMES (e.g. "陆远秋", "白清夏")
- NEVER extract kinship terms or role descriptors as character names:
  papa, mama, dad, mom, father, mother, uncle, aunt, grandma, grandpa, brother, sister,
  爸爸, 妈妈, 父亲, 母亲, 叔叔, 阿姨, 爷爷, 奶奶, 哥哥, 姐姐, 弟弟, 妹妹,
  teacher, student, master, servant, guard, doctor, etc.
- These kinship/role terms describe relationships TO named characters, they are NOT characters themselves
- Do NOT create a separate entity for title/address forms such as "白叔叔", "刘妈", "张阿姨", "李老师", "梁先生",
  "bác Bạch", "dì Lưu", "cô Lý", "ông Lương" when they refer to an existing named character
- If a title/address form clearly refers to an existing character, mention it only through address_rules or as context; keep the entity key as the canonical original name
- If the real name is unknown and the person is only a minor one-off role, skip them instead of creating a generic entity
- Create a temporary title-based entity only when the person recurs or has important relationships before their real name is revealed
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

RULES FOR ADDRESS RULES (VIETNAMESE XƯNG HÔ):
- Extract ONLY stable, explicit direct-address patterns between two named characters
- Use original names for "speaker" and "listener"; never use translated names as keys
- "self" is how the speaker refers to themselves in dialogue (e.g. "ta", "tôi", "anh", "em", "thiếp")
- "other" is how the speaker addresses/refers to the listener (e.g. "ngươi", "nàng", "em", "huynh", "bệ hạ")
- Include a rule only when the source or translation clearly supports it; if unsure, leave it out
- Record only the stable default pair used across scenes; do not repeat an unchanged existing rule
- Do NOT store proper names, temporary nicknames, insults, jokes, or emotional outbursts as address rules
- If a stable relationship change creates a new default pair, emit the new rule from this chapter
- Do NOT add generic third-person pronoun examples here
- Use "since": {{chapter_number}} when the pattern starts or is first confirmed in this chapter

Respond with JSON ONLY (no other text):
{
    "terms": {
        "original term": "Vietnamese translation"
    },
    "characters": {
        "entities": {
            "original name": {
                "translated_name": "Vietnamese name",
                "role": "protagonist | antagonist | supporting | minor",
                "pronoun": "Vietnamese pronoun (e.g. cậu, anh ấy, cô ấy, hắn)"
            }
        },
        "edges": [
            ["from_original_name", "to_original_name", "relationship_type_in_english"]
        ],
        "address_rules": [
            {
                "speaker": "from_original_name",
                "listener": "to_original_name",
                "self": "Vietnamese self-reference",
                "other": "Vietnamese address/reference for listener",
                "since": {{chapter_number}},
                "notes": "optional short reason or context"
            }
        ]
    }
}
