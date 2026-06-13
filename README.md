# Novel Translator

CLI tool for translating web novel chapters from Chinese/Korean/Japanese to Vietnamese or English using LLMs.

## Features

- **Multi-provider support**: Ollama (local), Gemini, OpenRouter
- **Auto language detection**: Unicode heuristic with LLM fallback
- **Selectable target language**: Vietnamese (`vi`) by default, English (`en`) via CLI/env
- **Context-aware translation**: Per-novel glossary + chapter summaries maintain consistency
- **Quality review loop**: LLM scores translations, deterministic checks catch mechanical issues, retries below threshold
- **Language-specific rules**: Honorifics, genre terms (xianxia, murim, isekai, regression)
- **Chunked processing**: Paragraph-aware splitting with overlap for context continuity
- **Illustration restoration**: Preserves `[[ILLUSTRATION:...]]` markers and restores imported EPUB images during packaging

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Ollama](https://ollama.com) (for local LLM) — or use Gemini/OpenRouter API keys

## Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env  # or create .env manually

# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the default model
ollama pull qwen3:8b

# Start Ollama (runs in background)
ollama serve
```

### Environment Variables

```env
# Provider: ollama | gemini | openrouter
LLM_PROVIDER=ollama

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Gemini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash

# OpenRouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=qwen/qwen3-8b

# Translation settings
TARGET_LANGUAGE=vi
TRANSLATION_TEMPERATURE=0.3
TRANSLATION_MAX_TOKENS=4096
CHUNK_SIZE=1500
CHUNK_OVERLAP=100
REVIEW_THRESHOLD=0.7
MAX_RETRIES=2
ENABLE_REVIEW=false
ENABLE_SUMMARY=false

# Novel share directory (optional)
# When set, reads from {NOVEL_SHARE_DIR}/{novel}/chapter_*.txt
# and writes to {NOVEL_SHARE_DIR}/output/{novel}/
NOVEL_SHARE_DIR=../share
```

## Usage

Place source files in the format `input/{novel}/chapter_{number}.txt`:

```
input/
└── my-novel/
    ├── chapter_1.txt
    ├── chapter_2.txt
    └── chapter_3.txt
```

Or, if `NOVEL_SHARE_DIR` is set in `.env`, use `{NOVEL_SHARE_DIR}/{novel}/chapter_{number}.txt`.

Then run:

```bash
# Translate all untranslated chapters
uv run translate my-novel

# Specify source language
uv run translate my-novel -l chinese

# Translate to English instead of Vietnamese
uv run translate my-novel --target en

# Use Gemini with review and summary
uv run translate my-novel -p gemini -r -s

# Translate a range of chapters
uv run translate my-novel -n 5 -e 10

# Translate at most 3 chapters starting from chapter 5
uv run translate my-novel -n 5 -m 3

# Resume chapter-level progress after an interrupted run
uv run translate my-novel -R

# Retry chapters recorded as failed
uv run translate my-novel -F

# Dry run to see what would be translated
uv run translate my-novel -d

# Verbose mode (print AI requests/responses)
uv run translate my-novel -v
```

### Options

| Flag | Description |
|------|-------------|
| `novel` | Novel name (matches directory in `input/`) |
| `-l, --lang` | Source language: `chinese`, `korean`, `japanese` (auto-detect) |
| `-t, --target` | Target language: `vi`, `en` (default from `TARGET_LANGUAGE`, fallback `vi`) |
| `-p, --provider` | LLM provider: `ollama`, `gemini`, `openrouter` |
| `-r, --review` | Enable review step |
| `-s, --summary` | Enable chapter summary generation |
| `-v, --verbose` | Print full AI request/response to console |
| `-n, --start N` | Start from chapter N |
| `-e, --to N` | Stop at chapter N (0 = all) |
| `-f, --force` | Re-translate already translated chapters |
| `-d, --dry-run` | List chapters to translate without running |
| `-R, --resume` | Skip chapters marked completed in `.progress/{novel}.json` |
| `-F, --failed-only` | Translate only chapters marked failed in `.progress/{novel}.json` |
| `-m, --limit N` | Translate at most N chapters (0 = no limit) |

For the default `vi` target, outputs stay in the legacy paths: `output/{novel}/`,
`reports/{novel}/`, `.progress/{novel}.json`, and `glossary/{novel}.json`.
For non-default targets such as `en`, generated data is isolated under target-specific
paths such as `output/en/{novel}/`, `reports/en/{novel}/`, `.progress/en/{novel}.json`,
and `glossary/{novel}.en.json`.

### Glossary CLI

Manage per-novel glossary memory without calling an LLM:

```bash
# List glossary terms
uv run translate glossary list my-novel

# Add or update a term
uv run translate glossary add my-novel 李明 "Lý Minh"

# Remove a term
uv run translate glossary remove my-novel 李明

# Export full glossary JSON
uv run translate glossary export my-novel

# List character memory
uv run translate glossary characters my-novel

# Set a character pronoun
uv run translate glossary pronoun my-novel 李明 "cậu"

# Update a character name or role
uv run translate glossary character my-novel 李明 --translated-name "Lý Minh" --role protagonist

# Add or update a relationship
uv run translate glossary relationship my-novel 李明 张伟 friend --since 3

# Validate glossary JSON
uv run translate glossary validate my-novel

# Audit translated output against glossary terms
uv run translate glossary audit my-novel
```

### Packaging CLI (EPUB & PDF)

After translating chapters, you can package them into a beautifully formatted EPUB or PDF book. This operates completely offline and does not call any LLM APIs:

```bash
# Package a novel into both EPUB and PDF
uv run pack my-novel

# Package into EPUB format only
uv run pack my-novel -f epub

# Package into PDF format only
uv run pack my-novel -f pdf

# Package English output from output/en/{novel}/
uv run pack my-novel --target en
# Writes output/my-novel.en.epub and output/my-novel.en.pdf by default

# Customize book title and author metadata
uv run pack my-novel --title "The Great Adventure" --author "Author Name"

# Specify a custom directory to save the packaged files
uv run pack my-novel -o /path/to/save/

# Enable dark mode for PDF output (charcoal background, cream/light-gray text)
uv run pack my-novel -f pdf --dark
```

Options for `pack`:

| Flag | Description |
|------|-------------|
| `novel` | Novel name (matches directory name in output/) |
| `-f, --format` | Packaging format: `epub`, `pdf`, or `all` (default: `all`) |
| `-t, --title` | Custom book title (defaults to formatted novel name) |
| `-a, --author` | Author name in book metadata (default: `AI Translator`) |
| `--target` | Target language output to package: `vi`, `en` (default from `TARGET_LANGUAGE`, fallback `vi`) |
| `-o, --output` | Custom directory to save the output files (defaults to novel root) |
| `--dark` | Enable dark mode for PDF output |

Packaged files are named `{novel}.{target}.epub` and `{novel}.{target}.pdf`.
For local output, they are written outside the chapter folder under `output/`,
for example `output/my-novel.en.epub`.

*Note for PDF format:* The packager automatically scans the system for TrueType serif fonts supporting Vietnamese diacritics (like DejaVuSerif) to ensure correct unicode rendering. It also cleans up any residual Chinese punctuation marks (`『`, `』`, etc.) or untranslated characters.

When crawler-imported chapters contain markers such as `[[ILLUSTRATION:003-001.jpg]]`,
`pack` loads the matching file from `{novel}/illustrations/` and inserts it at that position
in the generated EPUB or PDF.

### How it works

1. Scans `input/{novel}/` (or `{NOVEL_SHARE_DIR}/{novel}/` if set) for `chapter_*.txt` files
2. Checks target-specific output for already-translated chapters
3. Translates only missing chapters, in order
4. Shows single-line progress: `[3/10] 30% · 45s ch · 120s total`
5. Saves output to `output/{novel}/chapter_*.txt`
6. Saves detected source language to glossary immediately — re-running skips detection
7. Updates glossary memory with detected language, terms, characters, relationships, address rules, and summaries
8. Writes chapter quality reports to `reports/{novel}/chapter_*.json`
9. Tracks completed/failed chapters in `.progress/{novel}.json`

## Architecture

Translation pipeline (LangGraph state machine):

```
detect → context → chunk → translate → review → [retry loop] → accept → learn → END
```

| Node | Purpose |
|------|---------|
| `detect` | Unicode heuristic → LLM fallback for language detection |
| `context` | Load rules, glossary, last 3 chapter summaries, active characters with relationships and address rules |
| `chunk` | Split text by paragraphs/sentences with overlap |
| `translate` | LLM translation with rules + glossary + context |
| `review` | LLM scores translation (0-1), applies deterministic quality checks, retries if below threshold |
| `learn` | Extract new terms, character memory, chapter summary, save to glossary |

## Project Structure

```
├── translate.py         # Batch CLI (primary entry point)
├── main.py              # Single-chapter CLI
├── pack.py              # Packaging CLI (EPUB & PDF)
├── src/
│   ├── config.py        # Environment-based configuration with validation
│   ├── prompts/         # LLM prompt templates ({{var}} placeholders)
│   │   ├── __init__.py      # render_prompt() helper
│   │   ├── vi/              # Vietnamese target prompts
│   │   ├── en/              # English target prompts
│   │   └── detector.md
│   ├── models/
│   │   └── state.py     # LangGraph TypedDict state
│   ├── domain/          # Pure translation-domain rules (no IO/LLM)
│   │   ├── chunking.py  # Paragraph/sentence chunking with overlap
│   │   ├── glossary.py  # Glossary formatting, character context, merge rules
│   │   ├── language.py  # Unicode language detection heuristic
│   │   ├── quality.py   # Deterministic post-translation quality checks
│   │   └── terms.py     # Glossary term frequency filtering
│   ├── graph/
│   │   ├── builder.py   # Pipeline assembly
│   │   └── nodes/       # Individual pipeline nodes
│   │       ├── detector.py
│   │       ├── context.py
│   │       ├── chunker.py
│   │       ├── translator.py
│   │       ├── reviewer.py
│   │       └── learner.py
│   ├── services/
│   │   ├── llm/         # Multi-provider LLM interface
│   │   │   ├── __init__.py
│   │   │   ├── base.py      # Abstract base class
│   │   │   ├── factory.py   # Provider factory
│   │   │   ├── fallback.py  # Primary + fallback wrapper
│   │   │   ├── ollama.py
│   │   │   ├── gemini.py
│   │   │   └── openrouter.py
│   │   ├── glossary.py  # JSON persistence for per-novel glossary/memory
│   │   └── logger.py    # AI call logging
│   └── utils/
│       ├── display.py   # ANSI colors, banner, provider check
│       ├── json.py      # JSON object parsing helpers
│       └── progress.py  # Batch progress tracker
├── rules/               # Target-specific translation rules
│   ├── vi/              # Vietnamese target rules
│   └── en/              # English target rules
├── tests/               # Test suite grouped by application layer
│   ├── cli/             # CLI parsing and batch workflow helpers
│   ├── config/          # Runtime configuration
│   ├── domain/          # Pure translation/domain rules
│   ├── graph/           # Graph routing and node behavior
│   ├── models/          # Shared state/data models
│   ├── prompts/         # Prompt template tests
│   ├── services/        # LLM, glossary persistence, logging
│   └── utils/           # Reusable helpers
├── glossary/            # Auto-generated per-novel glossaries
├── input/               # Place source chapters here
├── output/              # Translated chapters saved here
├── reports/             # Per-chapter quality reports
├── .progress/           # Chapter-level completed/failed state
└── logs/                # AI request/response logs
```

## Testing

```bash
uv run pytest tests/ -v
```

Tests are organized by layer under `tests/`. For focused runs:

```bash
uv run pytest tests/domain/ -v
uv run pytest tests/services/ -v
uv run pytest tests/cli/ -v
```

See `tests/README.md` for the full test layout.

## License

MIT
