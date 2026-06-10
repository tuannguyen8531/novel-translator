You are analyzing a novel chapter. Extract important terms AND character relationships.

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
- If a character is only referred to as "Papa" or "Mama" without a real name being revealed, skip them
- Only include characters that actually appear or are mentioned in this chapter
- Assign a consistent English pronoun or reference style for each character based on gender,
  status, narrative voice, and relationship dynamics. Examples: "he", "she", "they",
  "the young master", "the lady", "the old man". Use the SAME style across all chapters.
- Use the JSON key "translated_name" for the English rendering or romanized name to keep in the glossary.

RULES FOR EDGES (RELATIONSHIPS):
- Relationship types MUST be in ENGLISH ONLY
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

RULES FOR ADDRESS RULES (ENGLISH DIRECT ADDRESS / REFERENCE STYLE):
- Extract ONLY stable, explicit direct-address patterns between two named characters
- Use original names for "speaker" and "listener"; never use translated or romanized names as keys
- "self" is how the speaker refers to themselves in dialogue, when relevant (e.g. "I", "this servant")
- "other" is how the speaker addresses/refers to the listener (e.g. "Your Highness", "Master", "my lady", first name)
- Include a rule only when the source or translation clearly supports it; if unsure, leave it out
- Do NOT add generic he/she/they examples here
- Use "since": {{chapter_number}} when the pattern starts or is first confirmed in this chapter

Respond with JSON ONLY (no other text):
{
    "terms": {
        "original term": "English translation"
    },
    "characters": {
        "entities": {
            "original name": {
                "translated_name": "English or romanized name",
                "role": "protagonist | antagonist | supporting | minor",
                "pronoun": "English pronoun/reference style (e.g. he, she, they, the young master)"
            }
        },
        "edges": [
            ["from_original_name", "to_original_name", "relationship_type_in_english"]
        ],
        "address_rules": [
            {
                "speaker": "from_original_name",
                "listener": "to_original_name",
                "self": "English self-reference, if needed",
                "other": "English address/reference for listener",
                "since": {{chapter_number}},
                "notes": "optional short reason or context"
            }
        ]
    }
}
