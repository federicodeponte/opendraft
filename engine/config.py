#!/usr/bin/env python3
"""
ABOUTME: Centralized configuration management for OpenDraft
ABOUTME: Single source of truth for all settings, models, and environment variables
"""

import os
from dataclasses import dataclass, field
from typing import Literal, Optional
from pathlib import Path


# Try to load environment variables from .env files
# Priority: .env.local > .env (local overrides default)
try:
    from dotenv import load_dotenv

    # Get directory where config.py is located
    config_dir = Path(__file__).parent

    # Load .env first (defaults)
    env_path = config_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)

    # Load .env.local second (overrides, gitignored)
    env_local_path = config_dir / '.env.local'
    if env_local_path.exists():
        load_dotenv(env_local_path, override=True)

except ImportError:
    # dotenv is optional - will use system environment variables
    pass


@dataclass
class ModelConfig:
    """
    Model configuration with sensible defaults.

    Supports Gemini models with configurable parameters.
    """
    provider: Literal['gemini', 'claude', 'openai'] = field(
        default_factory=lambda: os.getenv('AI_PROVIDER', 'gemini')
    )
    model_name: str = field(
        default_factory=lambda: (
            os.getenv('OPENAI_MODEL', 'gpt-4.1-nano')
            if os.getenv('AI_PROVIDER') == 'openai'
            else os.getenv('GEMINI_MODEL', 'gemini-3.1-pro-preview')
        )
    )
    temperature: float = 0.7
    max_output_tokens: Optional[int] = None
    api_key: Optional[str] = None

    def __post_init__(self):
        """Validate model configuration."""
        valid_gemini_models = [
            'gemini-3.1-pro-preview',    # Pro model for complex tasks
            'gemini-3-flash-preview',  # Primary flash model (supports JSON output)
            'gemini-2.5-pro',          # Legacy support
            'gemini-2.5-flash',        # Legacy support
            'gemini-2.0-flash-exp',    # Legacy support
            'gemini-1.5-flash',
            'gemini-1.5-pro',
        ]

        valid_openai_models = [
            'gpt-4.1-nano',
        ]

        if self.provider == 'gemini' and self.model_name not in valid_gemini_models:
            raise ValueError(
                f"Invalid Gemini model: {self.model_name}. "
                f"Valid options: {', '.join(valid_gemini_models)}"
            )

        if self.provider == 'openai' and self.model_name not in valid_openai_models:
            raise ValueError(
                f"Invalid OpenAI model: {self.model_name}. "
                f"Valid options: {', '.join(valid_openai_models)}"
            )


@dataclass
class ValidationConfig:
    """Configuration for validation agents (Skeptic, Verifier, Referee, FactCheck)."""
    use_pro_model: bool = field(default_factory=lambda: os.getenv('USE_PRO_FOR_VALIDATION', 'false').lower() == 'true')
    pro_model_name: str = 'gemini-3.1-pro-preview'
    validate_per_section: bool = True  # Always validate each section independently
    enable_factcheck: bool = field(
        default_factory=lambda: os.getenv('ENABLE_FACTCHECK', 'true').lower() == 'true'
    )

    def get_validation_model(self, base_model: str) -> str:
        """Return appropriate model for validation tasks."""
        return self.pro_model_name if self.use_pro_model else base_model


@dataclass
class PathConfig:
    """Path configuration for outputs and prompts."""
    project_root: Path = field(default_factory=lambda: Path(__file__).parent)
    output_dir: Path = field(default_factory=lambda: Path('tests/outputs'))
    prompts_dir: Path = field(default_factory=lambda: Path('prompts'))

    def __post_init__(self):
        """Ensure paths are absolute."""
        self.output_dir = self.project_root / self.output_dir
        self.prompts_dir = self.project_root / self.prompts_dir


@dataclass
class AppConfig:
    """
    Application-wide configuration.

    Single source of truth for all settings across the application.
    Follows SOLID principles and provides type-safe access to configuration.
    """
    # API Keys (GEMINI_API_KEY is alias for GOOGLE_API_KEY)
    google_api_key: str = field(
        default_factory=lambda: os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY', '')
    )
    google_api_key_fallback: str = field(default_factory=lambda: os.getenv('GOOGLE_API_KEY_FALLBACK', ''))
    google_api_key_fallback_2: str = field(default_factory=lambda: os.getenv('GOOGLE_API_KEY_FALLBACK_2', ''))
    google_api_key_fallback_3: str = field(default_factory=lambda: os.getenv('GOOGLE_API_KEY_FALLBACK_3', ''))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY', ''))
    openai_api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))

    # Sub-configurations
    model: ModelConfig = field(default_factory=ModelConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    paths: PathConfig = field(default_factory=PathConfig)

    # Citation and paper settings
    citation_style: str = field(default_factory=lambda: os.getenv('CITATION_STYLE', 'apa'))
    ai_detection_threshold: float = field(default_factory=lambda: float(os.getenv('AI_DETECTION_THRESHOLD', '0.20')))

    def __post_init__(self):
        """Validate configuration on initialization."""
        # Note: API key validation moved to validate_api_keys() for lazy validation
        # This allows importing config without requiring API keys (e.g., for --help)
        pass

    def validate_api_keys(self) -> None:
        """
        Validate that required API keys are present.

        Call this before operations that need API access.
        Raises ValueError if required keys are missing.
        """
        if self.model.provider == 'gemini' and not self.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is required for Gemini models. "
                "Set it in .env file or environment. "
                "Get your key at: https://makersuite.google.com/app/apikey"
            )

        if self.model.provider == 'claude' and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required for Claude models")

        if self.model.provider == 'openai' and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI models")

    @property
    def has_api_key(self) -> bool:
        """Check if required API key is configured (without raising)."""
        if self.model.provider == 'gemini':
            return bool(self.google_api_key)
        if self.model.provider == 'claude':
            return bool(self.anthropic_api_key)
        if self.model.provider == 'openai':
            return bool(self.openai_api_key)
        return False


# Global configuration instance - lazy loaded
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Get the global configuration instance (lazy loaded).

    Returns:
        AppConfig: The application configuration
    """
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def update_model(model_name: str) -> None:
    """
    Update the model name at runtime.

    Args:
        model_name: New model name to use
    """
    cfg = get_config()
    cfg.model.model_name = model_name
    cfg.model.__post_init__()  # Re-validate


if __name__ == '__main__':
    # Configuration validation test
    cfg = get_config()
    print(f"✅ Configuration loaded successfully")
    print(f"Model: {cfg.model.model_name}")
    print(f"Provider: {cfg.model.provider}")
    print(f"API Key configured: {cfg.has_api_key}")
    print(f"Validation per section: {cfg.validation.validate_per_section}")
    print(f"Output directory: {cfg.paths.output_dir}")
