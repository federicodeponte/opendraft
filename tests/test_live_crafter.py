#!/usr/bin/env python3
"""
Live test for TICKET-001 and TICKET-002

Runs the crafter agent with methodology and analysis requests,
then checks output for forbidden/required patterns.

Run with: python tests/test_live_crafter.py
"""

import sys
import os
import socket
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment with override to ensure fresh values
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from google import genai
from engine.utils.gemini_client import GeminiModelWrapper


def load_prompt(prompt_path: str) -> str:
    """Load prompt file"""
    path = PROJECT_ROOT / prompt_path
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def setup_model():
    """Setup Gemini model"""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    return GeminiModelWrapper(client, model_name)


def has_api_key():
    """Return whether a Gemini API key is configured."""
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def network_ready():
    """Check DNS reachability for Gemini endpoint."""
    try:
        socket.getaddrinfo("generativelanguage.googleapis.com", 443, proto=socket.IPPROTO_TCP)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def is_network_error(exc: Exception) -> bool:
    """Detect connectivity errors for graceful skip behavior."""
    if isinstance(exc, OSError):
        return True
    error_text = str(exc).lower()
    markers = [
        "connecterror",
        "connection error",
        "timed out",
        "deadline exceeded",
        "temporary failure in name resolution",
        "name or service not known",
        "nodename nor servname",
        "[errno 8]",
    ]
    return any(marker in error_text for marker in markers)

# TICKET-001: Forbidden methodology phrases
FORBIDDEN_METHODOLOGY = [
    "systematic review was conducted",
    "following PRISMA guidelines",
    "PRISMA flow",
    "records identified",
    "records screened",
    "duplicates removed (n=",
    "inter-rater reliability",
]

# TICKET-002: Required analysis elements
REQUIRED_ANALYSIS = [
    # At least one of these metric types
    ("HR", "AUC", "r²", "r=", "CI", "n=", "p<", "p =", "effect size", "Cohen"),
]


