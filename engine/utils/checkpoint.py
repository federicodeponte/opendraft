#!/usr/bin/env python3
"""
ABOUTME: Checkpoint/resume system for long-running draft generation
ABOUTME: Saves context state after each phase, allows resuming from checkpoint
"""

import json
import logging
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Phases in order of execution
PHASES = ["research", "structure", "citations", "compose", "validate", "compile"]


def save_checkpoint(ctx: 'DraftContext', phase: str, checkpoint_dir: Path) -> Path:
    """
    Save checkpoint after a phase completes.

    Args:
        ctx: Current DraftContext with phase outputs
        phase: Name of the phase that just completed
        checkpoint_dir: Directory to save checkpoint (usually output_dir)

    Returns:
        Path to saved checkpoint file
    """
    checkpoint_path = checkpoint_dir / "checkpoint.json"

    # Serialize context to dict
    checkpoint_data = {
        "version": "1.0",
        "completed_phase": phase,
        "timestamp": datetime.now().isoformat(),

        # User inputs (all serializable)
        "topic": ctx.topic,
        "language": ctx.language,
        "academic_level": ctx.academic_level,
        "output_type": ctx.output_type,
        "citation_style": ctx.citation_style,
        "skip_validation": ctx.skip_validation,
        "verbose": ctx.verbose,
        "blurb": ctx.blurb,
        "user_sources": ctx.user_sources,
        "user_material": ctx.user_material,

        # Academic metadata
        "author_name": ctx.author_name,
        "institution": ctx.institution,
        "department": ctx.department,
        "faculty": ctx.faculty,
        "advisor": ctx.advisor,
        "second_examiner": ctx.second_examiner,
        "location": ctx.location,
        "student_id": ctx.student_id,

        # Derived values (can be recalculated, but save for convenience)
        "language_name": ctx.language_name,
        "language_instruction": ctx.language_instruction,
        "word_targets": ctx.word_targets,

        # Folders as strings
        "folders": {k: str(v) for k, v in ctx.folders.items()},

        # Research phase outputs
        "scout_output": ctx.scout_output,
        "scribe_output": ctx.scribe_output,
        "signal_output": ctx.signal_output,
        "scout_result": _serialize_scout_result(ctx.scout_result),

        # Structure phase outputs
        "architect_output": ctx.architect_output,
        "formatter_output": ctx.formatter_output,

        # Citation management outputs
        "citation_summary": ctx.citation_summary,
        # Note: citation_database is saved separately as bibliography.json

        # Compose phase outputs
        "intro_output": ctx.intro_output,
        "lit_review_output": ctx.lit_review_output,
        "methodology_output": ctx.methodology_output,
        "results_output": ctx.results_output,
        "discussion_output": ctx.discussion_output,
        "body_output": ctx.body_output,
        "conclusion_output": ctx.conclusion_output,
        "appendix_output": ctx.appendix_output,
    }

    checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info(f"Checkpoint saved after {phase} phase: {checkpoint_path}")

    return checkpoint_path


def load_checkpoint(checkpoint_path: Path) -> Tuple[Dict[str, Any], str]:
    """
    Load checkpoint data from file.

    Args:
        checkpoint_path: Path to checkpoint.json

    Returns:
        Tuple of (checkpoint_data dict, completed_phase name)
    """
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint_data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    completed_phase = checkpoint_data.get("completed_phase", "")

    logger.info(f"Loaded checkpoint from {checkpoint_path}, last phase: {completed_phase}")

    return checkpoint_data, completed_phase


