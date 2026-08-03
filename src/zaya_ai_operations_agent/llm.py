from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from .config import Settings


class LLMProvider:
    """Interface for LLM providers."""

    name: str = "base"

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Simple mock provider used in tests and local development."""

    name = "mock"

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        return f"mock-response:{model or 'default'}:{prompt[:40]}"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        if not self.api_key:
            return f"openai-disabled:{model or 'gpt-4o-mini'}"
        return f"openai:{model or 'gpt-4o-mini'}:{prompt[:40]}"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        if not self.api_key:
            return f"anthropic-disabled:{model or 'claude-3-5-sonnet'}"
        return f"anthropic:{model or 'claude-3-5-sonnet'}:{prompt[:40]}"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        if not self.api_key:
            return f"gemini-disabled:{model or 'gemini-1.5-pro'}"
        return f"gemini:{model or 'gemini-1.5-pro'}:{prompt[:40]}"


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or "http://localhost:11434"

    def generate(self, prompt: str, *, model: Optional[str] = None) -> str:
        return f"ollama:{model or 'llama3'}:{prompt[:40]}"


@dataclass(slots=True)
class LLMSettings:
    provider: str = "mock"
    model: str = "default"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"


class LLMProviderFactory:
    """Creates provider instances from environment-driven configuration."""

    @staticmethod
    def load_settings(settings: Optional[Settings] = None) -> LLMSettings:
        settings = settings or Settings()
        env_values = os.environ.copy()
        return LLMSettings(
            provider=env_values.get("LLM_PROVIDER") or settings.llm_provider or "mock",
            model=env_values.get("LLM_MODEL") or settings.llm_model or "default",
            openai_api_key=env_values.get("OPENAI_API_KEY") or settings.openai_api_key,
            anthropic_api_key=env_values.get("ANTHROPIC_API_KEY"),
            gemini_api_key=env_values.get("GEMINI_API_KEY"),
            ollama_base_url=env_values.get("OLLAMA_BASE_URL") or "http://localhost:11434",
        )

    @classmethod
    def create(cls, settings: Optional[LLMSettings] = None, provider_name: Optional[str] = None) -> LLMProvider:
        resolved_settings = settings or cls.load_settings()
        provider_name = provider_name or resolved_settings.provider
        provider_name = (provider_name or "mock").lower()
        if provider_name == "openai":
            return OpenAIProvider(resolved_settings.openai_api_key)
        if provider_name == "anthropic":
            return AnthropicProvider(resolved_settings.anthropic_api_key)
        if provider_name == "gemini":
            return GeminiProvider(resolved_settings.gemini_api_key)
        if provider_name == "ollama":
            return OllamaProvider(resolved_settings.ollama_base_url)
        return MockLLMProvider()
