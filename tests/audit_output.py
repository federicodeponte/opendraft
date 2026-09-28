#!/usr/bin/env python3
"""
Output Auditor - Analyzes generated content for quality issues

This script generates sample content using OpenDraft prompts and
audits it for issues like:
- Overconfident claims
- Fake methodology language
- Missing citations
- Repetitive phrases
- Grammar issues
- Inconsistencies
"""

import os
import sys
import re
import socket
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from google import genai
from engine.utils.gemini_client import GeminiModelWrapper


def setup_model():
    """Configure Gemini model"""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No API key found")
    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    return GeminiModelWrapper(client, model_name)


def has_api_key():
    """Return whether a Gemini API key is configured."""
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


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


def load_prompt(prompt_path: str) -> str:
    """Load prompt file"""
    path = PROJECT_ROOT / prompt_path
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_sample_paper():
    """Generate a sample paper section for auditing"""
    model = setup_model()
    prompt = load_prompt("engine/prompts/03_compose/crafter.md")

    user_request = """
    Write a comprehensive literature review section (2000+ words) on:
    "Epigenetic Clocks: Current Applications and Clinical Potential"

    Include:
    - Introduction to epigenetic aging
    - First-generation clocks (Horvath, Hannum)
    - Second-generation clocks (PhenoAge, GrimAge)
    - Pace-of-aging clocks (DunedinPACE)
    - Clinical applications and limitations
    - Technical considerations (cell composition, batch effects)
    - Future directions

    Use citations like {cite_001}, {cite_002}, etc.
    """

    full_prompt = f"{prompt}\n\n---\n\nUser Request:\n{user_request}"

    print("Generating sample paper...")
    response = model.generate_content(full_prompt)
    return response.text