def run_crafter_test(test_name: str, user_input: str, checks: dict):
    """Run crafter with input and check output"""
    print(f"\n{'='*60}")
    print(f"LIVE TEST: {test_name}")
    print("="*60)

    try:
        # Setup model
        model = setup_model()

        # Load crafter prompt
        prompt = load_prompt("engine/prompts/03_compose/crafter.md")
        full_prompt = f"{prompt}\n\n---\n\nUser Request:\n{user_input}"

        print("  Running crafter agent...")
        response = model.generate_content(full_prompt)
        output = response.text

        print(f"  Output length: {len(output)} chars")
        print(f"  Preview: {output[:300]}...")

        # Check forbidden phrases
        all_passed = True

        if "forbidden" in checks:
            print("\n  Checking for forbidden phrases...")
            found_forbidden = []
            for phrase in checks["forbidden"]:
                if phrase.lower() in output.lower():
                    found_forbidden.append(phrase)

            if found_forbidden:
                print(f"  ❌ FAIL: Found forbidden phrases: {found_forbidden}")
                all_passed = False
            else:
                print("  ✅ PASS: No forbidden phrases found")

        # Check required phrases (at least one from each group)
        if "required_any" in checks:
            print("\n  Checking for required elements...")
            for phrase_group in checks["required_any"]:
                found = any(p.lower() in output.lower() for p in phrase_group)
                if found:
                    print(f"  ✅ PASS: Found metric/data element from {phrase_group[:3]}...")
                else:
                    print(f"  ❌ FAIL: Missing metrics - need one of {phrase_group}")
                    all_passed = False

        # Check for tables
        if checks.get("require_table"):
            print("\n  Checking for comparison table...")
            has_table = "|" in output and "---" in output
            if has_table:
                print("  ✅ PASS: Found markdown table")
            else:
                print("  ⚠️  WARNING: No markdown table found (may still be valid)")

        return all_passed

    except Exception as e:
        if is_network_error(e):
            print(f"  ⏭️  SKIP: Network unavailable during live call ({e})")
            return None
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("LIVE CRAFTER TESTS - TICKET-001 & TICKET-002")
    print("="*60)

    if not has_api_key():
        print("⏭️  SKIP: No GOOGLE_API_KEY/GEMINI_API_KEY configured")
        return 0

    ready, reason = network_ready()
    if not ready:
        print(f"⏭️  SKIP: Network/DNS unavailable for Gemini endpoint ({reason})")
        return 0

    results = {}

    # Test 1: Methodology section (TICKET-001)
    results["methodology"] = run_crafter_test(
        "Methodology Section (TICKET-001)",
        """
        Write a methodology section for a literature review paper on:
        "Machine learning approaches to cancer detection"

        The paper includes 42 academic sources from Semantic Scholar and CrossRef.
        Search terms: "machine learning cancer", "deep learning oncology", "AI tumor detection"
        Date range: 2019-2024.
        This is a narrative review, not a systematic review.
        """,
        checks={
            "forbidden": FORBIDDEN_METHODOLOGY,
        }
    )

    # Test 2: Analysis section (TICKET-002)
    results["analysis"] = run_crafter_test(
        "Analysis Section (TICKET-002)",
        """
        Write a results/analysis section comparing machine learning models for cancer detection.

        Include findings from these papers:
        - Smith et al. (2023): CNN achieved AUC 0.94 (n=1,200 patients)
        - Chen et al. (2022): Random Forest achieved AUC 0.87 (n=800 patients)
        - Kumar et al. (2024): Transformer model achieved AUC 0.96 (n=2,500 patients)

        Create a comparison table and synthesize the findings.
        """,
        checks={
            "required_any": REQUIRED_ANALYSIS,
            "require_table": True,
        }
    )

    # Test 3: Preprint preference (TICKET-004)
    results["preprint"] = run_crafter_test(
        "Preprint vs Journal Preference (TICKET-004)",
        """
        Write a brief paragraph citing this study. You have two citation options:

        Available citations:
        - cite_001: Smith et al. (2021) bioRxiv preprint, doi:10.1101/2021.05.01.442345
        - cite_002: Smith et al. (2022) Nature Communications, doi:10.1038/s41467-022-12345

        Both are the SAME study - cite_002 is the published journal version of cite_001.

        Write about their finding that "AI improves diagnostic accuracy by 25%".
        Use the CORRECT citation (the journal version, not the preprint).
        """,
        checks={
            "required_any": [("cite_002", "Nature Communications", "2022")],
            "forbidden": ["cite_001", "bioRxiv", "preprint"],
        }
    )

    # Test 4: No padding citations (TICKET-005)
    results["no_padding"] = run_crafter_test(
        "No Padding Citations (TICKET-005)",
        """
        Write a paragraph about epigenetic aging for a biology paper.

        Available citations:
        - cite_001: Horvath (2013) "DNA methylation age of human tissues" (seminal epigenetic clock paper)
        - cite_002: Lu et al. (2019) "DNA methylation GrimAge" (mortality predictor clock)
        - cite_003: Smith (2020) "Cybersecurity trends in Southeast Asia" (UNRELATED - about hacking)
        - cite_004: Jones (2021) "Digital transformation in Indonesian banking" (UNRELATED - economics)

        ONLY cite relevant biology papers. Do NOT cite the cybersecurity or economics papers.
        """,
        checks={
            "required_any": [("cite_001", "cite_002", "Horvath", "GrimAge")],
            "forbidden": ["cite_003", "cite_004", "cybersecurity", "Indonesia", "banking"],
        }
    )

    # Test 5: Named entity citation (TICKET-003)
    results["named_entity"] = run_crafter_test(
        "Named Entity Citation (TICKET-003)",
        """
        Write a paragraph about deep learning epigenetic clocks for a literature review.

        Mention these specific tools by name and cite them correctly:
        - DeepMAge (created by Galkin et al.)
        - GrimAge (created by Lu et al.)

        Available citations:
        - cite_001: Galkin et al. (2021) "DeepMAge: A Deep Learning Approach..." (DeepMAge origin paper)
        - cite_002: Lu et al. (2019) "DNA methylation GrimAge..." (GrimAge origin paper)
        - cite_003: Smith et al. (2022) "Deep learning methods for age prediction" (general concept paper)

        Use the correct citation IDs for each named tool.
        """,
        checks={
            "required_any": [("cite_001", "cite_002", "DeepMAge", "GrimAge")],
        }
    )

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    for name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⏭️  SKIP"
        print(f"  {status}: {name}")

    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
