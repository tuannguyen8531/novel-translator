# Common Translation Rules (All Languages → Vietnamese)

## General Guidelines
- Translate naturally and fluently, as if the text was originally written in Vietnamese
- Do NOT translate word-by-word; translate by meaning and context
- Preserve the original tone: formal scenes stay formal, casual scenes stay casual
- Preserve paragraph structure and dialogue formatting

## Scene Analysis & Dynamic Filtering
- Before translating, infer the scene type and adjust the style accordingly
- Action scenes: prioritize brevity, short punchy sentences, fewer conjunctions, and vivid verbs
- Romance or drama scenes: soften the tone, increase reduplicatives, and favor emotional resonance
- Info-dump or exposition scenes: use clear formal Vietnamese, including Hán-Việt terms when they improve clarity

## Dialogue
- Use Vietnamese quotation marks: "" or dashes (—) for dialogue
- Match the speaker's personality and relationship in pronoun choice
- Keep exclamations, ellipses (...), and emotional markers intact

## Contextual Pronoun System (RTAS)
- First follow any provided address rules exactly; they override these general pronoun guidelines
- If no address rule is provided for a pair, infer pronouns from age, status, relationship, politeness level, and scene tension
- Keep the same pronoun pair for the same speaker/listener within a scene unless the source clearly shows a relationship or emotional shift
- Do not randomly alternate between "tôi/cậu", "anh/em", "ta/ngươi", names, and zero pronouns for the same pair
- Prefer natural Vietnamese omission of pronouns when the speaker/listener is obvious
- Use RTAS (Relationship Tension & Affection Score) only as an internal fallback heuristic; do not mention the score in the output
- Estimate RTAS from the characters' words, actions, and relationship context
- RTAS 1.0 - 2.5: distant, formal, or antagonistic relationships. Prefer forms like Tôi - Anh/Cô, Ngài - Tôi, or other respectful equivalents
- RTAS 2.5 - 3.5: social, familiar, or neutral relationships. Prefer forms like Tớ - Cậu, Mình - Bạn, or Tôi - Ông/Bà when appropriate
- RTAS 3.5 - 4.2: warm, intimate, or transitional relationships. Prefer forms like Anh - Em (light), Tớ - Anh, or other close-but-natural pairings
- RTAS 4.2 - 5.0: deeply intimate relationships, lovers, spouses, or life-and-death moments. Prefer forms like Anh - Em (strong), Mình - Cậu, or similarly affectionate forms
- Family override: prioritize Anh/Chị - Em, Ba/Mẹ - Con, or equivalent kinship-based forms for close family relations. Do not use Tao - Mày for siblings
- Shock bypass: if a character is furious or shocked enough that the relationship abruptly collapses, a brief switch to Tao - Mày is allowed when it clearly serves the scene

## Names & Proper Nouns
- Keep character names consistent throughout the entire novel
- Refer to the GLOSSARY for established translations
- For new names not in the glossary, choose a natural Vietnamese rendering

## Internet/Modern Slang
- Translate internet slang to Vietnamese equivalents when possible
- If no equivalent exists, keep the original with context

## Anti-Translationese
- Avoid overusing "một cách"; prefer concise, idiomatic Vietnamese
- Prefer active voice unless passive voice carries a clear meaning advantage
- Reduce unnecessary possessive "của" in close or natural speech
- Avoid repeating the same exclamation too often; vary naturally to match the scene
- Replace neutral verbs with stronger, more specific Vietnamese verbs when they better fit the scene

## Boldness & Sensory Writing
- When the scene is intense, allow shorter, broken sentences to create rhythm and tension
- Prefer vivid Vietnamese verbs over neutral ones when they sharpen the image
- Use reduplicative forms when they strengthen emotion, motion, or atmosphere
- For extreme emotional intensity, fragmented sentences are allowed when they heighten shock, breathlessness, or crying
- For sensitive or adult content, prefer metaphorical and literary language over clinical description
- Use Vietnamese onomatopoeia and reduplicatives to strengthen sound, texture, and motion

## Formatting
- Preserve line breaks between paragraphs
- Keep special formatting like【brackets】for in-story posts, messages, etc.
- Keep『brackets』for chat messages or system notifications

## Quality Standards
- No missing sentences or paragraphs — translate EVERYTHING
- No added content — do not invent details not in the source
- No translator notes, footnotes, or explanations in the output
- Preserve special symbols and formatting such as 【Posts】, 『Systems』, and 「Dialogue」
