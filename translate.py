"""
Novel Translator — Batch Translate CLI

Usage:
    uv run translate my-novel
    uv run translate my-novel -l chinese
    uv run translate my-novel -p gemini -r -s
"""

import argparse
import json
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
REPORT_DIR = Path("reports")
PROGRESS_DIR = Path(".progress")

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


def _progress_path(novel_name: str) -> Path:
    return PROGRESS_DIR / f"{novel_name}.json"


def load_progress(novel_name: str) -> dict:
    """Load chapter-level progress state."""
    path = _progress_path(novel_name)
    if not path.exists():
        return {"completed": [], "failed": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"completed": [], "failed": []}


def save_progress(novel_name: str, progress: dict) -> None:
    """Save chapter-level progress state."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    normalized = {
        "completed": sorted(set(progress.get("completed", []))),
        "failed": sorted(set(progress.get("failed", []))),
    }
    _progress_path(novel_name).write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")


def _report_path(novel_name: str, chapter_number: int) -> Path:
    return REPORT_DIR / novel_name / f"chapter_{chapter_number:03d}.json"


def save_quality_report(novel_name: str, chapter_number: int, report: dict) -> None:
    """Persist a chapter quality report."""
    report_path = _report_path(novel_name, chapter_number)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


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

    quality_report = {
        "chapter": chapter_number,
        "output_chars": len(final_text),
        "elapsed_seconds": round(elapsed, 3),
        "new_terms_count": new_terms_count,
        "new_characters_count": len(result.get("new_characters", {}).get("entities", {})),
        "chunks": result.get("quality_reports", []),
    }
    save_quality_report(novel_name, chapter_number, quality_report)

    return True, len(final_text), elapsed, new_terms_count


def glossary_main(argv: list[str]) -> None:
    """Manage per-novel glossary data."""
    from src.services.glossary import (
        load_glossary_data,
        remove_glossary_term,
        save_character_pronoun,
        save_glossary,
    )

    parser = argparse.ArgumentParser(description="Manage novel glossary data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List glossary terms")
    list_parser.add_argument("novel")

    add_parser = subparsers.add_parser("add", help="Add or update a glossary term")
    add_parser.add_argument("novel")
    add_parser.add_argument("original")
    add_parser.add_argument("translated")

    remove_parser = subparsers.add_parser("remove", help="Remove a glossary term")
    remove_parser.add_argument("novel")
    remove_parser.add_argument("original")

    export_parser = subparsers.add_parser("export", help="Print full glossary JSON")
    export_parser.add_argument("novel")

    character_parser = subparsers.add_parser("characters", help="List character memory")
    character_parser.add_argument("novel")

    pronoun_parser = subparsers.add_parser("pronoun", help="Set a character pronoun")
    pronoun_parser.add_argument("novel")
    pronoun_parser.add_argument("original")
    pronoun_parser.add_argument("pronoun")

    args = parser.parse_args(argv)

    if args.command == "list":
        terms = load_glossary_data(args.novel).get("terms", {})
        if not terms:
            print(f"{DIM}No glossary terms for {args.novel}.{RESET}")
            return
        for original, translated in sorted(terms.items()):
            print(f"{original}\t{translated}")
        return

    if args.command == "add":
        save_glossary(args.novel, {args.original: args.translated})
        print(f"{GREEN}✓ Added glossary term:{RESET} {args.original} → {args.translated}")
        return

    if args.command == "remove":
        removed = remove_glossary_term(args.novel, args.original)
        if removed:
            print(f"{GREEN}✓ Removed glossary term:{RESET} {args.original}")
        else:
            print(f"{YELLOW}Term not found:{RESET} {args.original}")
        return

    if args.command == "export":
        print(json.dumps(load_glossary_data(args.novel), ensure_ascii=False, indent=2))
        return

    if args.command == "characters":
        entities = load_glossary_data(args.novel).get("entities", {})
        if not entities:
            print(f"{DIM}No characters for {args.novel}.{RESET}")
            return
        for original, info in sorted(entities.items()):
            name_vi = info.get("name_vi", "")
            role = info.get("role", "")
            pronoun = info.get("pronoun", "")
            print(f"{original}\t{name_vi}\t{role}\t{pronoun}")
        return

    if args.command == "pronoun":
        updated = save_character_pronoun(args.novel, args.original, args.pronoun)
        if updated:
            print(f"{GREEN}✓ Updated pronoun:{RESET} {args.original} → {args.pronoun}")
        else:
            print(f"{YELLOW}Character not found:{RESET} {args.original}")


def main() -> None:
    global _graph

    if len(sys.argv) > 1 and sys.argv[1] == "glossary":
        glossary_main(sys.argv[2:])
        return

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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip chapters marked completed in .progress/{novel}.json",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Translate only chapters marked failed in .progress/{novel}.json",
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

    progress_state = load_progress(novel_name)
    if args.failed_only:
        failed = set(progress_state.get("failed", []))
        untranslated = [ch for ch in untranslated if ch in failed]
    elif args.resume:
        completed = set(progress_state.get("completed", []))
        untranslated = [ch for ch in untranslated if ch not in completed]

    if not untranslated:
        print(f"{GREEN}✓ All {len(chapters)} chapters already translated.{RESET}")
        return

    if args.dry_run:
        print(f"{DIM}📕 {novel_name}: {len(chapters)} chapters total, {len(untranslated)} would be translated{RESET}")
        print(f"{DIM}   Chapters: {', '.join(str(c) for c in untranslated)}{RESET}")
        return

    if not check_provider(config):
        sys.exit(1)

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
            save_progress(novel_name, progress_state)
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
                progress_state.setdefault("completed", []).append(chapter_num)
                progress_state["failed"] = [ch for ch in progress_state.get("failed", []) if ch != chapter_num]
                save_progress(novel_name, progress_state)
                terms_msg = f" [+ {new_terms_count} terms]" if new_terms_count > 0 else ""
                print(f"  {GREEN}✓ Ch.{chapter_num}{RESET} {DIM}→ {out_chars:,} chars · {elapsed:.1f}s{terms_msg}{RESET}")
            else:
                progress_state.setdefault("failed", []).append(chapter_num)
                save_progress(novel_name, progress_state)
        except Exception as e:
            progress.chapter_done(False)
            progress_state.setdefault("failed", []).append(chapter_num)
            save_progress(novel_name, progress_state)
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
