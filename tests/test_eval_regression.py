#!/usr/bin/env python3
"""
ABOUTME: Regression test for citation accuracy — pytest integration
ABOUTME: Tests the eval_regression script's core functions without requiring
         file I/O. Can be run with: pytest tests/test_eval_regression.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from utils.quality_gate import score_draft_quality, QualityScore
from phases.context import DraftContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_topic():
    """A single eval topic entry."""
    return {
        "id": "topic_001",
        "domain": "computer_science",
        "topic": "Attention mechanisms in transformer architectures",
        "canonical_papers": ["Vaswani et al., 2017"],
        "expected_citation_count_min": 10,
        "expected_citation_count_max": 25,
    }


@pytest.fixture
def sample_baseline():
    """A minimal baseline dict for testing."""
    return {
        "topic_001": {
            "total_score": 60.0,
            "citation_score": 25.0,
            "word_count": 1673.0,
            "unique_citations": 15.0,
        }
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildMockContext:
    """Tests for _build_mock_context from eval_regression module."""

    def setup_method(self):
        from scripts.eval_regression import _build_mock_context
        self._build_mock_context = _build_mock_context

    def test_context_has_topic(self):
        ctx = self._build_mock_context("Test topic", "test_domain")
        assert ctx.topic == "Test topic"

    def test_context_has_academic_level(self):
        ctx = self._build_mock_context("Test topic", "test_domain")
        assert ctx.academic_level == "master"

    def test_context_outputs_not_empty(self):
        ctx = self._build_mock_context("Test topic", "test_domain")
        assert len(ctx.intro_output.strip()) > 0
        assert len(ctx.body_output.strip()) > 0
        assert len(ctx.conclusion_output.strip()) > 0

    def test_context_has_citations(self):
        ctx = self._build_mock_context("Test topic", "test_domain")
        import re
        all_text = (
            ctx.intro_output + ctx.body_output + ctx.conclusion_output
        )
        refs = re.findall(r"\{cite_\d+\}", all_text)
        assert len(refs) >= 10


class TestComputeMetrics:
    """Tests for _compute_metrics from eval_regression module."""

    def setup_method(self):
        from scripts.eval_regression import _compute_metrics
        self._compute_metrics = _compute_metrics

    def test_metrics_return_dict(self):
        ctx = DraftContext()
        metrics = self._compute_metrics(ctx)
        assert isinstance(metrics, dict)

    def test_metrics_have_required_keys(self):
        ctx = DraftContext()
        metrics = self._compute_metrics(ctx)
        required_keys = [
            "total_score", "word_count_score", "citation_score",
            "completeness_score", "structure_score",
            "word_count", "unique_citations", "total_citation_refs", "passed",
        ]
        for key in required_keys:
            assert key in metrics, f"Missing key: {key}"

    def test_metrics_are_numeric(self):
        ctx = DraftContext()
        metrics = self._compute_metrics(ctx)
        for key, value in metrics.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric: {type(value)}"

    def test_quality_score_is_reasonable(self):
        ctx = DraftContext()
        ctx.intro_output = "Intro " * 100 + " {cite_001}"
        ctx.body_output = "Body " * 500 + " {cite_002} {cite_003}"
        ctx.conclusion_output = "Conclusion " * 50 + " {cite_004}"
        ctx.lit_review_output = "Lit " * 50
        ctx.methodology_output = "Meth " * 50
        ctx.results_output = "Res " * 50
        metrics = self._compute_metrics(ctx)
        assert 0 <= metrics["total_score"] <= 100


class TestQualityGateIntegration:
    """Integration tests using the quality gate directly."""

    def test_good_draft_passes_quality_gate(self):
        """A well-formed draft should pass the quality gate."""
        ctx = DraftContext()
        ctx.intro_output = "Intro " * 150 + " {cite_001} {cite_002}"
        ctx.body_output = "Body " * 500 + " {cite_003} {cite_004} {cite_005}"
        ctx.conclusion_output = "Conclusion " * 100 + " {cite_006}"
        ctx.lit_review_output = "Lit " * 80
        ctx.methodology_output = "Meth " * 60
        ctx.results_output = "Res " * 60
        ctx.academic_level = "master"
        ctx.word_targets = {"min_citations": 10}

        score = score_draft_quality(ctx)
        assert score.passed is True
        assert score.total_score >= 50

    def test_poor_draft_fails_quality_gate(self):
        """A draft with no content should fail the quality gate."""
        ctx = DraftContext()
        ctx.intro_output = ""
        ctx.body_output = ""
        ctx.conclusion_output = ""
        ctx.lit_review_output = ""
        ctx.methodology_output = ""
        ctx.results_output = ""
        ctx.academic_level = "master"
        ctx.word_targets = {"min_citations": 10}

        score = score_draft_quality(ctx)
        assert score.passed is False
        assert score.total_score < 50


class TestRegressionThreshold:
    """Tests for the degradation threshold logic."""

    def setup_method(self):
        from scripts.eval_regression import run_regression
        self.run_regression = run_regression

    def test_no_degradation_passes(self, sample_topic, sample_baseline, tmp_path):
        """When current metrics match baseline, regression should pass."""
        topics_file = tmp_path / "topics.json"
        topics_file.write_text(json.dumps([sample_topic]))

        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps(sample_baseline))

        exit_code = self.run_regression(
            str(topics_file), str(baseline_file), threshold=0.10
        )
        assert exit_code == 0

    def test_excessive_degradation_fails(self, sample_topic, sample_baseline, tmp_path):
        """When metrics degrade >10%, regression should fail."""
        degraded_baseline = {
            "topic_001": {
                "total_score": 100.0,  # Artificially high baseline
                "citation_score": 25.0,
                "word_count": 1673.0,
                "unique_citations": 15.0,
            }
        }
        topics_file = tmp_path / "topics.json"
        topics_file.write_text(json.dumps([sample_topic]))

        baseline_file = tmp_path / "baseline.json"
        baseline_file.write_text(json.dumps(degraded_baseline))

        exit_code = self.run_regression(
            str(topics_file), str(baseline_file), threshold=0.10
        )
        assert exit_code == 1
