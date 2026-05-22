"""
Novel Translator — CLI Entry Point

Usage:
    uv run python main.py -i input/my-novel/chapter_1.txt
    uv run python main.py -i input/my-novel/chapter_1.txt --lang chinese
    uv run python main.py -i input/my-novel/chapter_1.txt --provider gemini
"""

import argparse
import re
import sys
import time
import warnings
from pathlib import Path

from src.config import config
from src.graph.builder import build_graph
from src.models.state import initial_state
from src.services.logger import log_error
from src.utils.display import print_banner, check_provider, RED, GREEN, YELLOW, DIM, RESET
from src.utils.text import normalize_paragraph_spacing



def _get_output_dir(novel_name: str) -> Path:
    if config.novel_share_dir:
        return Path(config.novel_share_dir) / novel_name / "output"
    return Path("output") / novel_name


def parse_input_path(input_path: str) -> tuple[str, str, int]:
    """Parse novel name and chapter number from file path.

    Expected formats:
      - {base}/{novel}/chapter_{number}.txt (local input/ dir)
      - {base}/{novel}/input/chapter_{number}.txt (shared dir)
    Returns: (full_path, novel_name, chapter_number)
    """
    path = Path(input_path)
    if not path.exists():
        print(f"{RED}✗ Input file not found: {input_path}{RESET}")
        sys.exit(1)

    # Handle shared dir pattern: .../{novel}/input/chapter_N.txt
    if path.parent.name == "input":
        novel_name = path.parent.parent.name
        match = re.match(r"^chapter_(\d+)\.txt$", path.name)
        if match and novel_name:
            return str(path), novel_name, int(match.group(1))

    match = re.search(r"([^/\\]+)[/\\]chapter_(\d+)\.txt$", str(path))
    if not match:
        print(f"{RED}✗ Invalid file format. Expected: {{novel}}/chapter_{{number}}.txt{RESET}")
        print(f"  Got: {input_path}{RESET}")
        sys.exit(1)

    novel_name = match.group(1)
    chapter_number = int(match.group(2))
    return str(path), novel_name, chapter_number


def translate_file(input_path: str, novel_name: str, chapter_number: int, language: str = "") -> None:
    """Run the translation pipeline on a file."""
    input_file = Path(input_path)
    source_text = input_file.read_text(encoding="utf-8")
    if not source_text.strip():
        print(f"{RED}✗ Input file is empty: {input_path}{RESET}")
        sys.exit(1)

    print(f"{DIM}📄 Input: {input_path} ({len(source_text)} chars){RESET}")
    print(f"{DIM}📕 Novel: {novel_name} · Chapter {chapter_number}{RESET}")
    if language:
        print(f"{DIM}🌐 Language: {language} (specified){RESET}")
    else:
        print(f"{DIM}🌐 Language: auto-detect{RESET}")
    print()

    graph = build_graph()
    start_time = time.time()

    try:
        result = graph.invoke(initial_state(
            source_text=source_text,
            source_language=language,
            novel_name=novel_name,
            chapter_number=chapter_number,
        ))
    except Exception as e:
        log_error(f"Translation failed for chapter {chapter_number}", e, chapter=chapter_number, novel=novel_name)
        print(f"{RED}✗ Translation failed: {e}{RESET}")
        sys.exit(1)

    elapsed = time.time() - start_time

    output_dir = _get_output_dir(novel_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"chapter_{chapter_number:03d}.txt"

    final_text = result.get("final_translation", "")
    normalized_text = normalize_paragraph_spacing(final_text)
    output_file.write_text(normalized_text, encoding="utf-8")

    print()
    print(f"{GREEN}{'═' * 54}")
    print(f"  ✅ Translation complete!")
    print(f"{'═' * 54}{RESET}")
    print(f"  {DIM}Output:     {output_file}{RESET}")
    print(f"  {DIM}Length:     {len(normalized_text)} chars{RESET}")
    print(f"  {DIM}Time:       {elapsed:.1f}s{RESET}")
    print(f"  {DIM}Chunks:     {len(result.get('chunks', []))}{RESET}")

    new_terms = result.get("new_terms", {})
    if new_terms:
        print(f"  {DIM}New terms:  {len(new_terms)}{RESET}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="📚 Novel Translator — Trung/Hàn/Nhật → Tiếng Việt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py -i input/my-novel/chapter_1.txt
  uv run python main.py -i input/my-novel/chapter_1.txt --lang chinese
  uv run python main.py -i input/my-novel/chapter_1.txt --provider gemini
        """,
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to input file (format: input/{novel}/chapter_{number}.txt)",
    )
    parser.add_argument(
        "-l", "--lang",
        choices=["chinese", "korean", "japanese"],
        default="",
        help="Source language (auto-detect if not specified)",
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "gemini", "openrouter"],
        default=None,
        help="LLM provider (overrides .env setting)",
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

    args = parser.parse_args()

    input_path, novel_name, chapter_number = parse_input_path(args.input)

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

    print()
    translate_file(input_path, novel_name, chapter_number, args.lang)


if __name__ == "__main__":
    main()
