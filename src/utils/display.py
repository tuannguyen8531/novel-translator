"""Display utilities — ANSI colors, banner, provider check."""

import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def _get_model_name(config) -> str:
    """Get the current model name based on provider."""
    if config.llm_provider == "ollama":
        return config.ollama_model
    elif config.llm_provider == "gemini":
        return config.gemini_model
    elif config.llm_provider == "openrouter":
        return config.openrouter_model
    return "unknown"


def print_banner(config) -> None:
    """Print the application banner."""
    print(f"""
{CYAN}╔══════════════════════════════════════════════════════╗
║         📚  Novel Translator  📚                     ║
║    Chinese / Korean / Japanese → Vietnamese          ║
╚══════════════════════════════════════════════════════╝{RESET}
{DIM}Provider: {config.llm_provider} · Model: {_get_model_name(config)} · Temp: {config.translation_temperature}{RESET}
""")


def check_provider(config) -> bool:
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
