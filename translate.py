"""
Novel Translator — Batch Translate CLI

Usage:
    uv run translate my-novel
    uv run translate my-novel -l chinese
    uv run translate my-novel -p gemini -r -s
"""

import argparse
import re
import sys
import time
import warnings
from pathlib import Path

# Suppress LangChain internal deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")
warnings.filterwarnings("ignore", message=".*LangChainPendingDeprecationWarning.*")

from src.config import config
from src.graph.builder import build_graph
from src.models.state import initial_state
from src.services.glossary import (
    load_translated_chapters,
)

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

INPUT_DIR = Path("input")


def print_banner():
    """Print the application banner."""
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════╗
║         📚  Novel Translator  📚                     ║
║    Chinese / Korean / Japanese → Vietnamese          ║
╚══════════════════════════════════════════════════════╝{RESET}
{DIM}Provider: {config.llm_provider} · Model: {_get_model_name()} · Temp: {config.translation_temperature}{RESET}
""")


def _get_model_name() -> str:
    """Get the current model name based on provider."""
    if config.llm_provider == "ollama":
        return config.ollama_model
    elif config.llm_provider == "gemini":
        return config.gemini_model
    elif config.llm_provider == "openrouter":
        return config.openrouter_model
    return "unknown"


def check_provider():
    """Verify the configured LLM provider is accessible."""
    provider = config.llm_provider

    if provider == "ollama":
        import httpx
        try:
            resp = httpx.get(f"{config.ollama_base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if config.ollama_model not in models:
                model_base = config.ollama_model.split(":")[0]
                matching = [m for m in models if m.startswith(model_base)]
                if not matching:
                    print(f"{YELLOW}⚠ Model '{config.ollama_model}' not found. Available: {', '.join(models)}")
                    print(f"  Run: ollama pull {config.ollama_model}{RESET}")
                    return False
            print(f"{GREEN}✓ Ollama connected. Model: {config.ollama_model}{RESET}")
            return True
        except Exception:
            print(f"{RED}✗ Cannot connect to Ollama at {config.ollama_base_url}")
            print(f"  Make sure Ollama is running: ollama serve{RESET}")
            return False

    elif provider == "gemini":
        if not config.gemini_api_key:
            print(f"{RED}✗ GEMINI_API_KEY not set in .env{RESET}")
            return False
        print(f"{GREEN}✓ Gemini API configured. Model: {config.gemini_model}{RESET}")
        return True

    elif provider == "openrouter":
        if not config.openrouter_api_key:
            print(f"{RED}✗ OPENROUTER_API_KEY not set in .env{RESET}")
            return False
        print(f"{GREEN}✓ OpenRouter API configured. Model: {config.openrouter_model}{RESET}")
        return True

    else:
        print(f"{RED}✗ Unknown provider: {provider}{RESET}")
        return False


def scan_chapters(novel_name: str) -> dict[int, Path]:
    """Scan input directory for chapter files.

    Returns dict of chapter_number -> file_path, sorted by chapter number.
    """
    novel_dir = INPUT_DIR / novel_name
    if not novel_dir.exists():
        print(f"{RED}✗ Input directory not found: {novel_dir}{RESET}")
        sys.exit(1)

    chapters = {}
    pattern = re.compile(r"^chapter_(\d+)\.txt$")

    for f in novel_dir.iterdir():
        if f.is_file():
            match = pattern.match(f.name)
            if match:
                chapters[int(match.group(1))] = f

    return dict(sorted(chapters.items()))


def find_untranslated(novel_name: str, chapters: dict[int, Path]) -> list[int]:
    """Find chapters that exist in input but haven't been translated yet."""
    translated = load_translated_chapters(novel_name)
    return [ch for ch in chapters if ch not in translated]


