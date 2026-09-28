"""Provider routing and response compatibility without network calls."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from engine.config import AppConfig, ModelConfig
from engine.utils.provider_adapters import ClaudeModelWrapper, OpenAIModelWrapper
from engine.utils.agent_runner import setup_model


def test_claude_model_resolution_and_route(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example")
    config = AppConfig()
    assert config.model.model_name == "claude-sonnet-4-6"
    with patch("engine.utils.agent_runner.get_config", return_value=config), \
         patch("anthropic.Anthropic") as client_cls:
        model = setup_model()
    client_cls.assert_called_once_with(api_key="test-key", base_url="https://proxy.example")
    assert model.__class__.__name__ == "ClaudeModelWrapper"
    assert model.model_name == "claude-sonnet-4-6"


def test_claude_adapter_returns_agent_compatible_response():
    client = Mock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Research summary")],
        usage=SimpleNamespace(input_tokens=120, output_tokens=30),
    )
    result = ClaudeModelWrapper(client, "claude-sonnet-4-6").generate_content(
        ["first", "second"], {"temperature": 0.2, "max_output_tokens": 500}
    )
    client.messages.create.assert_called_once_with(
        model="claude-sonnet-4-6", max_tokens=500, temperature=0.2,
        messages=[{"role": "user", "content": "first\nsecond"}],
    )
    assert result.text == "Research summary"
    assert result.candidates[0].content.parts[0].text == result.text
    assert result.usage_metadata.prompt_token_count == 120


def test_openai_route_and_adapter(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")
    config = AppConfig()
    with patch("engine.utils.agent_runner.get_config", return_value=config), \
         patch("openai.OpenAI") as client_cls:
        model = setup_model()
    client_cls.assert_called_once_with(api_key="test-key", base_url="https://proxy.example/v1")
    assert model.__class__.__name__ == "OpenAIModelWrapper"
    model.client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Draft"))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
    )
    result = model.generate_content("Prompt")
    assert result.text == "Draft"
    assert result.usage_metadata.candidates_token_count == 4


def test_claude_requires_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("engine.utils.agent_runner.get_config", return_value=AppConfig()):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            setup_model()


def test_custom_models_allowed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_MODEL", "custom-claude")
    assert ModelConfig().model_name == "custom-claude"
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "custom-openai")
    assert ModelConfig().model_name == "custom-openai"
