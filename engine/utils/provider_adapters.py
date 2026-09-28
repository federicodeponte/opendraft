"""Adapters exposing the response shape used by OpenDraft's existing agents."""

from types import SimpleNamespace
from typing import Any


def _prompt_text(prompt: Any) -> str:
    if isinstance(prompt, list):
        return "\n".join(str(part) for part in prompt)
    return str(prompt)


def _generation_options(config: Any, temperature: float) -> dict:
    if isinstance(config, dict):
        values = config
    elif config is None:
        values = {}
    else:
        values = vars(config)
    return {
        "temperature": values.get("temperature", temperature),
        "max_tokens": values.get("max_output_tokens", 8192),
    }


def _response(text: str, input_tokens: int = 0, output_tokens: int = 0):
    """Match the Gemini fields consumed by AgentRunner and DeepResearchPlanner."""
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(
            finish_reason=1,
            content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        )] if text else [],
        usage_metadata=SimpleNamespace(
            prompt_token_count=input_tokens,
            candidates_token_count=output_tokens,
            total_token_count=input_tokens + output_tokens,
        ),
    )


class ClaudeModelWrapper:
    def __init__(self, client, model_name: str, temperature: float = 0.7):
        self.client = client
        self.model_name = model_name
        self.temperature = temperature

    def generate_content(self, prompt, generation_config=None, safety_settings=None):
        options = _generation_options(generation_config, self.temperature)
        message = self.client.messages.create(
            model=self.model_name,
            max_tokens=options["max_tokens"],
            temperature=options["temperature"],
            messages=[{"role": "user", "content": _prompt_text(prompt)}],
        )
        text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        usage = getattr(message, "usage", None)
        return _response(text, getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))


class OpenAIModelWrapper:
    def __init__(self, client, model_name: str, temperature: float = 0.7):
        self.client = client
        self.model_name = model_name
        self.temperature = temperature

    def generate_content(self, prompt, generation_config=None, safety_settings=None):
        options = _generation_options(generation_config, self.temperature)
        completion = self.client.chat.completions.create(
            model=self.model_name,
            max_tokens=options["max_tokens"],
            temperature=options["temperature"],
            messages=[{"role": "user", "content": _prompt_text(prompt)}],
        )
        text = completion.choices[0].message.content or "" if completion.choices else ""
        usage = getattr(completion, "usage", None)
        return _response(text, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0))