def translate_file(input_path: Path, novel_name: str, chapter_number: int, language: str = "") -> bool:
    """Run the translation pipeline on a file. Returns True on success."""
    source_text = input_path.read_text(encoding="utf-8")
    if not source_text.strip():
        print(f"  {RED}✗ Empty file, skipping{RESET}")
        return False

    print(f"{DIM}  📄 {input_path.name} ({len(source_text)} chars){RESET}")

    graph = build_graph()

    start_time = time.time()

    result = graph.invoke(initial_state(
        source_text=source_text,
        source_language=language,
        novel_name=novel_name,
        chapter_number=chapter_number,
    ))

    elapsed = time.time() - start_time

    # Save output
    output_dir = Path("output") / novel_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"chapter_{chapter_number:03d}.txt"

    final_text = result.get("final_translation", "")
    output_file.write_text(final_text, encoding="utf-8")

    new_terms = result.get("new_terms", {})
    print(f"  {GREEN}✓ Done{RESET} · {DIM}{len(final_text)} chars · {elapsed:.1f}s")
    if new_terms:
        print(f"  {DIM}+ {len(new_terms)} new terms{RESET}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="📚 Novel Translator — Batch translate chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run translate my-novel
  uv run translate my-novel -l chinese
  uv run translate my-novel -p gemini -r -s
        """,
    )
    parser.add_argument(
        "novel",
        help="Novel name (must match directory in input/)",
    )
    parser.add_argument(
        "-l", "--lang",
        choices=["chinese", "korean", "japanese"],
        default="",
        help="Source language (auto-detect if omitted)",
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "gemini", "openrouter"],
        default=None,
        help="LLM provider (overrides .env)",
    )
    parser.add_argument(
        "-r", "--review",
        action="store_true",
        help="Enable review step",
    )
    parser.add_argument(
        "-s", "--summary",
        action="store_true",
        help="Enable chapter summary generation",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print full AI request/response to console",
    )
    parser.add_argument(
        "--from",
        dest="start_chapter",
        type=int,
        default=0,
        help="Start from this chapter number",
    )
    parser.add_argument(
        "--to",
        dest="end_chapter",
        type=int,
        default=0,
        help="Stop at this chapter number (0 = all)",
    )

    args = parser.parse_args()

    novel_name = args.novel

    # Apply overrides
    if args.provider:
        config.llm_provider = args.provider
    if args.review:
        config.enable_review = True
    if args.summary:
        config.enable_summary = True

    if args.verbose:
        from src.services.logger import set_verbose
        set_verbose(True)

    print_banner()

    if not check_provider():
        sys.exit(1)

    # Scan and find untranslated chapters
    chapters = scan_chapters(novel_name)
    if not chapters:
        print(f"{RED}✗ No chapter files found in input/{novel_name}/{RESET}")
        print(f"  Expected format: input/{novel_name}/chapter_1.txt{RESET}")
        sys.exit(1)

    untranslated = find_untranslated(novel_name, chapters)

    # Apply range filters
    if args.start_chapter > 0:
        untranslated = [ch for ch in untranslated if ch >= args.start_chapter]
    if args.end_chapter > 0:
        untranslated = [ch for ch in untranslated if ch <= args.end_chapter]

    if not untranslated:
        print(f"{GREEN}✓ All {len(chapters)} chapters already translated.{RESET}")
        return

    total = len(untranslated)
    print(f"{DIM}📕 {novel_name}: {len(chapters)} chapters found, {total} to translate{RESET}")
    print(f"{DIM}   Chapters: {untranslated[0]}-{untranslated[-1]}{RESET}")
    print()

    # Load source language from glossary if not specified
    language = args.lang
    if not language:
        from src.services.glossary import load_source_language
        language = load_source_language(novel_name)
        if language:
            print(f"{DIM}🌐 Language: {language} (from glossary){RESET}")
        else:
            print(f"{DIM}🌐 Language: auto-detect{RESET}")
    else:
        print(f"{DIM}🌐 Language: {language} (specified){RESET}")
    print()

    # Translate chapters
    success_count = 0
    fail_count = 0
    overall_start = time.time()

    for i, chapter_num in enumerate(untranslated, 1):
        chapter_path = chapters[chapter_num]
        print(f"{CYAN}[{i}/{total}] Chapter {chapter_num}{RESET}")

        try:
            if translate_file(chapter_path, novel_name, chapter_num, language):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"  {RED}✗ Failed: {e}{RESET}")
            fail_count += 1

    overall_elapsed = time.time() - overall_start

    print()
    print(f"{GREEN}{'═' * 54}")
    print(f"  ✅ Batch complete!")
    print(f"{'═' * 54}{RESET}")
    print(f"  {DIM}Translated: {success_count}/{total}{RESET}")
    if fail_count:
        print(f"  {RED}Failed: {fail_count}{RESET}")
    print(f"  {DIM}Total time: {overall_elapsed:.1f}s{RESET}")
    print()


if __name__ == "__main__":
    main()
