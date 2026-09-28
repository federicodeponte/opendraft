"""Regression coverage for supplied inputs and length-scaled research."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.phases.context import DraftContext
from engine.phases.research import run_research_phase
from engine.draft_generator import get_word_count_targets, scale_citation_target, validate_compose_phase, PipelineValidationError
import pytest


def test_research_preserves_supplied_sources_and_material(tmp_path):
    research = tmp_path / "research"
    papers = research / "papers"
    papers.mkdir(parents=True)
    source = "Survey of rural care in 2024"
    calls = []

    def discover(**kwargs):
        calls.append(kwargs)
        kwargs["output_path"].write_text("# Scout\n")
        return {"citations": [], "count": 0}

    def agent(**kwargs):
        calls.append(kwargs)
        return "summary"

    ctx = DraftContext(
        topic="Rural care", blurb="Survey analysis", user_sources=[source],
        user_material="\nUSER SUPPLIED CONTEXT: survey response rate 62%",
        folders={"research": research, "papers": papers},
        word_targets={"min_citations": 12, "deep_research_min_sources": 20},
        verbose=False,
    )
    with patch("utils.agent_runner.research_citations_via_api", side_effect=discover), \
         patch("utils.agent_runner.run_agent", side_effect=agent), \
         patch("utils.agent_runner.rate_limit_delay"), \
         patch("engine.phases.research.split_scribe_to_papers"), \
         patch("engine.phases.research.extract_all_citations_as_papers"):
        run_research_phase(ctx)

    assert calls[0]["seed_references"] == [source]
    assert source in calls[0]["research_topics"]
    assert "response rate 62%" in calls[0]["scope"]
    assert ctx.scout_result["citations"][0].verification_status == "user_supplied"
    assert source in ctx.scout_output
    assert "response rate 62%" in calls[1]["user_input"]


def test_writer_fails_when_unique_citations_are_too_sparse():
    ctx = DraftContext(intro_output="A " * 800 + "{cite_001}",
                       lit_review_output="Body",
                       config=SimpleNamespace(words_per_citation=400))
    with pytest.raises(PipelineValidationError, match="3 required"):
        validate_compose_phase(ctx)


def test_target_length_requires_scaled_unique_sources():
    targets = get_word_count_targets("master")
    assert targets["total"] == "25,000-30,000"
    scaled = scale_citation_target(targets, 400)
    assert scaled["min_citations"] == 75
    assert scaled["deep_research_min_sources"] >= 75
    assert scale_citation_target(targets, 200)["min_citations"] == 150
