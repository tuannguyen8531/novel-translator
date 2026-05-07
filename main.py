"""
Novel Translator — CLI Entry Point

Usage:
    uv run python main.py --input input/chapter1.txt --novel "my-novel" --chapter 1
    uv run python main.py --input input/chapter1.txt --novel "my-novel" --chapter 1 --lang chinese
    uv run python main.py --input input/chapter1.txt --novel "my-novel" --chapter 1 --provider gemini
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

# Suppress LangChain internal deprecation warnings (not actionable by us)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")
warnings.filterwarnings("ignore", message=".*LangChainPendingDeprecationWarning.*")

from src.config import config
from src.graph.builder import build_graph


# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def print_banner():
    """Print the application banner."""
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════╗
║         📚  Novel Translator  📚                     ║
║    Trung / Hàn / Nhật → Tiếng Việt                   ║
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
                # Check without tag
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


def translate_file(input_path: str, novel_name: str, chapter_number: int, language: str = ""):
    """Run the translation pipeline on a file."""
    # Read input
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"{RED}✗ Input file not found: {input_path}{RESET}")
        sys.exit(1)

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

    # Build and run graph
    graph = build_graph()

    start_time = time.time()

    result = graph.invoke({
        "source_text": source_text,
        "source_language": language,
        "novel_name": novel_name,
        "chapter_number": chapter_number,
        # Initialize empty state fields
        "translation_rules": "",
        "glossary": {},
        "previous_summary": "",
        "chunks": [],
        "current_chunk_index": 0,
        "translated_chunks": [],
        "current_translation": "",
        "review_score": 0.0,
        "review_feedback": "",
        "retry_count": 0,
        "new_terms": {},
        "chapter_summary": "",
        "final_translation": "",
    })

    elapsed = time.time() - start_time

    # Save output
    output_dir = Path("output") / novel_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"chapter_{chapter_number:03d}.txt"

    final_text = result.get("final_translation", "")
    output_file.write_text(final_text, encoding="utf-8")

    # Print results
    print()
    print(f"{GREEN}{'═' * 54}")
    print(f"  ✅ Translation complete!")
    print(f"{'═' * 54}{RESET}")
    print(f"  {DIM}Output:     {output_file}{RESET}")
    print(f"  {DIM}Length:     {len(final_text)} chars{RESET}")
    print(f"  {DIM}Time:       {elapsed:.1f}s{RESET}")
    print(f"  {DIM}Chunks:     {len(result.get('chunks', []))}{RESET}")

    new_terms = result.get("new_terms", {})
    if new_terms:
        print(f"  {DIM}New terms:  {len(new_terms)}{RESET}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="📚 Novel Translator — Trung/Hàn/Nhật → Tiếng Việt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1
  uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1 -l chinese
  uv run python main.py -i input/chapter1.txt -n "my-novel" -c 1 -p gemini
        """,
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input .txt file")
    parser.add_argument("-n", "--novel", required=True, help="Novel name (for glossary)")
    parser.add_argument("-c", "--chapter", type=int, required=True, help="Chapter number")
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
        "--skip-review",
        action="store_true",
        default=None,
        help="Skip the review step (faster, no quality check)",
    )

    args = parser.parse_args()

    # Override provider if specified
    if args.provider:
        config.llm_provider = args.provider
        # Re-create LLM service with new provider
        from src.services import llm as llm_module
        llm_module.llm = llm_module.LLMService(provider=args.provider)

    # Override skip_review if specified via CLI
    if args.skip_review:
        config.skip_review = True

    print_banner()

    if not check_provider():
        sys.exit(1)

    print()
    translate_file(args.input, args.novel, args.chapter, args.lang)


if __name__ == "__main__":
    main()
