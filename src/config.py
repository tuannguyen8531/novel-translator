"""
Configuration for Novel Translator.
Loads settings from .env file.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(interpolate=True)


@dataclass
class Config:
    """Application configuration."""

    # LLM Provider: "ollama" | "gemini" | "openrouter"
    llm_provider: str = "ollama"

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # Gemini API settings
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # OpenRouter API settings
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3-8b"

    # Translation settings
    translation_temperature: float = 0.3
    translation_max_tokens: int = 4096
    chunk_size: int = 1500
    chunk_overlap: int = 100
    review_threshold: float = 0.7
    max_retries: int = 2
    skip_review: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "qwen/qwen3-8b"),
            translation_temperature=float(os.getenv("TRANSLATION_TEMPERATURE", "0.3")),
            translation_max_tokens=int(os.getenv("TRANSLATION_MAX_TOKENS", "4096")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1500")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            review_threshold=float(os.getenv("REVIEW_THRESHOLD", "0.7")),
            max_retries=int(os.getenv("MAX_RETRIES", "2")),
            skip_review=os.getenv("SKIP_REVIEW", "false").lower() in ("true", "1", "yes"),
        )


config = Config.from_env()
