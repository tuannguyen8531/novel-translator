# Novel Translator

CLI tool for translating web novel chapters from Chinese/Korean/Japanese to Vietnamese using LLMs.

## Features

- **Multi-provider support**: Ollama (local), Gemini, OpenRouter
- **Auto language detection**: Unicode heuristic with LLM fallback
- **Context-aware translation**: Per-novel glossary + chapter summaries maintain consistency
- **Quality review loop**: LLM scores translations, retries below threshold
- **Language-specific rules**: Honorifics, genre terms (xianxia, murim, isekai, regression)
- **Chunked processing**: Paragraph-aware splitting with overlap for context continuity

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
TRANSLATION_TEMPERATURE=0.3
TRANSLATION_MAX_TOKENS=4096
CHUNK_SIZE=1500
CHUNK_OVERLAP=100
REVIEW_THRESHOLD=0.7
MAX_RETRIES=2
ENABLE_REVIEW=false
ENABLE_SUMMARY=false
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

Then run:

```bash
# Translate all untranslated chapters
uv run translate my-novel

# Specify source language
uv run translate my-novel -l chinese

# Use Gemini with review and summary
uv run translate my-novel -p gemini -r -s

# Translate a range of chapters
uv run translate my-novel --from 5 --to 10

# Verbose mode (print AI requests/responses)
uv run translate my-novel -v
```

### Options

| Flag | Description |
|------|-------------|
| `novel` | Novel name (matches directory in `input/`) |
| `-l, --lang` | Source language: `chinese`, `korean`, `japanese` (auto-detect) |
| `-p, --provider` | LLM provider: `ollama`, `gemini`, `openrouter` |
| `-r, --review` | Enable review step |
| `-s, --summary` | Enable chapter summary generation |
| `-v, --verbose` | Print full AI request/response to console |
| `--from N` | Start from chapter N |
| `--to N` | Stop at chapter N (0 = all) |

### How it works

1. Scans `input/{novel}/` for `chapter_*.txt` files
2. Checks glossary for already-translated chapters
3. Translates only missing chapters, in order
4. Shows single-line progress: `[3/10] 30% · 45s ch · 120s total`
5. Saves output to `output/{novel}/chapter_*.txt`
6. Saves detected language to glossary immediately — re-running skips detection
7. Tracks translated chapters in glossary — re-running skips them

## Architecture

Translation pipeline (LangGraph state machine):

```
detect → context → chunk → translate → review → [retry loop] → accept → learn → END
```

| Node | Purpose |
|------|---------|
| `detect` | Unicode heuristic → LLM fallback for language detection |
| `context` | Load rules, glossary, last 3 chapter summaries |
| `chunk` | Split text by paragraphs/sentences with overlap |
| `translate` | LLM translation with rules + glossary + context |
| `review` | LLM scores translation (0-1), retries if below threshold |
| `learn` | Extract new terms, generate chapter summary, save to glossary |

## Project Structure

```
├── translate.py         # Batch CLI (primary entry point)
├── main.py              # Single-chapter CLI (legacy)
├── src/
│   ├── config.py        # Environment-based configuration
│   ├── models/
│   │   └── state.py     # LangGraph TypedDict state
│   ├── graph/
│   │   ├── builder.py   # Pipeline assembly
│   │   └── nodes/       # Individual pipeline nodes
│   ├── services/
│   │   ├── llm.py       # Multi-provider LLM interface
│   │   ├── glossary.py  # Per-novel glossary management
│   │   └── logger.py    # AI call logging
│   └── utils/
│       └── text.py      # Language detection, chunking
├── rules/               # Translation rules (common + per-language)
├── tests/               # Test suite
├── glossary/            # Auto-generated per-novel glossaries
├── input/               # Place source chapters here
├── output/              # Translated chapters saved here
└── logs/                # AI request/response logs
```

## Testing

```bash
uv run pytest tests/ -v
```

## License

MIT
