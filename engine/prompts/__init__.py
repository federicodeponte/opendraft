"""OpenDraft agent prompt library.

This package exists so the prompt markdown files (loaded at runtime by the
scribe/scout/compose/validate phases) are collected as package data and shipped
in the built wheel. Without it, `pip install opendraft` omits the prompts and
the scribe phase raises FileNotFoundError (issue #26).

Prompt files are addressed by relative path, e.g. "01_research/scribe.md";
resolution is centralized in utils.agent_runner.load_prompt.
"""
