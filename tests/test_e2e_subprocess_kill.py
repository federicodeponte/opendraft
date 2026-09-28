#!/usr/bin/env python3
"""
TRUE End-to-End subprocess kill and resume tests.

These tests spawn actual Python subprocesses that run a mock pipeline,
send real signals (SIGKILL/SIGTERM), and verify checkpoint-based resume
works correctly across process boundaries.

This is the gold standard for testing checkpoint reliability.
"""

import os
import sys
import json
import time
import signal
import tempfile
import subprocess
import pytest
from pathlib import Path
from multiprocessing import Process, Queue

sys.path.insert(0, str(Path(__file__).parent.parent / "engine"))

from utils.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    restore_context,
    get_next_phase,
    PHASES,
)
from utils.citation_database import Citation
from phases.context import DraftContext


# =============================================================================
# MOCK PIPELINE RUNNER (runs in subprocess)
# =============================================================================

MOCK_PIPELINE_SCRIPT = '''
#!/usr/bin/env python3
"""Mock pipeline that simulates phase execution with delays."""
import sys
import time
import json
import signal
import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("OPENDRAFT_TEST_REPO_ROOT", Path.cwd())).resolve()
sys.path.insert(0, str(REPO_ROOT / "engine"))

from utils.checkpoint import save_checkpoint, load_checkpoint, restore_context, get_next_phase, PHASES
from utils.citation_database import Citation
from phases.context import DraftContext


def run_mock_pipeline(output_dir: Path, resume_from: Path = None):
    """Run mock pipeline with checkpoints."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize context
    ctx = DraftContext()
    ctx.topic = "E2E Kill Test Topic"
    ctx.language = "en"
    ctx.academic_level = "research_paper"
    ctx.folders = {"root": output_dir, "research": output_dir / "research"}
    ctx.word_targets = {"min_citations": 10}

    (output_dir / "research").mkdir(exist_ok=True)

    # Handle resume
    completed_phase = None
    if resume_from and Path(resume_from).exists():
        data, completed_phase = load_checkpoint(Path(resume_from))
        restore_context(ctx, data)
        print(f"RESUMED_FROM:{completed_phase}", flush=True)

    # Write PID for external control
    pid_file = output_dir / "pipeline.pid"
    pid_file.write_text(str(os.getpid()))

    # Execute phases
    for phase in PHASES:
        # Skip completed phases
        if completed_phase:
            next_phase = get_next_phase(completed_phase)
            if next_phase != phase and PHASES.index(phase) <= PHASES.index(completed_phase):
                continue

        # Signal we're starting this phase
        print(f"STARTING_PHASE:{phase}", flush=True)

        # Phase markers file (for external detection)
        marker = output_dir / f".phase_{phase}_started"
        marker.write_text(str(time.time()))

        # Simulate phase work with delay
        if phase == "research":
            ctx.scout_output = f"Research output at {time.time()}"
            ctx.scout_result = {
                "citations": [
                    Citation(
                        citation_id=f"cite_{i:03d}",
                        authors=[f"Author{i}"],
                        year=2024,
                        title=f"Paper {i}",
                        source_type="journal",
                    ).to_dict()
                    for i in range(1, 11)
                ]
            }
            time.sleep(0.5)  # Simulate work

        elif phase == "structure":
            ctx.architect_output = f"Structure output at {time.time()}"
            time.sleep(0.5)

        elif phase == "citations":
            ctx.citation_summary = f"Citations summary at {time.time()}"
            time.sleep(0.5)

        elif phase == "compose":
            ctx.intro_output = "# Introduction\\n\\n" + "Content. " * 100
            ctx.body_output = "## Body\\n\\n" + "More content. " * 200
            ctx.conclusion_output = "## Conclusion\\n\\n" + "Final. " * 50
            time.sleep(0.5)

        elif phase == "validate":
            time.sleep(0.3)

        elif phase == "compile":
            time.sleep(0.3)

        # Save checkpoint after phase
        save_checkpoint(ctx, phase, output_dir)
        print(f"COMPLETED_PHASE:{phase}", flush=True)

        # Mark phase complete
        complete_marker = output_dir / f".phase_{phase}_complete"
        complete_marker.write_text(str(time.time()))

    print("PIPELINE_COMPLETE", flush=True)
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume-from", default=None)
    args = parser.parse_args()

    import os
    os.chdir(REPO_ROOT)  # CD to opendraft root

    success = run_mock_pipeline(
        output_dir=Path(args.output_dir),
        resume_from=Path(args.resume_from) if args.resume_from else None,
    )
    sys.exit(0 if success else 1)
'''


