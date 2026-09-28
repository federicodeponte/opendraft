"""Provider adapters exposing OpenDraft's ``generate_content`` interface.

The pipeline historically consumed Gemini response objects directly.  These
small adapters normalize OpenAI and Anthropic responses to the subset of that
interface used by OpenDraft, which keeps provider-specific code out of the
agent and phase implementations.
"""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class _TextPart:
    text: str


@dataclass
class _Content:
    parts: List[_TextPart]


@dataclass
class _Candidate:
    content: _Content
    finish_reason: int = 1


@dataclass
class _UsageMetadata:
    prompt_token_count: int = 0
    candidates_token_count: int = 0

    @property
    def total_token_count(self) -> int:
        return self.prompt_token_count + self.candidates_token_count


class ProviderResponse:
    """Minimal Gemini-compatible response consumed by the pipeline."""

    def __init__(self, text: str, input_tokens: int = 0, output_tokens: int = 0):
        self.text = text
        self.candidates = [_Candidate(content=_Content(parts=[_TextPart(text=text)]))]
        self.usage_metadata = _UsageMetadata(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
        )


def _prompt_text(prompt: Any) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        return "\n".join(str(item) for item in prompt)
    return str(prompt)


def _generation_value(generation_config: Any, name: str, default: Any = None) -> Any:
    if generation_config is None:
        return default
    if isinstance(generation_config, dict):
        return generation_config.get(name, default)
    return getattr(generation_config, name, default)


class OpenAIModelWrapper:
    """Adapt an ``openai.OpenAI`` client to ``generate_content``."""

    def __init__(self, client: Any, model_name: str, temperature: float = 0.7):
        self.client = client
        self.model_name = model_name
        self.default_temperature = temperature

    def generate_content(
        self,
        prompt: Any,
        generation_config: Any = None,
        safety_settings: Any = None,
    ) -> ProviderResponse:
        del safety_settings
        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": _prompt_text(prompt)}],
            "temperature": _generation_value(
                generation_config, "temperature", self.default_temperature
            ),
        }
        max_tokens = _generation_value(generation_config, "max_output_tokens")
        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens

        response = self.client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


class AnthropicModelWrapper:
    """Adapt an ``anthropic.Anthropic`` client to ``generate_content``."""

    def __init__(
        self,
        client: Any,
        model_name: str,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
    ):
        self.client = client
        self.model_name = model_name
        self.default_temperature = temperature
        self.default_max_output_tokens = max_output_tokens

    def generate_content(
        self,
        prompt: Any,
        generation_config: Any = None,
        safety_settings: Any = None,
    ) -> ProviderResponse:
        del safety_settings
        max_tokens: Optional[int] = _generation_value(
            generation_config, "max_output_tokens", self.default_max_output_tokens
        )
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens or self.default_max_output_tokens,
            temperature=_generation_value(
                generation_config, "temperature", self.default_temperature
            ),
            messages=[{"role": "user", "content": _prompt_text(prompt)}],
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        )
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            text=text,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
