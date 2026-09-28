"""Unit tests for non-Gemini provider response adapters."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from utils.provider_clients import (  # noqa: E402
    AnthropicModelWrapper,
    OpenAIModelWrapper,
)


class Recorder:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def test_openai_wrapper_normalizes_text_and_usage():
    raw = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="OpenAI answer"))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
    )
    recorder = Recorder(raw)
    client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    model = OpenAIModelWrapper(client, "gpt-test", temperature=0.2)

    response = model.generate_content("topic", {"max_output_tokens": 321})

    assert response.text == "OpenAI answer"
    assert response.candidates[0].content.parts[0].text == "OpenAI answer"
    assert response.usage_metadata.prompt_token_count == 12
    assert response.usage_metadata.candidates_token_count == 7
    assert recorder.kwargs["max_completion_tokens"] == 321
    assert recorder.kwargs["messages"] == [{"role": "user", "content": "topic"}]


def test_anthropic_wrapper_joins_text_blocks_and_normalizes_usage():
    raw = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Claude "),
            SimpleNamespace(type="tool_use", text=None),
            SimpleNamespace(type="text", text="answer"),
        ],
        usage=SimpleNamespace(input_tokens=9, output_tokens=4),
    )
    recorder = Recorder(raw)
    client = SimpleNamespace(messages=recorder)
    model = AnthropicModelWrapper(client, "claude-test", temperature=0.3)

    response = model.generate_content(["same", "topic"])

    assert response.text == "Claude answer"
    assert response.usage_metadata.total_token_count == 13
    assert recorder.kwargs["messages"] == [{"role": "user", "content": "same\ntopic"}]
    assert recorder.kwargs["max_tokens"] == 8192