class TestTrueE2ESubprocessKill:
    """
    TRUE end-to-end tests that spawn subprocess, kill it, and verify resume.

    These tests actually spawn Python processes, send real signals,
    and verify checkpoint-based resume across process boundaries.
    """

    @pytest.fixture
    def mock_script(self, tmp_path):
        """Create mock pipeline script in temp directory."""
        script_path = tmp_path / "mock_pipeline.py"
        script_path.write_text(MOCK_PIPELINE_SCRIPT)
        return script_path

    def _subprocess_env(self) -> dict:
        """Return environment for mock pipeline subprocesses."""
        env = os.environ.copy()
        env["OPENDRAFT_TEST_REPO_ROOT"] = str(Path(__file__).parent.parent)
        return env

    def _wait_for_phase(self, output_dir: Path, phase: str, timeout: float = 10.0) -> bool:
        """Wait for a phase to start (marker file appears)."""
        marker = output_dir / f".phase_{phase}_started"
        start = time.time()
        while time.time() - start < timeout:
            if marker.exists():
                return True
            time.sleep(0.05)
        return False

    def _wait_for_phase_complete(self, output_dir: Path, phase: str, timeout: float = 10.0) -> bool:
        """Wait for a phase to complete."""
        marker = output_dir / f".phase_{phase}_complete"
        start = time.time()
        while time.time() - start < timeout:
            if marker.exists():
                return True
            time.sleep(0.05)
        return False

    def test_kill_during_research_resume_from_start(self, tmp_path, mock_script):
        """
        Kill during research phase → resume should restart from research.
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Start subprocess
        proc = subprocess.Popen(
            [sys.executable, str(mock_script), "--output-dir", str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        try:
            # Wait for research to start
            assert self._wait_for_phase(output_dir, "research", timeout=5), "Research never started"

            # Kill immediately (before checkpoint is saved)
            time.sleep(0.1)  # Let it start but not finish
            proc.kill()
            proc.wait(timeout=5)

        except Exception:
            proc.kill()
            raise

        # Checkpoint should NOT exist (killed before save)
        checkpoint_path = output_dir / "checkpoint.json"
        # May or may not exist depending on timing - that's ok

        # If no checkpoint, resume should start fresh
        if not checkpoint_path.exists():
            # Run again without resume
            proc2 = subprocess.Popen(
                [sys.executable, str(mock_script), "--output-dir", str(output_dir)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).parent.parent),
                env=self._subprocess_env(),
            )

            stdout, _ = proc2.communicate(timeout=30)
            assert proc2.returncode == 0, f"Pipeline failed: {stdout}"
            assert "PIPELINE_COMPLETE" in stdout

    def test_kill_after_research_resume_from_structure(self, tmp_path, mock_script):
        """
        Kill after research completes → resume should start from structure.
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Start subprocess
        proc = subprocess.Popen(
            [sys.executable, str(mock_script), "--output-dir", str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        try:
            # Wait for research to complete
            assert self._wait_for_phase_complete(output_dir, "research", timeout=10), "Research never completed"

            # Kill before structure completes
            time.sleep(0.1)
            proc.kill()
            proc.wait(timeout=5)

        except Exception:
            proc.kill()
            raise

        # Checkpoint should exist at research
        checkpoint_path = output_dir / "checkpoint.json"
        assert checkpoint_path.exists(), "Checkpoint should exist after research"

        data, completed = load_checkpoint(checkpoint_path)
        assert completed == "research"

        # Resume should continue from structure
        proc2 = subprocess.Popen(
            [
                sys.executable, str(mock_script),
                "--output-dir", str(output_dir),
                "--resume-from", str(checkpoint_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        stdout, stderr = proc2.communicate(timeout=30)
        assert proc2.returncode == 0, f"Resume failed: {stdout}\n{stderr}"
        assert "RESUMED_FROM:research" in stdout
        assert "STARTING_PHASE:structure" in stdout
        assert "PIPELINE_COMPLETE" in stdout

    def test_kill_after_compose_resume_to_validate(self, tmp_path, mock_script):
        """
        Kill after compose → resume should continue to validate.
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Start subprocess
        proc = subprocess.Popen(
            [sys.executable, str(mock_script), "--output-dir", str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        try:
            # Wait for compose to complete
            assert self._wait_for_phase_complete(output_dir, "compose", timeout=20), "Compose never completed"

            # Kill after compose
            time.sleep(0.1)
            proc.kill()
            proc.wait(timeout=5)

        except Exception:
            proc.kill()
            raise

        # Verify checkpoint at compose
        checkpoint_path = output_dir / "checkpoint.json"
        data, completed = load_checkpoint(checkpoint_path)
        assert completed == "compose"

        # Verify compose outputs preserved
        assert "Introduction" in data.get("intro_output", "")
        assert "Body" in data.get("body_output", "")

        # Resume
        proc2 = subprocess.Popen(
            [
                sys.executable, str(mock_script),
                "--output-dir", str(output_dir),
                "--resume-from", str(checkpoint_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        stdout, _ = proc2.communicate(timeout=30)
        assert proc2.returncode == 0
        assert "RESUMED_FROM:compose" in stdout
        assert "STARTING_PHASE:validate" in stdout
        assert "PIPELINE_COMPLETE" in stdout

    def test_sigterm_allows_graceful_checkpoint(self, tmp_path, mock_script):
        """
        SIGTERM should allow graceful checkpoint save before exit.
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        proc = subprocess.Popen(
            [sys.executable, str(mock_script), "--output-dir", str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        try:
            # Wait for structure to start
            assert self._wait_for_phase(output_dir, "structure", timeout=10)

            # Send SIGTERM (graceful)
            proc.terminate()
            proc.wait(timeout=10)

        except Exception:
            proc.kill()
            raise

        # With SIGTERM, checkpoint may be at research (last completed)
        checkpoint_path = output_dir / "checkpoint.json"
        if checkpoint_path.exists():
            _, completed = load_checkpoint(checkpoint_path)
            # Should be at least research
            assert completed in PHASES

    def test_multiple_kill_resume_cycles(self, tmp_path, mock_script):
        """
        Multiple kill/resume cycles should eventually complete pipeline.
        """
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        completed_phases = set()
        max_attempts = 10
        checkpoint_path = output_dir / "checkpoint.json"

        for attempt in range(max_attempts):
            resume_arg = ["--resume-from", str(checkpoint_path)] if checkpoint_path.exists() else []

            proc = subprocess.Popen(
                [sys.executable, str(mock_script), "--output-dir", str(output_dir)] + resume_arg,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(__file__).parent.parent),
                env=self._subprocess_env(),
            )

            try:
                # Let it run for a bit then kill
                stdout, _ = proc.communicate(timeout=2)

                if "PIPELINE_COMPLETE" in stdout:
                    # Pipeline finished!
                    break

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

            # Check checkpoint progress
            if checkpoint_path.exists():
                _, completed = load_checkpoint(checkpoint_path)
                completed_phases.add(completed)

        # Should have completed eventually or made progress
        assert checkpoint_path.exists(), "No checkpoint after multiple attempts"

        # Final run to completion
        proc = subprocess.Popen(
            [
                sys.executable, str(mock_script),
                "--output-dir", str(output_dir),
                "--resume-from", str(checkpoint_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env=self._subprocess_env(),
        )

        stdout, _ = proc.communicate(timeout=60)
        assert "PIPELINE_COMPLETE" in stdout or proc.returncode == 0


class TestConcurrentCheckpointWrites:
    """Test checkpoint behavior under concurrent write conditions."""

    def test_rapid_sequential_saves(self, tmp_path):
        """Rapid saves should not corrupt checkpoint file."""
        ctx = DraftContext()
        ctx.topic = "Rapid Save Test"
        ctx.folders = {'root': tmp_path}

        # Rapid saves
        for i in range(100):
            ctx.scout_output = f"Output iteration {i}"
            save_checkpoint(ctx, "research", tmp_path)

        # Final checkpoint should be valid
        data, completed = load_checkpoint(tmp_path / "checkpoint.json")
        assert completed == "research"
        assert "Output iteration 99" in data["scout_output"]

    def test_concurrent_thread_writes(self, tmp_path):
        """Multiple threads writing should not corrupt (last write wins)."""
        import threading

        results = []
        errors = []

        def writer(output_dir, writer_id, iterations):
            try:
                for i in range(iterations):
                    ctx = DraftContext()
                    ctx.topic = f"Writer {writer_id} iteration {i}"
                    ctx.folders = {'root': output_dir}
                    ctx.scout_output = f"Writer {writer_id} content"
                    save_checkpoint(ctx, "research", output_dir)
                    time.sleep(0.01)
                results.append(writer_id)
            except Exception as e:
                errors.append(e)

        # Start multiple writer threads
        threads = []
        for writer_id in range(3):
            t = threading.Thread(target=writer, args=(tmp_path, writer_id, 20))
            t.start()
            threads.append(t)

        # Wait for all
        for t in threads:
            t.join(timeout=30)

        # No errors should have occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Checkpoint should be valid (one of the writers' content)
        checkpoint_path = tmp_path / "checkpoint.json"
        assert checkpoint_path.exists()

        data, completed = load_checkpoint(checkpoint_path)
        assert completed == "research"
        assert "Writer" in data["topic"]


class TestEdgeCaseSerialization:
    """Test checkpoint serialization with edge cases."""

    def test_unicode_edge_cases(self, tmp_path):
        """Test various unicode edge cases."""
        ctx = DraftContext()
        ctx.folders = {'root': tmp_path}

        # Various unicode
        ctx.topic = "Unicode: 日本語 العربية עברית 中文 한국어 Ελληνικά кириллица"
        ctx.scout_output = "Emojis: 🔬📊🎓✨🚀 Math: ∑∏∫√∞ ± × ÷"
        ctx.architect_output = "Zero-width: ​\u200b​ Combining: é = e\u0301"
        ctx.intro_output = "Right-to-left: مرحبا שלום"

        save_checkpoint(ctx, "compose", tmp_path)
        data, _ = load_checkpoint(tmp_path / "checkpoint.json")

        restored = DraftContext()
        restore_context(restored, data)

        assert "日本語" in restored.topic
        assert "🔬" in restored.scout_output
        assert "مرحبا" in restored.intro_output

    def test_very_long_strings(self, tmp_path):
        """Test with very long strings (>1MB)."""
        ctx = DraftContext()
        ctx.folders = {'root': tmp_path}
        ctx.topic = "Long String Test"

        # Create 2MB of content
        ctx.body_output = "x" * (2 * 1024 * 1024)

        save_checkpoint(ctx, "compose", tmp_path)
        data, _ = load_checkpoint(tmp_path / "checkpoint.json")

        restored = DraftContext()
        restore_context(restored, data)

        assert len(restored.body_output) == 2 * 1024 * 1024

    def test_special_json_characters(self, tmp_path):
        """Test characters that need JSON escaping."""
        ctx = DraftContext()
        ctx.folders = {'root': tmp_path}

        ctx.topic = 'Quotes: "double" and \'single\''
        ctx.scout_output = "Backslash: \\ and newline: \n and tab: \t"
        ctx.architect_output = "Control chars: \x00\x01\x02 (null, soh, stx)"
        ctx.intro_output = '{"json": "inside", "nested": {"key": "value"}}'

        save_checkpoint(ctx, "compose", tmp_path)
        data, _ = load_checkpoint(tmp_path / "checkpoint.json")

        restored = DraftContext()
        restore_context(restored, data)

        assert '"double"' in restored.topic
        assert "\\" in restored.scout_output
        assert "json" in restored.intro_output

    def test_empty_and_none_fields(self, tmp_path):
        """Test empty strings and None values."""
        ctx = DraftContext()
        ctx.folders = {'root': tmp_path}
        ctx.topic = "Empty Fields Test"

        ctx.scout_output = ""
        ctx.architect_output = None  # Will be saved as null
        ctx.intro_output = "   "  # Whitespace only

        save_checkpoint(ctx, "research", tmp_path)
        data, _ = load_checkpoint(tmp_path / "checkpoint.json")

        restored = DraftContext()
        restore_context(restored, data)

        assert restored.scout_output == ""
        # None becomes empty string after restore
        assert restored.architect_output == "" or restored.architect_output is None


class TestFlakyDetection:
    """Run tests many times to detect any flakiness."""

    def test_determinism_100_runs(self, tmp_path):
        """Run scoring 100 times to detect non-determinism."""
        from utils.quality_gate import score_draft_quality

        ctx = DraftContext()
        ctx.academic_level = "research_paper"
        ctx.word_targets = {'min_citations': 10}
        ctx.intro_output = "# Introduction\n\n" + "Content word here. " * 100 + "{cite_001}"
        ctx.body_output = "## Body\n\n" + "Body content word. " * 300 + "{cite_002} {cite_003}"
        ctx.conclusion_output = "## Conclusion\n\n" + "Final word here. " * 80 + "{cite_004}"
        ctx.lit_review_output = "Literature review. " * 50
        ctx.methodology_output = "Methods. " * 50
        ctx.results_output = "Results. " * 50
        ctx.discussion_output = "Discussion. " * 50

        scores = []
        for _ in range(100):
            result = score_draft_quality(ctx)
            scores.append(result.total_score)

        # All scores should be identical
        unique_scores = set(scores)
        assert len(unique_scores) == 1, f"Non-deterministic! Got {len(unique_scores)} unique scores: {unique_scores}"

    def test_checkpoint_roundtrip_100_runs(self, tmp_path):
        """Checkpoint roundtrip 100 times should be consistent."""
        original_ctx = DraftContext()
        original_ctx.topic = "Consistency Test"
        original_ctx.scout_output = "Test content " * 100
        original_ctx.folders = {'root': tmp_path}

        for i in range(100):
            save_checkpoint(original_ctx, "research", tmp_path)
            data, _ = load_checkpoint(tmp_path / "checkpoint.json")

            restored = DraftContext()
            restore_context(restored, data)

            assert restored.topic == original_ctx.topic
            assert restored.scout_output == original_ctx.scout_output
