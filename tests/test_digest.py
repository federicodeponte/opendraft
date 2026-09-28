#!/usr/bin/env python3
"""Tests for Digest functionality."""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add engine to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))


class TestElevenLabsClient:
    """Tests for ElevenLabs TTS client."""

    def test_client_requires_api_key(self):
        """Test that client raises error without API key."""
        from utils.elevenlabs import ElevenLabsClient

        # Clear env var if set
        old_key = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="API key required"):
                ElevenLabsClient()
        finally:
            if old_key:
                os.environ["ELEVENLABS_API_KEY"] = old_key

    def test_client_accepts_explicit_key(self):
        """Test client accepts explicit API key."""
        from utils.elevenlabs import ElevenLabsClient

        client = ElevenLabsClient(api_key="test-key-12345")
        assert client.api_key == "test-key-12345"

    def test_voice_id_resolution(self):
        """Test voice name to ID resolution."""
        from utils.elevenlabs import VOICES

        assert "rachel" in VOICES
        assert "adam" in VOICES
        assert "josh" in VOICES
        assert len(VOICES) >= 5


class TestDigestGeneration:
    """Tests for digest script generation."""

    @pytest.mark.integration
    def test_generate_script_with_mock(self, tmp_path):
        """Test digest script generation with mocked Gemini."""
        from digest import generate_script

        # Create test document
        doc = tmp_path / "paper.md"
        doc.write_text("""
        # Sleep and Performance Study

        This research examines how sleep deprivation affects workplace performance.
        A study of 500 healthcare workers found alarming results about safety.
        Those sleeping under 6 hours made 3x more errors in critical tasks.
        The brain enters microsleeps without the person being aware.
        """)

        mock_response = Mock()
        mock_response.text = """Today we're looking at sleep and workplace safety...
        from a study of five hundred healthcare workers. The question is simple:
        does running on little sleep actually make you dangerous at work?
        Here's the thing... workers sleeping under six hours made three times
        more errors on critical tasks. But here's the scary part... your brain
        enters microsleeps without you even knowing. So what does this mean for you?
        If you're in a safety-critical job, your gut feeling about being "fine"
        is probably wrong. Get more sleep... your coworkers are counting on it."""

        with patch('digest.GeminiModelWrapper') as MockModel:
            mock_instance = MockModel.return_value
            mock_instance.generate_content.return_value = mock_response

            with patch('google.genai'):
                script, metadata = generate_script(doc)

        assert "sleep" in script.lower()
        assert metadata["word_count"] > 50

    def test_script_cleaning(self):
        """Test that scripts are cleaned for TTS."""
        from digest import _clean_script

        dirty = "**Bold** text with *italics* and `code` plus [citation]."
        clean = _clean_script(dirty)

        assert "**" not in clean
        assert "*" not in clean
        assert "`" not in clean
        assert "[" not in clean

    def test_script_cleaning_removes_citations(self):
        """Test that academic citations are removed."""
        from digest import _clean_script

        # Should remove citation patterns
        assert "Smith" not in _clean_script("A study (Smith 2020) found.")
        assert "et al" not in _clean_script("Results (Smith et al., 2020) show.")
        assert "Jones" not in _clean_script("Paper (Smith & Jones 2019) analyzed.")

    def test_script_cleaning_preserves_non_citations(self):
        """Test that non-citation parentheticals are preserved."""
        from digest import _clean_script

        # Should NOT remove these (not citations)
        assert "3000 participants" in _clean_script("The study (about 3000 participants) shows.")
        assert "2019-2020" in _clean_script("In the year (2019-2020) there was growth.")
        assert "circa 1985" in _clean_script("Results from (circa 1985) experiments.")


class TestDigestCLI:
    """Tests for digest CLI command."""

    def test_cli_file_not_found(self):
        """Test CLI error when file not found."""
        from opendraft.cli import run_digest_command

        result = run_digest_command(["/nonexistent/file.pdf"])
        assert result == 1

    def test_cli_help(self, capsys):
        """Test CLI help output."""
        from opendraft.cli import run_digest_command

        with pytest.raises(SystemExit) as exc_info:
            run_digest_command(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "audio digest" in captured.out.lower() or "document" in captured.out

    def test_cli_voice_choices(self):
        """Test that voice argument accepts valid choices."""
        from opendraft.cli import run_digest_command

        # Invalid voice should fail
        with pytest.raises(SystemExit):
            run_digest_command(["test.pdf", "--voice", "invalid_voice"])


class TestDigestOutput:
    """Tests for digest output handling."""

    def test_generate_digest_creates_files(self, tmp_path):
        """Test that generate_digest creates expected output files."""
        from digest import generate_digest

        # Create test document
        doc = tmp_path / "paper.md"
        doc.write_text("Test paper content about research findings.")

        output_dir = tmp_path / "output"

        mock_response = Mock()
        mock_response.text = "This is a test digest script about research findings and their implications for the field."

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            with patch('digest.GeminiModelWrapper') as MockModel:
                mock_instance = MockModel.return_value
                mock_instance.generate_content.return_value = mock_response

                with patch('google.genai'):
                    result = generate_digest(
                        doc,
                        output_dir=output_dir,
                        generate_audio=False  # Skip audio for unit test
                    )

        assert "script" in result
        assert "script_path" in result
        assert result["script_path"].exists()
        assert "audio_path" not in result  # No audio generated
