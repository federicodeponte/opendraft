#!/usr/bin/env python3
"""
ABOUTME: Model pricing data for token cost estimation
ABOUTME: Ported from OpenPaper — sync adaptation for OpenDraft
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPricing:
    """Pricing per 1M tokens for a given model."""
    input_price: float   # USD per 1M input tokens
    output_price: float  # USD per 1M output tokens
    name: str = ""
    display_name: str = ""
    provider: str = ""


# Pricing updated February 2026
MODEL_PRICING: Dict[str, ModelPricing] = {
    # Gemini 3 family (Preview)
    "gemini-3.1-pro-preview": ModelPricing(
        input_price=2.00,
        output_price=12.00,
        name="Gemini 3 Pro Preview",
        display_name="Gemini 3.0 Pro (Preview)",
        provider="gemini",
    ),
    "gemini-3-flash-preview": ModelPricing(
        input_price=0.50,
        output_price=3.00,
        name="Gemini 3 Flash Preview",
        display_name="Gemini 3.0 Flash (Preview)",
        provider="gemini",
    ),
    # Gemini 2.5 family
    "gemini-2.5-pro": ModelPricing(
        input_price=1.25,
        output_price=10.00,
        name="Gemini 2.5 Pro",
        display_name="Gemini 2.5 Pro",
        provider="gemini",
    ),
    "gemini-2.5-pro-preview-05-06": ModelPricing(
        input_price=1.25,
        output_price=10.00,
        name="Gemini 2.5 Pro Preview",
        display_name="Gemini 2.5 Pro Preview",
        provider="gemini",
    ),
    "gemini-2.5-flash": ModelPricing(
        input_price=0.15,
        output_price=0.60,
        name="Gemini 2.5 Flash",
        display_name="Gemini 2.5 Flash",
        provider="gemini",
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        input_price=0.10,
        output_price=0.40,
        name="Gemini 2.5 Flash Lite",
        display_name="Gemini 2.5 Flash Lite",
        provider="gemini",
    ),
    "gemini-2.5-flash-preview-04-17": ModelPricing(
        input_price=0.15,
        output_price=0.60,
        name="Gemini 2.5 Flash Preview",
        display_name="Gemini 2.5 Flash Preview",
        provider="gemini",
    ),
    # Gemini 2.0 family
    "gemini-2.0-flash": ModelPricing(
        input_price=0.10,
        output_price=0.40,
        name="Gemini 2.0 Flash",
        display_name="Gemini 2.0 Flash",
        provider="gemini",
    ),
    "gemini-2.0-flash-exp": ModelPricing(
        input_price=0.10,
        output_price=0.40,
        name="Gemini 2.0 Flash (Experimental)",
        display_name="Gemini 2.0 Flash (Experimental)",
        provider="gemini",
    ),
    "gemini-2.0-flash-lite": ModelPricing(
        input_price=0.075,
        output_price=0.30,
        name="Gemini 2.0 Flash Lite",
        display_name="Gemini 2.0 Flash Lite",
        provider="gemini",
    ),
    # Gemini 1.5 family (legacy)
    "gemini-1.5-pro": ModelPricing(
        input_price=1.25,
        output_price=10.00,
        name="Gemini 1.5 Pro",
        display_name="Gemini 1.5 Pro",
        provider="gemini",
    ),
    "gemini-1.5-flash": ModelPricing(
        input_price=0.10,
        output_price=0.40,
        name="Gemini 1.5 Flash",
        display_name="Gemini 1.5 Flash",
        provider="gemini",
    ),
    # OpenAI models
    "gpt-4.1-nano": ModelPricing(
        input_price=0.30,
        output_price=1.20,
        name="GPT-4.1 Nano",
        display_name="GPT-4.1 Nano",
        provider="openai",
    ),
    "gpt-4": ModelPricing(
        input_price=30.0,
        output_price=60.0,
        name="GPT-4",
        display_name="GPT-4",
        provider="openai",
    ),
    "gpt-4-turbo": ModelPricing(
        input_price=10.0,
        output_price=30.0,
        name="GPT-4 Turbo",
        display_name="GPT-4 Turbo",
        provider="openai",
    ),
    "gpt-3.5-turbo": ModelPricing(
        input_price=0.50,
        output_price=1.50,
        name="GPT-3.5 Turbo",
        display_name="GPT-3.5 Turbo",
        provider="openai",
    ),
}


def get_model_pricing(model_name: str) -> Optional[ModelPricing]:
    """
    Look up pricing for a model name.

    Supports partial matching: 'gemini-3-pro' matches 'gemini-3.1-pro-preview'.
    Returns None if no match found.
    """
    # Exact match first
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]

    # Partial / prefix match
    for key, pricing in MODEL_PRICING.items():
        if key.startswith(model_name) or model_name.startswith(key):
            return pricing

    return None


def get_provider_for_model(model_name: str) -> Optional[str]:
    """
    Determine the provider for a given model name.

    Args:
        model_name: Name of the model

    Returns:
        Provider string ('gemini', 'openai') or None if not found
    """
    pricing = get_model_pricing(model_name)
    if pricing and pricing.provider:
        return pricing.provider

    # Heuristic fallback based on name patterns
    model_lower = model_name.lower()
    if "gemini" in model_lower:
        return "gemini"
    elif "gpt" in model_lower or "openai" in model_lower:
        return "openai"
    elif "claude" in model_lower:
        return "anthropic"

    return None


def calculate_token_cost(
    input_tokens: int, output_tokens: int, model_pricing: ModelPricing
) -> float:
    """
    Calculate the cost for a given number of tokens.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model_pricing: ModelPricing object

    Returns:
        Cost in USD
    """
    input_cost = (input_tokens / 1_000_000) * model_pricing.input_price
    output_cost = (output_tokens / 1_000_000) * model_pricing.output_price
    return input_cost + output_cost
