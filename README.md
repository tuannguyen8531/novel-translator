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

## Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env  # or create .env manually
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
SKIP_REVIEW=false
```

## Usage

```bash
# Basic usage (auto-detect language)
uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1

# Specify source language
uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1 -l chinese

# Use Gemini provider
uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1 -p gemini

# Skip review step (faster, no quality check)
uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1 --skip-review
```

### Options

| Flag | Description |
|------|-------------|
| `-i, --input` | Path to input `.txt` file (required) |
| `-n, --novel` | Novel name for glossary (required) |
| `-c, --chapter` | Chapter number (required) |
| `-l, --lang` | Source language: `chinese`, `korean`, `japanese` (auto-detect if omitted) |
| `-p, --provider` | LLM provider: `ollama`, `gemini`, `openrouter` (overrides `.env`) |
| `--skip-review` | Skip quality review step |

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
├── main.py              # CLI entry point
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
├── glossary/            # Auto-generated per-novel glossaries
├── input/               # Place source chapters here
├── output/              # Translated chapters saved here
└── logs/                # Full AI request/response logs
```

## Testing

```bash
uv run pytest tests/ -v
```

## License

MIT
