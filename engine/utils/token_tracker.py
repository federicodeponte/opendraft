#!/usr/bin/env python3
"""
ABOUTME: Synchronous TokenTracker for tracking API call token usage and costs
ABOUTME: Ported from OpenPaper — async removed for OpenDraft's synchronous pipeline
"""

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from utils.model_config import get_model_pricing

logger = logging.getLogger(__name__)


class CallStatus(str, Enum):
    """Status of an API call."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CACHED = "cached"
    RATE_LIMITED = "rate_limited"


@dataclass
class APICall:
    """Record of a single API call."""
    stage: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    timestamp: float = field(default_factory=time.time)
    model_name: str = ""
    cost_usd: float = 0.0
    status: CallStatus = CallStatus.SUCCESS
    error_message: Optional[str] = None


@dataclass
class StageStats:
    """Aggregated stats for a pipeline stage."""
    stage: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    success_count: int = 0
    failure_count: int = 0


class TokenTracker:
    """
    Tracks token usage across the entire draft generation pipeline.

    Usage:
        tracker = TokenTracker(model_name="gemini-3.1-pro-preview")
        tracker.add_call(stage="scribe", input_tokens=5000, output_tokens=2000)
        tracker.add_call(stage="architect", input_tokens=3000, output_tokens=1500)
        tracker.print_report()
    """

    def __init__(self, model_name: str = "gemini-3.1-pro-preview"):
        self.model_name = model_name
        self.calls: List[APICall] = []
        self._start_time = time.time()

        # Look up pricing
        self._pricing = get_model_pricing(model_name)
        if self._pricing:
            logger.info(f"TokenTracker: Using pricing for {self._pricing.name}")
        else:
            logger.warning(f"TokenTracker: No pricing found for '{model_name}' — costs will be $0")

    def add_call(
        self,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        status: CallStatus = CallStatus.SUCCESS,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a single API call."""
        total = input_tokens + output_tokens

        cost = 0.0
        if self._pricing:
            cost = (
                (input_tokens / 1_000_000) * self._pricing.input_price
                + (output_tokens / 1_000_000) * self._pricing.output_price
            )

        call = APICall(
            stage=stage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            model_name=self.model_name,
            cost_usd=cost,
            status=status,
            error_message=error_message,
        )
        self.calls.append(call)
        logger.debug(
            f"TokenTracker: {stage} — "
            f"{input_tokens:,} in + {output_tokens:,} out = {total:,} tokens "
            f"(${cost:.4f}){f' [{status.value}]' if status != CallStatus.SUCCESS else ''}"
        )

    def get_stage_stats(self) -> Dict[str, StageStats]:
        """Aggregate stats by stage."""
        stats: Dict[str, StageStats] = {}
        for call in self.calls:
            if call.stage not in stats:
                stats[call.stage] = StageStats(stage=call.stage)
            s = stats[call.stage]
            s.calls += 1
            s.input_tokens += call.input_tokens
            s.output_tokens += call.output_tokens
            s.total_tokens += call.total_tokens
            s.cost_usd += call.cost_usd
            if call.status == CallStatus.SUCCESS:
                s.success_count += 1
            elif call.status == CallStatus.FAILURE:
                s.failure_count += 1
        return stats

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_cost(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    def generate_report(self) -> str:
        """Generate a human-readable token usage report string."""
        elapsed = time.time() - self._start_time
        lines = []

        lines.append("═" * 70)
        lines.append("                  TOKEN USAGE & COST REPORT".center(70))
        lines.append("═" * 70)
        lines.append("")

        model_display = self._pricing.display_name if self._pricing and self._pricing.display_name else self.model_name
        lines.append(f"Model: {model_display}")
        lines.append(f"Duration: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        lines.append("")

        lines.append("STAGE-BY-STAGE BREAKDOWN:")
        lines.append("─" * 70)

        stats = self.get_stage_stats()
        if stats:
            lines.append(
                f"{'Stage':<30} │ {'Calls':>6} │ {'In Tokens':>10} │ {'Out Tokens':>10} │ {'Cost':>8}"
            )
            lines.append("─" * 70)
            for stage_name in sorted(stats.keys()):
                s = stats[stage_name]
                stage_display = s.stage[:28]
                lines.append(
                    f"{stage_display:<30} │ {s.calls:>6} │ "
                    f"{s.input_tokens:>10,} │ {s.output_tokens:>10,} │ ${s.cost_usd:>7.4f}"
                )
        else:
            lines.append("(No API calls recorded)")

        lines.append("")
        lines.append("TOTALS:")
        lines.append("─" * 70)
        lines.append(f"Total API Calls: {self.total_calls}")
        lines.append(f"Total Input Tokens: {self.total_input_tokens:,}")
        lines.append(f"Total Output Tokens: {self.total_output_tokens:,}")
        lines.append(f"Total Tokens: {self.total_tokens:,}")
        lines.append(f"Total Cost: ${self.total_cost:.4f}")
        lines.append("")
        lines.append("═" * 70)

        return "\n".join(lines)

    def print_report(self) -> None:
        """Print the token usage report to logger."""
        logger.info("\n" + self.generate_report())

    def get_session_summary(self) -> Dict[str, any]:
        """
        Get a summary of the current session's usage.

        Returns:
            Dict with session summary statistics including:
            - total calls, tokens, cost
            - per-stage breakdown
            - timing information
            - success/error counts
        """
        elapsed = time.time() - self._start_time
        stats = self.get_stage_stats()

        # Count calls by status
        status_counts = {}
        for call in self.calls:
            status = getattr(call, 'status', CallStatus.SUCCESS)
            status_str = status.value if isinstance(status, CallStatus) else str(status)
            status_counts[status_str] = status_counts.get(status_str, 0) + 1

        return {
            "model": self.model_name,
            "duration_seconds": round(elapsed, 1),
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "status_counts": status_counts,
            "stages": {
                name: {
                    "calls": s.calls,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "total_tokens": s.total_tokens,
                    "cost_usd": round(s.cost_usd, 6),
                    "success_count": s.success_count,
                    "failure_count": s.failure_count,
                }
                for name, s in sorted(stats.items())
            },
        }

    def to_dict(self) -> dict:
        """Serialize tracker state for JSON export."""
        elapsed = time.time() - self._start_time
        stats = self.get_stage_stats()

        return {
            "model": self.model_name,
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "duration_seconds": round(elapsed, 1),
            "stages": {
                name: {
                    "calls": s.calls,
                    "input_tokens": s.input_tokens,
                    "output_tokens": s.output_tokens,
                    "total_tokens": s.total_tokens,
                    "cost_usd": round(s.cost_usd, 6),
                    "success_count": s.success_count,
                    "failure_count": s.failure_count,
                }
                for name, s in sorted(stats.items())
            },
            "calls": [
                {
                    "stage": c.stage,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "total_tokens": c.total_tokens,
                    "cost_usd": round(c.cost_usd, 6),
                    "timestamp": c.timestamp,
                    "status": c.status.value,
                    **({"error_message": c.error_message} if c.error_message else {}),
                }
                for c in self.calls
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
