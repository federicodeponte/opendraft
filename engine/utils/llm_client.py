#!/usr/bin/env python3
"""
ABOUTME: Provider-agnostic LLM client wrappers for OpenDraft.
ABOUTME: Normalizes Gemini/OpenAI responses behind a single generate_content() interface.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Optional

try:
    from config import get_config, DEFAULT_OPENAI_MODEL, DEFAULT_GEMINI_MODEL
except ImportError:  # pragma: no cover - package-relative fallback
    from ..config import get_config, DEFAULT_OPENAI_MODEL, DEFAULT_GEMINI_MODEL

try:
    from .gemini_client import GeminiModelWrapper
except ImportError:  # pragma: no cover - direct-module fallback
    from utils.gemini_client import GeminiModelWrapper


class _ResponseShim:
    """Minimal response object that looks like google.genai responses."""

    def __init__(self, text: str):
        part = SimpleNamespace(text=text)
        content = SimpleNamespace(parts=[part])
        candidate = SimpleNamespace(finish_reason=1, content=content)
        self.text = text
        self.candidates = [candidate]


class OpenAIModelWrapper:
    """OpenAI chat-completions wrapper with Gemini-like surface area."""

    def __init__(self, client: Any, model_name: str, temperature: float = 0.7):
        self.client = client
        self.model_name = model_name
        self.default_temperature = temperature

    def generate_content(self, prompt: Any, generation_config: Any = None, safety_settings: Any = None) -> Any:
        _ = safety_settings
        config: dict[str, Any] = {
            "temperature": self.default_temperature,
        }

        if generation_config:
            if hasattr(generation_config, "temperature") and generation_config.temperature is not None:
                config["temperature"] = generation_config.temperature
            if hasattr(generation_config, "max_output_tokens") and generation_config.max_output_tokens:
                config["max_tokens"] = generation_config.max_output_tokens
            if isinstance(generation_config, dict):
                if "temperature" in generation_config and generation_config["temperature"] is not None:
                    config["temperature"] = generation_config["temperature"]
                if "max_output_tokens" in generation_config and generation_config["max_output_tokens"]:
                    config["max_tokens"] = generation_config["max_output_tokens"]
                if generation_config.get("response_mime_type") == "application/json":
                    config["response_format"] = {"type": "json_object"}

        if isinstance(prompt, list):
            contents = "\n".join(str(item) for item in prompt)
        else:
            contents = str(prompt)

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": contents}],
            **config,
        )
        text = (response.choices[0].message.content or "").strip()
        return _ResponseShim(text)


def get_active_provider() -> str:
    cfg = get_config()
    provider = (cfg.model.provider or os.getenv("AI_PROVIDER", "gemini")).strip().lower()
    return provider


def build_model_client(model_override: Optional[str] = None, provider_override: Optional[str] = None) -> Any:
    """Return a Gemini-like client for the active provider."""
    cfg = get_config()
    provider = (provider_override or cfg.model.provider or os.getenv("AI_PROVIDER", "gemini")).strip().lower()
    if provider in {"codex", "openai-codex"}:
        provider = "openai"

    if provider == "openai":
        model_name = (
            model_override
            or os.getenv("OPENAI_MODEL")
            or cfg.model.model_name
            or DEFAULT_OPENAI_MODEL
        )
        if "gemini" in model_name.lower():
            model_name = os.getenv("OPENAI_MODEL") or cfg.model.model_name or DEFAULT_OPENAI_MODEL
    else:
        model_name = (
            model_override
            or os.getenv("GEMINI_MODEL")
            or cfg.model.model_name
            or DEFAULT_GEMINI_MODEL
        )
        if "gpt" in model_name.lower() or "openai" in model_name.lower():
            model_name = os.getenv("GEMINI_MODEL") or cfg.model.model_name or DEFAULT_GEMINI_MODEL

    if provider == "gemini":
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("google-genai not installed. Run: pip install google-genai>=1.0.0") from exc

        api_key = cfg.google_api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY required for Gemini models")
        client = genai.Client(api_key=api_key)
        return GeminiModelWrapper(client, model_name, temperature=cfg.model.temperature)

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai not installed. Run: pip install openai>=1.0.0") from exc

        api_key = cfg.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI/Codex models")
        client = OpenAI(api_key=api_key)
        return OpenAIModelWrapper(client, model_name, temperature=cfg.model.temperature)

    if provider == "claude":
        raise ValueError("Claude provider is not wired into the OpenDraft runtime yet")

    raise ValueError(f"Unsupported AI provider: {provider}")
