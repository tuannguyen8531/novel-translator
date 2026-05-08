"""LLM provider factory — creates and caches the global LLM instance."""

from src.config import config
from src.services.llm.base import BaseProvider
from src.services.llm.ollama import OllamaProvider
from src.services.llm.gemini import GeminiProvider
from src.services.llm.openrouter import OpenRouterProvider
from src.services.llm.fallback import FallbackProvider

_PROVIDER_MAP: dict[str, type[BaseProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}

_llm_instance: BaseProvider | None = None


def _create_provider(name: str) -> BaseProvider:
    """Create a provider instance by name."""
    provider_cls = _PROVIDER_MAP.get(name)
    if provider_cls is None:
        raise ValueError(f"Unknown LLM provider: {name}")
    return provider_cls()


def get_llm() -> BaseProvider:
    """Get the global LLM service instance, with fallback if configured."""
    global _llm_instance
    if _llm_instance is None:
        primary = _create_provider(config.llm_provider)

        # Wrap with fallback if configured and different from primary
        if config.fallback_provider and config.fallback_provider != config.llm_provider:
            fallback = _create_provider(config.fallback_provider)
            _llm_instance = FallbackProvider(primary, fallback)
        else:
            _llm_instance = primary

    return _llm_instance


def reset_llm():
    """Reset the global LLM instance (useful after config changes)."""
    global _llm_instance
    if _llm_instance is not None:
        _llm_instance.close()
    _llm_instance = None