class OutputAuditor:
    """Audits generated content for quality issues"""

    def __init__(self, text: str):
        self.text = text
        self.issues = []
        self.warnings = []
        self.stats = {}

    def audit_all(self):
        """Run all audits"""
        self.audit_overconfident_claims()
        self.audit_fake_methodology()
        self.audit_citations()
        self.audit_repetition()
        self.audit_grammar()
        self.audit_technical_precision()
        self.audit_document_consistency()
        self.audit_hedging()
        self.audit_banned_phrases()
        self.audit_leaked_metadata()
        self.audit_missing_citations()
        self.audit_planning_leakage()
        return self

    def audit_overconfident_claims(self):
        """Check for overconfident language"""
        overconfident_patterns = [
            (r'\bindisputable\b', "indisputable"),
            (r'\bproves conclusively\b', "proves conclusively"),
            (r'\bwithout doubt\b', "without doubt"),
            (r'\bthe only\b', "the only"),
            (r'\bthe best\b', "the best"),
            (r'\brevolutionary\b', "revolutionary"),
            (r'\bparadigm shift\b', "paradigm shift"),
            (r'\balways\b', "always"),
            (r'\bnever\b', "never"),
            (r'\bperfect\b', "perfect"),
            (r'\bsolves\b', "solves (should be 'addresses')"),
            (r'\bproves\b', "proves (should be 'supports')"),
            (r'\bundeniable\b', "undeniable"),
            (r'\bunquestionable\b', "unquestionable"),
            (r'\bdefinitively\b', "definitively"),
        ]

        found = []
        for pattern, description in overconfident_patterns:
            matches = re.findall(pattern, self.text, re.IGNORECASE)
            if matches:
                found.append(f"'{description}' ({len(matches)}x)")

        if found:
            self.issues.append(f"OVERCONFIDENT CLAIMS: {', '.join(found)}")

        self.stats['overconfident_count'] = len(found)

    def audit_fake_methodology(self):
        """Check for fake systematic review language"""
        fake_patterns = [
            (r'systematic review', "systematic review (should be 'narrative review')"),
            (r'PRISMA', "PRISMA (not applicable)"),
            (r'records identified', "records identified (fake PRISMA)"),
            (r'records screened', "records screened (fake PRISMA)"),
            (r'duplicates removed', "duplicates removed (fake PRISMA)"),
            (r'inter-rater', "inter-rater reliability (not applicable)"),
            (r'risk of bias assessment', "risk of bias (not applicable)"),
            (r'quality assessment.*conducted', "quality assessment conducted"),
        ]

        found = []
        for pattern, description in fake_patterns:
            if re.search(pattern, self.text, re.IGNORECASE):
                found.append(description)

        if found:
            self.issues.append(f"FAKE METHODOLOGY: {', '.join(found)}")

        # Check for correct methodology language
        if re.search(r'narrative review', self.text, re.IGNORECASE):
            self.stats['has_narrative_review'] = True
        else:
            self.warnings.append("Missing 'narrative review' declaration")

    def audit_citations(self):
        """Check citation patterns"""
        # Count citations
        citations = re.findall(r'\{cite_\d+\}', self.text)
        self.stats['citation_count'] = len(citations)

        # Check for uncited claims (statistics without citations)
        uncited_stats = re.findall(
            r'(\d+(?:\.\d+)?%|\d+(?:\.\d+)? percent)(?![^{]*\{cite_)',
            self.text
        )
        if uncited_stats:
            self.warnings.append(f"UNCITED STATISTICS: {len(uncited_stats)} percentages without citations")

        # Check citation density (should have ~1 citation per 100-150 words)
        word_count = len(self.text.split())
        expected_citations = word_count // 125
        if len(citations) < expected_citations * 0.5:
            self.warnings.append(f"LOW CITATION DENSITY: {len(citations)} citations for {word_count} words")

        # Check for [VERIFY] markers
        verify_count = len(re.findall(r'\[VERIFY\]', self.text))
        if verify_count > 0:
            self.warnings.append(f"UNVERIFIED CLAIMS: {verify_count} [VERIFY] markers")

        self.stats['uncited_stats'] = len(uncited_stats)

    def audit_repetition(self):
        """Check for repetitive phrases"""
        # Find repeated phrases (3+ words)
        words = self.text.lower().split()
        phrases = []
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            # Filter out common phrases
            if not any(x in phrase for x in ['of the', 'in the', 'to the', 'and the', 'for the']):
                phrases.append(phrase)

        phrase_counts = Counter(phrases)
        repeated = [(p, c) for p, c in phrase_counts.items() if c > 2]

        if repeated:
            top_repeated = sorted(repeated, key=lambda x: -x[1])[:5]
            self.warnings.append(f"REPEATED PHRASES: {', '.join([f'{p} ({c}x)' for p, c in top_repeated])}")

        # Check crutch words
        crutch_words = ['significant', 'important', 'notable', 'interesting', 'clearly']
        for word in crutch_words:
            count = len(re.findall(rf'\b{word}\w*\b', self.text, re.IGNORECASE))
            if count > 5:
                self.warnings.append(f"OVERUSED WORD: '{word}' appears {count} times")

        self.stats['repeated_phrases'] = len(repeated)

    def audit_grammar(self):
        """Check common grammar issues"""
        # Data plurality
        if re.search(r'\bdata (is|was|has)\b', self.text, re.IGNORECASE):
            self.warnings.append("GRAMMAR: 'data' used as singular (should be plural: 'data are/were/have')")

        # Which vs that
        which_errors = re.findall(r'\w+\s+which\s+\w+', self.text)
        # This is a rough check - not all 'which' usages are wrong

        self.stats['data_as_singular'] = bool(re.search(r'\bdata (is|was|has)\b', self.text, re.IGNORECASE))

    def audit_technical_precision(self):
        """Check for imprecise technical descriptions"""
        imprecise_patterns = [
            (r'measures? (biological )?aging', "Imprecise: 'measures aging' - should specify what is predicted"),
            (r'trained on.*rate of change', "Imprecise: DunedinPACE description - should clarify derivation chain"),
        ]

        for pattern, description in imprecise_patterns:
            if re.search(pattern, self.text, re.IGNORECASE):
                self.warnings.append(f"TECHNICAL PRECISION: {description}")

    def audit_document_consistency(self):
        """Check for document type consistency"""
        paper_refs = len(re.findall(r'\bthis paper\b', self.text, re.IGNORECASE))
        thesis_refs = len(re.findall(r'\bthis thesis\b', self.text, re.IGNORECASE))
        study_refs = len(re.findall(r'\bthis study\b', self.text, re.IGNORECASE))
        review_refs = len(re.findall(r'\bthis review\b', self.text, re.IGNORECASE))

        types_used = []
        if paper_refs: types_used.append(f"paper ({paper_refs})")
        if thesis_refs: types_used.append(f"thesis ({thesis_refs})")
        if study_refs: types_used.append(f"study ({study_refs})")
        if review_refs: types_used.append(f"review ({review_refs})")

        if len(types_used) > 1:
            self.warnings.append(f"DOCUMENT TYPE INCONSISTENCY: Mixed references - {', '.join(types_used)}")

        self.stats['document_types'] = types_used

    def audit_hedging(self):
        """Check hedging language balance"""
        strong_hedges = len(re.findall(r'\b(suggests?|indicates?|may|might|could|appears?)\b', self.text, re.IGNORECASE))
        strong_claims = len(re.findall(r'\b(demonstrates?|shows?|proves?|establishes?|confirms?)\b', self.text, re.IGNORECASE))

        self.stats['hedges'] = strong_hedges
        self.stats['strong_claims'] = strong_claims

        if strong_claims > strong_hedges * 2:
            self.warnings.append(f"HEDGING IMBALANCE: {strong_claims} strong claims vs {strong_hedges} hedged statements")

    def audit_banned_phrases(self):
        """Check for discovery tool links and other banned content"""
        banned_urls = [
            (r'semanticscholar\.org', "Semantic Scholar link"),
            (r'scholar\.google', "Google Scholar link"),
            (r'researchgate\.net', "ResearchGate link"),
            (r'academia\.edu', "Academia.edu link"),
        ]

        for pattern, description in banned_urls:
            if re.search(pattern, self.text, re.IGNORECASE):
                self.issues.append(f"BANNED URL: {description} found")

    def audit_leaked_metadata(self):
        """Check for metadata that should not appear in output"""
        metadata_patterns = [
            (r'\*\*Section:\*\*', "Section metadata leaked"),
            (r'\*\*Word Count:\*\*', "Word count metadata leaked"),
            (r'\*\*Status:\*\*.*Draft', "Status metadata leaked"),
            (r'\*\*Citations Used\*\*', "Citations summary leaked"),
            (r'\*\*Notes for Revision\*\*', "Revision notes leaked"),
            (r'## Citations Used', "Citations section leaked"),
            (r'## Notes for', "Notes section leaked"),
            (r'\[TODO\]', "TODO markers in output"),
        ]

        found = []
        for pattern, description in metadata_patterns:
            if re.search(pattern, self.text, re.IGNORECASE):
                found.append(description)

        if found:
            self.issues.append(f"LEAKED METADATA: {', '.join(found)}")

        self.stats['leaked_metadata'] = len(found)

    def audit_missing_citations(self):
        """Check for MISSING citation markers"""
        missing = re.findall(r'\{cite_MISSING[^}]*\}', self.text)
        if missing:
            self.issues.append(f"MISSING CITATIONS: {len(missing)} cite_MISSING markers found")
            # Show first few examples
            examples = missing[:3]
            for ex in examples:
                self.warnings.append(f"  Example: {ex[:60]}...")

        self.stats['missing_citations'] = len(missing)

    def audit_planning_leakage(self):
        """Check for planning/thinking content that leaked into output"""
        planning_patterns = [
            (r'^Okay,? I (understand|will|am going)', "Planning preamble leaked"),
            (r"Here's (the plan|my plan|the output)", "Planning statement leaked"),
            (r'\d+\.\s+\*\*[A-Z][^*]+\*\*:', "Numbered planning steps leaked"),
            (r'I will (write|generate|create|ensure)', "Intent statement leaked"),
            (r'Before (writing|generating|I begin)', "Pre-writing statement leaked"),
            (r'Let me (first|start|begin)', "Let me statement leaked"),
        ]

        found = []
        for pattern, description in planning_patterns:
            if re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE):
                found.append(description)

        if found:
            self.issues.append(f"PLANNING LEAKAGE: {', '.join(found)}")

        self.stats['planning_leakage'] = len(found)

    def report(self):
        """Generate audit report"""
        print("\n" + "="*70)
        print("OUTPUT AUDIT REPORT")
        print("="*70)

        # Stats
        print("\n📊 STATISTICS")
        print("-"*40)
        print(f"  Word count: {len(self.text.split())}")
        print(f"  Citation count: {self.stats.get('citation_count', 0)}")
        print(f"  Hedged statements: {self.stats.get('hedges', 0)}")
        print(f"  Strong claims: {self.stats.get('strong_claims', 0)}")

        # Issues (critical)
        if self.issues:
            print("\n🔴 CRITICAL ISSUES")
            print("-"*40)
            for issue in self.issues:
                print(f"  ❌ {issue}")
        else:
            print("\n✅ No critical issues found")

        # Warnings
        if self.warnings:
            print("\n🟡 WARNINGS")
            print("-"*40)
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")
        else:
            print("\n✅ No warnings")

        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"  Critical issues: {len(self.issues)}")
        print(f"  Warnings: {len(self.warnings)}")

        if len(self.issues) == 0 and len(self.warnings) <= 3:
            print("\n  ✅ OUTPUT QUALITY: GOOD")
        elif len(self.issues) == 0:
            print("\n  🟡 OUTPUT QUALITY: ACCEPTABLE (minor issues)")
        else:
            print("\n  ❌ OUTPUT QUALITY: NEEDS IMPROVEMENT")

        return len(self.issues), len(self.warnings)


def main():
    print("="*70)
    print("OPENDRAFT OUTPUT AUDITOR")
    print("="*70)

    if not has_api_key():
        print("\n⏭️  SKIP: No GOOGLE_API_KEY/GEMINI_API_KEY configured")
        return 0

    ready, reason = network_ready()
    if not ready:
        print(f"\n⏭️  SKIP: Network/DNS unavailable for Gemini endpoint ({reason})")
        return 0

    try:
        # Generate sample content
        text = generate_sample_paper()

        print(f"\nGenerated {len(text.split())} words")
        print("\nPreview (first 500 chars):")
        print("-"*40)
        print(text[:500] + "...")

        # Run audit
        auditor = OutputAuditor(text)
        auditor.audit_all()
        issues, warnings = auditor.report()

        # Save output for manual review
        output_path = PROJECT_ROOT / "tests" / "audit_sample.md"
        with open(output_path, 'w') as f:
            f.write(text)
        print(f"\n📄 Full output saved to: {output_path}")

        return 0 if issues == 0 else 1

    except Exception as e:
        if is_network_error(e):
            print(f"\n⏭️  SKIP: Network unavailable during live generation ({e})")
            return 0
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
