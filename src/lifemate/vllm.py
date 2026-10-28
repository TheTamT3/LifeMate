"""Local vLLM/OpenAI-compatible model configuration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any


@dataclass(frozen=True)
class VLLMConfig:
    base_url: str = "http://127.0.0.1:8000/v1"
    model_name: str = "qwen3-4b"
    max_steps: int = 8

    def __post_init__(self) -> None:
        validate_loopback_url(self.base_url)
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")


def validate_loopback_url(base_url: str) -> str:
    """Accept only HTTP(S) endpoints hosted on the local machine."""

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("vLLM endpoint must use a loopback host")
    if not parsed.netloc:
        raise ValueError("vLLM endpoint must include a port or authority")
    return base_url


def create_vllm_model(config: VLLMConfig) -> Any:
    """Build the PydanticAI OpenAI model without making a network request."""

    validate_loopback_url(config.base_url)
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
    except ImportError as exc:  # pragma: no cover - exercised in runtime env
        raise RuntimeError(
            "PydanticAI OpenAI support is required; install pydantic-ai[openai]"
        ) from exc

    provider = OpenAIProvider(base_url=config.base_url, api_key="local")
    return OpenAIChatModel(config.model_name, provider=provider)
