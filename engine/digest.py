#!/usr/bin/env python3
"""
ABOUTME: Generate 60-second audio digests from academic papers
ABOUTME: Standalone module for TTS-optimized research summaries

Usage:
    python -m engine.digest paper.pdf
    python -m engine.digest paper.pdf --voice adam -o output/
    python -m engine.digest paper.pdf --no-audio
"""

import os
import re
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from utils.document_reader import read_document, get_document_info

logger = logging.getLogger(__name__)

DIGEST_PROMPT = (Path(__file__).parent / "prompts" / "digest.md").read_text()


def generate_script(
    document_path: Path,
    model_name: str | None = None,
    max_chars: int = 100000,
) -> tuple[str, dict]:
    """
    Generate a 60-second narration script from a document.

    Args:
        document_path: Path to PDF, markdown, or text file
        model_name: Model name to use for the active provider
        max_chars: Max characters to read from document

    Returns:
        Tuple of (script, metadata)
    """
    document_path = Path(document_path)
    content = read_document(document_path, max_chars=max_chars)

    # Setup provider client
    from utils.llm_client import build_model_client

    model = build_model_client(model_override=model_name)

    # Build prompt
    prompt = f"""{DIGEST_PROMPT}

---
DOCUMENT: {document_path.name}
---

{content}

---

Generate a 150-180 word narration script. Output ONLY the script text, nothing else.
"""

    # Generate
    response = model.generate_content(prompt)
    script = _clean_script(response.text)

    metadata = {
        "document": document_path.name,
        "word_count": len(script.split()),
        "model": getattr(model, 'model_name', model_name or 'unknown'),
    }

    return script, metadata


def _clean_script(script: str) -> str:
    """Clean script for TTS."""
    # Remove markdown formatting
    script = re.sub(r'\*\*([^*]+)\*\*', r'\1', script)  # bold
    script = re.sub(r'\*([^*]+)\*', r'\1', script)  # italic
    script = re.sub(r'`([^`]+)`', r'\1', script)  # code

    # Remove any headers
    script = re.sub(r'^#+\s+.*$', '', script, flags=re.MULTILINE)

    # Remove citations (Author Year pattern only, not general parentheticals)
    # Matches: (Smith 2020), (Smith et al., 2020), (Smith & Jones 2019)
    # Does NOT match: (about 3000 participants), (2019-2020), (circa 1985)
    script = re.sub(r'\([A-Z][a-zA-Z\s&.,]+(?:19|20)\d{2}[^)]*\)', '', script)
    script = re.sub(r'\[[^\]]+\]', '', script)

    # Clean whitespace
    script = re.sub(r'\s+', ' ', script)
    return script.strip()


def generate_digest(
    document_path: Path,
    output_dir: Optional[Path] = None,
    voice: str = "rachel",
    model_name: str | None = None,
    generate_audio: bool = True,
) -> dict:
    """
    Generate a complete digest: script + audio.

    Args:
        document_path: Path to document
        output_dir: Directory for output files
        voice: ElevenLabs voice name
        model_name: Model name for script generation
        generate_audio: Whether to generate audio

    Returns:
        Dict with script, script_path, and optionally audio_path
    """
    document_path = Path(document_path)

    if output_dir is None:
        output_dir = document_path.parent

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate script
    script, metadata = generate_script(document_path, model_name=model_name)

    # Save script
    base_name = document_path.stem
    script_path = output_dir / f"{base_name}_digest.md"
    script_path.write_text(f"## Digest Script\n\n{script}\n", encoding="utf-8")

    result = {
        "script": script,
        "script_path": script_path,
        "word_count": metadata["word_count"],
    }

    # Generate audio if requested
    if generate_audio:
        try:
            from utils.elevenlabs import generate_audio as gen_audio

            audio_path = output_dir / f"{base_name}_digest.mp3"
            gen_audio(script, audio_path, voice=voice)
            result["audio_path"] = audio_path
        except ValueError as e:
            result["audio_error"] = str(e)
        except Exception as e:
            result["audio_error"] = f"Audio generation failed: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate 60-second audio digest for any paper"
    )
    parser.add_argument("document", help="Path to document (PDF, MD, or TXT)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument(
        "--voice",
        default="rachel",
        choices=["rachel", "adam", "josh", "elli", "bella"],
        help="ElevenLabs voice (default: rachel)"
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio generation"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (defaults to the active provider's selected model)"
    )

    args = parser.parse_args()
    try:
        from opendraft.cli import apply_saved_runtime_config
    except ImportError:
        from cli import apply_saved_runtime_config
    apply_saved_runtime_config()
    document_path = Path(args.document)

    if not document_path.exists():
        print(f"Error: File not found: {document_path}")
        sys.exit(1)

    print(f"Document: {document_path.name}")
    print(f"Voice: {args.voice}")

    try:
        info = get_document_info(document_path)
        print(f"Words: {info['word_count']:,}")
    except Exception:
        pass

    print("\nGenerating digest...")

    output_dir = Path(args.output) if args.output else None

    result = generate_digest(
        document_path,
        output_dir=output_dir,
        voice=args.voice,
        model_name=args.model,
        generate_audio=not args.no_audio,
    )

    print(f"\n--- Digest Script ({result['word_count']} words) ---")
    print(result["script"])
    print("---")

    print(f"\nScript saved: {result['script_path']}")

    if "audio_path" in result:
        print(f"Audio saved: {result['audio_path']}")
    elif "audio_error" in result:
        print(f"Audio skipped: {result['audio_error']}")


if __name__ == "__main__":
    main()
