#!/usr/bin/env python3
"""
ABOUTME: Tier-adaptive concurrency configuration for OpenDraft
ABOUTME: Auto-configures rate limits and parallel execution based on detected API tier
"""

import os
from dataclasses import dataclass, field
from typing import Literal, Optional


def _tier_to_rpm(tier: str) -> int:
    """Map tier name to default RPM."""
    tier_map = {
        "free": 10,
        "paid": 2000,
        "custom": 100,  # Conservative default for unknown tiers
    }
    return tier_map.get(tier, 10)


@dataclass
class ConcurrencyConfig:
    """
    Tier-adaptive concurrency configuration.

    Automatically adjusts parallelization and rate limiting based on
    detected API tier (free=10 RPM, paid=2,000 RPM).

    Attributes:
        tier: API tier ("free", "paid", "custom")
        rpm_limit: Requests per minute limit
        rate_limit_delay: Seconds to wait between API calls
        crafter_parallel: Whether to run 6 Crafter agents in parallel
        scout_batch_delay: Seconds between Scout citation research batches
        scout_batch_size: Citations per batch
        scout_parallel_workers: Number of parallel workers for citation research
        max_parallel_theses: Max thesis generations to run concurrently
    """

    # Tier detection (auto-detected if not specified)
    tier: Literal["free", "paid", "custom"] = field(default=None)

    # Rate limiting (auto-configured based on tier)
    rpm_limit: int = field(default=None)
    rate_limit_delay: float = field(default=None)

    # Parallel execution flags
    crafter_parallel: bool = field(default=None)

    # Scout (citation research) settings
    scout_batch_size: int = field(
        default_factory=lambda: int(os.getenv("SCOUT_BATCH_SIZE", "10"))
    )
    scout_batch_delay: float = field(
        default_factory=lambda: float(os.getenv("SCOUT_BATCH_DELAY", "1.0"))
    )
    scout_parallel_workers: int = field(
        default_factory=lambda: int(os.getenv("SCOUT_PARALLEL_WORKERS", "4"))
    )

    # Thesis generation limits
    max_parallel_theses: int = field(
        default_factory=lambda: int(os.getenv("MAX_PARALLEL_THESES", "3"))
    )

    def __post_init__(self):
        """Configure settings based on detected tier."""
        # Auto-detect tier if not specified
        if self.tier is None:
            env_tier = os.getenv("API_TIER")
            if env_tier and env_tier.lower() in ["free", "paid", "custom"]:
                self.tier = env_tier.lower()
            else:
                # Only auto-detect if we have a Google/Gemini API key
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                if api_key:
                    try:
                        from utils.api_tier_detector import detect_api_tier
                        self.tier = detect_api_tier(verbose=False)
                    except Exception:
                        self.tier = "free"  # Default to free tier on detection failure
                else:
                    self.tier = "free"  # Default to free tier if no API key

        # Get tier-specific rate limit
        if self.rpm_limit is None:
            self.rpm_limit = _tier_to_rpm(self.tier)

        # Calculate delay between calls based on RPM
        if self.rate_limit_delay is None:
            if self.tier == "free":
                # Free tier: 10 RPM = 6 seconds between calls (with buffer)
                self.rate_limit_delay = 7.0
            elif self.tier == "paid":
                # Paid tier: 2000 RPM = 0.03s, but use 0.5s for safety
                self.rate_limit_delay = 0.5
            else:
                # Custom: use environment or default
                self.rate_limit_delay = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))

        # Parallel execution based on tier
        if self.crafter_parallel is None:
            # Only enable parallel crafters on paid tier
            self.crafter_parallel = self.tier == "paid"


# Singleton instance
_config: Optional[ConcurrencyConfig] = None


def get_concurrency_config(verbose: bool = False) -> ConcurrencyConfig:
    """
    Get or create the singleton concurrency config.

    Args:
        verbose: Whether to print configuration info (default: False)

    Returns:
        ConcurrencyConfig instance
    """
    global _config
    if _config is None:
        _config = ConcurrencyConfig()
        if verbose:
            print(f"⚙️  Concurrency config: tier={_config.tier}, {_config.scout_parallel_workers} workers, "
                  f"{_config.scout_batch_size} batch size, {_config.rate_limit_delay}s delay")
    return _config


def reset_config():
    """Reset the singleton (for testing)."""
    global _config
    _config = None


if __name__ == "__main__":
    # Test configuration
    reset_config()
    config = get_concurrency_config(verbose=True)
    print(f"Tier: {config.tier}")
    print(f"RPM Limit: {config.rpm_limit}")
    print(f"Rate Limit Delay: {config.rate_limit_delay}s")
    print(f"Crafter Parallel: {config.crafter_parallel}")
    print(f"Scout Batch Size: {config.scout_batch_size}")
    print(f"Scout Workers: {config.scout_parallel_workers}")