def restore_context(ctx: 'DraftContext', checkpoint_data: Dict[str, Any]) -> None:
    """
    Restore context state from checkpoint data.

    Args:
        ctx: DraftContext to restore into (must have model, config already set)
        checkpoint_data: Data loaded from checkpoint file
    """
    # Restore user inputs
    ctx.topic = checkpoint_data.get("topic", ctx.topic)
    ctx.language = checkpoint_data.get("language", ctx.language)
    ctx.academic_level = checkpoint_data.get("academic_level", ctx.academic_level)
    ctx.output_type = checkpoint_data.get("output_type", ctx.output_type)
    ctx.citation_style = checkpoint_data.get("citation_style", ctx.citation_style)
    ctx.skip_validation = checkpoint_data.get("skip_validation", ctx.skip_validation)
    ctx.verbose = checkpoint_data.get("verbose", ctx.verbose)
    ctx.blurb = checkpoint_data.get("blurb", ctx.blurb)
    ctx.user_sources = checkpoint_data.get("user_sources", ctx.user_sources)
    ctx.user_material = checkpoint_data.get("user_material", ctx.user_material)

    # Restore academic metadata
    ctx.author_name = checkpoint_data.get("author_name")
    ctx.institution = checkpoint_data.get("institution")
    ctx.department = checkpoint_data.get("department")
    ctx.faculty = checkpoint_data.get("faculty")
    ctx.advisor = checkpoint_data.get("advisor")
    ctx.second_examiner = checkpoint_data.get("second_examiner")
    ctx.location = checkpoint_data.get("location")
    ctx.student_id = checkpoint_data.get("student_id")

    # Restore derived values
    ctx.language_name = checkpoint_data.get("language_name", ctx.language_name)
    ctx.language_instruction = checkpoint_data.get("language_instruction", ctx.language_instruction)
    ctx.word_targets = checkpoint_data.get("word_targets", ctx.word_targets)

    # Restore folders as Path objects
    folders_data = checkpoint_data.get("folders", {})
    ctx.folders = {k: Path(v) for k, v in folders_data.items()}

    # Restore research phase outputs
    ctx.scout_output = checkpoint_data.get("scout_output", "")
    ctx.scribe_output = checkpoint_data.get("scribe_output", "")
    ctx.signal_output = checkpoint_data.get("signal_output", "")
    ctx.scout_result = _deserialize_scout_result(checkpoint_data.get("scout_result"))

    # Restore structure phase outputs
    ctx.architect_output = checkpoint_data.get("architect_output", "")
    ctx.formatter_output = checkpoint_data.get("formatter_output", "")

    # Restore citation summary (citation_database loaded separately from bibliography.json)
    ctx.citation_summary = checkpoint_data.get("citation_summary", "")

    # Restore compose phase outputs
    ctx.intro_output = checkpoint_data.get("intro_output", "")
    ctx.lit_review_output = checkpoint_data.get("lit_review_output", "")
    ctx.methodology_output = checkpoint_data.get("methodology_output", "")
    ctx.results_output = checkpoint_data.get("results_output", "")
    ctx.discussion_output = checkpoint_data.get("discussion_output", "")
    ctx.body_output = checkpoint_data.get("body_output", "")
    ctx.conclusion_output = checkpoint_data.get("conclusion_output", "")
    ctx.appendix_output = checkpoint_data.get("appendix_output", "")

    logger.info(f"Context restored from checkpoint")


def get_next_phase(completed_phase: str) -> Optional[str]:
    """
    Get the next phase to run after a completed phase.

    Args:
        completed_phase: Name of the last completed phase

    Returns:
        Name of next phase, or None if all phases complete
    """
    if completed_phase not in PHASES:
        return PHASES[0]  # Start from beginning if unknown phase

    idx = PHASES.index(completed_phase)
    if idx + 1 < len(PHASES):
        return PHASES[idx + 1]
    return None


def _serialize_scout_result(scout_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Serialize scout_result, converting Citation objects to dicts."""
    if scout_result is None:
        return None

    from utils.citation_database import Citation

    result = dict(scout_result)

    # Convert citations list if present
    if "citations" in result and result["citations"]:
        result["citations"] = [
            c.to_dict() if hasattr(c, 'to_dict') else c
            for c in result["citations"]
        ]

    return result


def _deserialize_scout_result(scout_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Deserialize scout_result, converting dicts back to Citation objects."""
    if scout_result is None:
        return None

    from utils.citation_database import Citation

    result = dict(scout_result)

    # Convert citation dicts back to Citation objects
    if "citations" in result and result["citations"]:
        result["citations"] = [
            Citation.from_dict(c) if isinstance(c, dict) else c
            for c in result["citations"]
        ]

    return result
