"""The litellm provider: routing, the Gemini-shaped response, and credential handling.

LiteLLM is stubbed, so nothing here makes a network call.
"""
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from engine.config import AppConfig, ModelConfig
from engine.utils import provider_adapters
from engine.utils.agent_runner import setup_model
from engine.utils.provider_adapters import LiteLLMModelWrapper


def _completion(text="Draft section", prompt_tokens=11, completion_tokens=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture
def litellm(monkeypatch):
    calls = []
    sdk = types.ModuleType("litellm")
    sdk.calls = calls
    sdk.reply = _completion()

    def completion(**kwargs):
        calls.append(kwargs)
        return sdk.reply

    sdk.completion = completion
    monkeypatch.setitem(sys.modules, "litellm", sdk)
    return sdk


def test_model_resolution_reads_litellm_model(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "litellm")
    monkeypatch.setenv("LITELLM_MODEL", "vertex_ai/gemini-2.5-flash")
    assert ModelConfig().model_name == "vertex_ai/gemini-2.5-flash"


def test_a_missing_model_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "litellm")
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="LITELLM_MODEL is required"):
        ModelConfig()


def test_setup_model_routes_to_the_litellm_wrapper(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "litellm")
    monkeypatch.setenv("LITELLM_MODEL", "bedrock/anthropic.claude-sonnet-4-6")
    config = AppConfig()
    with patch("engine.utils.agent_runner.get_config", return_value=config):
        model = setup_model()
    assert isinstance(model, LiteLLMModelWrapper)
    assert model.model_name == "bedrock/anthropic.claude-sonnet-4-6"
    # LiteLLM reads each provider's own credentials, so no key is required up front.
    config.validate_api_keys()
    assert config.has_api_key is True


def test_adapter_returns_an_agent_compatible_response(litellm):
    result = LiteLLMModelWrapper("vertex_ai/gemini-2.5-flash").generate_content(
        ["first", "second"], {"temperature": 0.2, "max_output_tokens": 500}
    )
    request = litellm.calls[0]
    assert request["model"] == "vertex_ai/gemini-2.5-flash"
    assert request["messages"] == [{"role": "user", "content": "first\nsecond"}]
    assert (request["temperature"], request["max_tokens"]) == (0.2, 500)
    assert request["drop_params"] is True
    assert "api_base" not in request and "api_key" not in request
    assert result.text == "Draft section"
    assert result.candidates[0].content.parts[0].text == "Draft section"
    assert result.usage_metadata.prompt_token_count == 11
    assert result.usage_metadata.candidates_token_count == 5


def test_override_key_and_proxy_endpoint_are_passed_only_when_set(litellm):
    LiteLLMModelWrapper("gpt-4.1-mini", api_key="sk-override", api_base="http://localhost:4000").generate_content("hi")
    request = litellm.calls[0]
    assert request["api_base"] == "http://localhost:4000"
    assert request["api_key"] == "sk-override"


def test_banners_are_suppressed_on_import(litellm):
    LiteLLMModelWrapper("gpt-4.1-mini").generate_content("hi")
    assert litellm.suppress_debug_info is True


def test_missing_sdk_names_the_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "litellm", None)
    with pytest.raises(ImportError, match=r"opendraft\[litellm\]"):
        provider_adapters._import_litellm()
