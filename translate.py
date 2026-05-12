"""
Novel Translator — Batch Translate CLI

Usage:
    uv run translate my-novel
    uv run translate my-novel -l chinese
    uv run translate my-novel -p gemini -r -s
"""

import argparse
import re
import signal
import sys
import time
from pathlib import Path

from src.config import config
from src.services.logger import log_error
from src.graph.builder import build_graph
from src.models.state import initial_state
from src.utils.progress import ProgressTracker
from src.utils.display import print_banner, check_provider, RED, GREEN, YELLOW, DIM, RESET

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")

_shutdown_requested = False
_graph = None


def _signal_handler(signum, frame) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\n{YELLOW}⚠ Shutting down gracefully...{DIM}")


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


def find_untranslated(novel_name: str, chapters: dict[int, Path], force: bool = False) -> list[int]:
    """Find chapters that exist in input but haven't been translated yet."""
    if force:
        return sorted(chapters.keys())

    output_dir = OUTPUT_DIR / novel_name
    translated = set()
    if output_dir.exists():
        for f in output_dir.iterdir():
            match = re.match(r"^chapter_(\d+)\.txt$", f.name)
            if match:
                translated.add(int(match.group(1)))
    return [ch for ch in chapters if ch not in translated]


def translate_file(input_path: Path, novel_name: str, chapter_number: int, language: str = "", graph=None) -> tuple[bool, int, float, int]:
    """Run the translation pipeline on a file. Returns (success, char_count, elapsed, new_terms_count)."""
    source_text = input_path.read_text(encoding="utf-8")
    if not source_text.strip():
        return False, 0, 0, 0

    if graph is None:
        graph = build_graph()

    start = time.time()

    result = graph.invoke(initial_state(
        source_text=source_text,
        source_language=language,
        novel_name=novel_name,
        chapter_number=chapter_number,
    ))

    elapsed = time.time() - start

    output_dir = OUTPUT_DIR / novel_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"chapter_{chapter_number:03d}.txt"

    final_text = result.get("final_translation", "")
    new_terms_count = len(result.get("new_terms", {}))
    output_file.write_text(final_text, encoding="utf-8")

    return True, len(final_text), elapsed, new_terms_count


def main() -> None:
    global _graph

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
        "--start",
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-translate already translated chapters",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List chapters to translate without actually translating",
    )

    args = parser.parse_args()

    novel_name = args.novel

    if args.provider:
        config.llm_provider = args.provider
    if args.review:
        config.enable_review = True
    if args.summary:
        config.enable_summary = True

    if args.verbose:
        from src.services.logger import set_verbose
        set_verbose(True)

    print_banner(config)

    if not check_provider(config):
        sys.exit(1)

    chapters = scan_chapters(novel_name)
    if not chapters:
        print(f"{RED}✗ No chapter files found in input/{novel_name}/{RESET}")
        print(f"  Expected format: input/{novel_name}/chapter_1.txt{RESET}")
        sys.exit(1)

    untranslated = find_untranslated(novel_name, chapters, force=args.force)

    if args.start_chapter > 0:
        untranslated = [ch for ch in untranslated if ch >= args.start_chapter]
    if args.end_chapter > 0:
        untranslated = [ch for ch in untranslated if ch <= args.end_chapter]

    if not untranslated:
        print(f"{GREEN}✓ All {len(chapters)} chapters already translated.{RESET}")
        return

    if args.dry_run:
        print(f"{DIM}📕 {novel_name}: {len(chapters)} chapters total, {len(untranslated)} would be translated{RESET}")
        print(f"{DIM}   Chapters: {', '.join(str(c) for c in untranslated)}{RESET}")
        return

    total = len(untranslated)
    print(f"{DIM}📕 {novel_name}: {len(chapters)} chapters found, {total} to translate{RESET}")
    print(f"{DIM}   Chapters: {untranslated[0]}-{untranslated[-1]}{RESET}")
    print()

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

    signal.signal(signal.SIGINT, _signal_handler)

    _graph = build_graph()
    progress = ProgressTracker(total, novel_name)

    for index, chapter_num in enumerate(untranslated, 1):
        if _shutdown_requested:
            print(f"\n{YELLOW}⚠ Interrupted at chapter {chapter_num}. Progress saved.{RESET}")
            break

        chapter_path = chapters[chapter_num]
        file_size = len(chapter_path.read_text(encoding="utf-8"))

        progress.start_chapter(index, chapter_num, file_size)

        try:
            success, out_chars, elapsed, new_terms_count = translate_file(
                chapter_path, novel_name, chapter_num, language, graph=_graph
            )
            progress.chapter_done(success)
            if success:
                terms_msg = f" [+ {new_terms_count} terms]" if new_terms_count > 0 else ""
                print(f"  {GREEN}✓ Ch.{chapter_num}{RESET} {DIM}→ {out_chars:,} chars · {elapsed:.1f}s{terms_msg}{RESET}")
        except Exception as e:
            progress.chapter_done(False)
            log_error(f"Translation failed for chapter {chapter_num}", e, chapter=chapter_num, novel=novel_name)
            print(f"  {RED}✗ Ch.{chapter_num}: {e}{RESET}")

    progress.print_summary()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("Top-level execution error", e)
        print(f"\n[Error] {e}")
        sys.exit(1)
