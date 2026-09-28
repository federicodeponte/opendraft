#!/usr/bin/env python3
"""
ABOUTME: Citation validation utility to detect hallucinated/invalid citations
ABOUTME: Uses CrossRef API to verify DOIs, URL status checks, and metadata quality validation
"""

import json
import logging
import re
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from utils.retry import retry


logger = logging.getLogger(__name__)


class _RetryableCrossrefError(requests.HTTPError):
    """CrossRef returned a transient status that should be retried."""


@dataclass
class ValidationIssue:
    """Represents a citation validation issue."""
    citation_id: str
    severity: str  # 'critical', 'warning', 'info'
    issue_type: str
    message: str
    citation_text: str


class CitationValidator:
    """Validates citations for academic integrity."""

    def __init__(self, timeout: int = 10):
        """
        Initialize validator.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.crossref_api_base = "https://api.crossref.org/works/"

    @retry(
        max_attempts=3,
        base_delay=0.5,
        max_delay=4.0,
        exceptions=(
            requests.exceptions.RequestException,
            _RetryableCrossrefError,
        ),
    )
    def _get_crossref_work(self, doi_clean: str) -> requests.Response:
        """Fetch a CrossRef work, retrying transient failures with backoff."""
        response = requests.get(
            f"{self.crossref_api_base}{doi_clean}",
            timeout=self.timeout,
            headers={
                'User-Agent': (
                    'OpenDraft/1.3 '
                    '(https://github.com/federicodeponte/opendraft)'
                )
            }
        )

        if response.status_code == 429 or response.status_code >= 500:
            logger.warning(
                (
                    "CrossRef DOI validation got HTTP %s for %s; "
                    "retrying if attempts remain"
                ),
                response.status_code,
                doi_clean,
            )
            raise _RetryableCrossrefError(
                f"CrossRef transient response: HTTP {response.status_code}",
                response=response,
            )

        return response

    def validate_doi(self, doi: str) -> Optional[bool]:
        """
        Verify if a DOI exists via CrossRef API.

        Args:
            doi: DOI to verify (can include https://doi.org/ prefix)

        Returns:
            True if DOI exists, False if DOI not found (404), None if network error
        """
        # Clean DOI (remove prefix if present)
        doi_clean = doi.replace('https://doi.org/', '').replace(
            'http://doi.org/',
            '',
        )

        try:
            response = self._get_crossref_work(doi_clean)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            # Network error - assume DOI might be valid
            return None  # Unknown

    def check_author_sanity(self, authors: List[str]) -> List[str]:
        """
        Check for suspicious author name patterns.

        Returns:
            List of issues found (empty if no issues)
        """
        issues = []

        # Check for excessive authors (likely bad data from API)
        MAX_REASONABLE_AUTHORS = 30
        if len(authors) > MAX_REASONABLE_AUTHORS:
            issues.append(f"Excessive authors ({len(authors)}) - likely malformed data")
            return issues  # Skip individual checks for malformed citations

        for author in authors:
            # Pattern 1: Repetitive initials (e.g., "N. C. A. C. B. S. C. A.")
            if re.match(r'^([A-Z]\.\s*){6,}$', author):
                issues.append(f"Repetitive initials pattern: '{author}'")

            # Pattern 2: Same first and last name (e.g., "Smith, Smith")
            parts = author.split(',')
            if len(parts) == 2:
                last, first = parts[0].strip(), parts[1].strip()
                if last and first and last.lower() == first.lower():
                    issues.append(f"Same first/last name: '{author}'")

            # Pattern 3: Initials only, no full name (e.g., "E. A. W.")
            if re.match(r'^([A-Z]\.\s*){1,3}$', author):
                issues.append(f"Initials only (incomplete): '{author}'")

            # Pattern 4: Too many consecutive same letters
            if re.search(r'([A-Z])\.\s*\1\.\s*\1\.', author):
                issues.append(f"Repetitive letters: '{author}'")

            # Pattern 5: Domain name as author (NEW - Day 10)
            if re.search(r'\.(com|org|gov|edu|net|io|ai|co\.uk)(:443)?$', author, re.IGNORECASE):
                issues.append(f"Domain name as author: '{author}'")

        return issues

    def validate_url_status(self, url: str) -> Tuple[Optional[int], str]:
        """
        Check HTTP status of URL.

        Args:
            url: URL to validate

        Returns:
            Tuple of (status_code, error_message)
            - status_code: HTTP status code (200, 403, 404, etc.) or None if error
            - error_message: Error description if request failed
        """
        if not url:
            return None, "No URL provided"

        try:
            response = requests.head(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                headers={'User-Agent': 'AcademicDraftAI/1.0 Citation Validator'}
            )

            # Some servers block HEAD, try GET
            if response.status_code == 405:
                response = requests.get(url, timeout=self.timeout, allow_redirects=True)

            return response.status_code, ""

        except requests.exceptions.Timeout:
            return None, "Timeout"
        except requests.exceptions.ConnectionError:
            return None, "Connection failed"
        except requests.exceptions.RequestException as e:
            return None, f"Request error: {str(e)[:50]}"

    def check_metadata_quality(self, citation: Dict) -> List[str]:
        """
        Check for suspicious metadata patterns.

        Returns:
            List of issues found (empty if no issues)
        """
        issues = []
        title = citation.get('title', '')
        authors = citation.get('authors', [])
        url = citation.get('url', '')
        year = citation.get('year', 0)

        # Check 1: Title is domain name
        domain_pattern = r'^[a-zA-Z0-9.-]+\.(com|org|gov|edu|net|io|ai|co\.uk)(:443)?$'
        if re.match(domain_pattern, title, re.IGNORECASE):
            issues.append(f"Domain name as title: '{title}'")

        # Check 2: Author is same as title (domain repetition)
        if authors and title and authors[0].strip().lower() == title.strip().lower():
            issues.append(f"Author duplicates title: '{authors[0]}'")

        # Check 3: URL contains error keywords
        error_keywords = ['error', '403', '404', '500', '503', 'not-found', 'forbidden']
        if url and any(keyword in url.lower() for keyword in error_keywords):
            issues.append(f"URL contains error keyword: '{url}'")

        # Check 4: Year out of reasonable range
        if year and (year < 1990 or year > 2026):
            issues.append(f"Year out of range: {year}")

        # Check 5: Empty or placeholder titles
        placeholder_titles = [
            'untitled',
            'no title',
            'unknown',
            '[title]',
            'n/a',
            'article',
            'document'
        ]
        if title.lower().strip() in placeholder_titles:
            issues.append(f"Placeholder title: '{title}'")

        return issues

    def validate_citation(self, citation: Dict) -> List[ValidationIssue]:
        """
        Validate a single citation from citation database.

        Args:
            citation: Citation dict with keys: id, authors, year, title, doi, etc.

        Returns:
            List of validation issues found
        """
        issues = []
        cite_id = citation.get('id', 'unknown')
        title = citation.get('title', '')
        authors = citation.get('authors', [])
        doi = citation.get('doi', '')

        # Format citation text for display
        author_str = ', '.join(authors[:2])
        if len(authors) > 2:
            author_str += ' et al.'
        cite_text = f"{author_str} ({citation.get('year')}) - {title[:60]}..."

        # Check 1: Author name sanity
        author_issues = self.check_author_sanity(authors)
        for issue in author_issues:
            issues.append(ValidationIssue(
                citation_id=cite_id,
                severity='critical',
                issue_type='invalid_author',
                message=issue,
                citation_text=cite_text
            ))

        # Check 2: DOI validation (if DOI provided)
        if doi:
            doi_valid = self.validate_doi(doi)
            if doi_valid is False:
                issues.append(ValidationIssue(
                    citation_id=cite_id,
                    severity='critical',
                    issue_type='invalid_doi',
                    message=f"DOI not found: {doi}",
                    citation_text=cite_text
                ))
            elif doi_valid is None:
                issues.append(ValidationIssue(
                    citation_id=cite_id,
                    severity='warning',
                    issue_type='doi_check_failed',
                    message=f"Could not verify DOI (network error): {doi}",
                    citation_text=cite_text
                ))

        # Check 3: Generic AI-generated titles
        generic_patterns = [
            r'A Systematic Review$',
            r'A Comprehensive Study$',
            r'An Overview$',
            r'A Survey$',
        ]
        for pattern in generic_patterns:
            if re.search(pattern, title):
                issues.append(ValidationIssue(
                    citation_id=cite_id,
                    severity='warning',
                    issue_type='generic_title',
                    message=f"Generic title pattern: '{pattern.strip('$')}'",
                    citation_text=cite_text
                ))

        # Check 4: Metadata quality (NEW - Day 10)
        metadata_issues = self.check_metadata_quality(citation)
        for issue in metadata_issues:
            issues.append(ValidationIssue(
                citation_id=cite_id,
                severity='critical',
                issue_type='invalid_metadata',
                message=issue,
                citation_text=cite_text
            ))

        # Check 5: URL HTTP status (NEW - Day 10)
        url = citation.get('url', '')
        if url:
            status_code, error_msg = self.validate_url_status(url)

            if status_code and status_code >= 400:
                # 4xx or 5xx errors are critical
                issues.append(ValidationIssue(
                    citation_id=cite_id,
                    severity='critical',
                    issue_type='invalid_url',
                    message=f"URL returns HTTP {status_code}: {url}",
                    citation_text=cite_text
                ))
            elif error_msg:
                # Network errors are warnings (might be temporary)
                issues.append(ValidationIssue(
                    citation_id=cite_id,
                    severity='warning',
                    issue_type='url_check_failed',
                    message=f"Could not verify URL ({error_msg}): {url}",
                    citation_text=cite_text
                ))

        return issues

    def validate_database(self, database_path: Path) -> Tuple[List[ValidationIssue], Dict]:
        """
        Validate all citations in a citation database JSON file.

        Args:
            database_path: Path to citation_database.json

        Returns:
            Tuple of (issues_list, stats_dict)
        """
        with open(database_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                import logging
                logging.getLogger(__name__).warning(f"Invalid JSON in {database_path}: {e}")
                return [], {'total_citations': 0, 'total_issues': 0,
                            'critical_issues': 0, 'warnings': 0,
                            'invalid_dois': 0, 'invalid_authors': 0,
                            'invalid_urls': 0, 'invalid_metadata': 0}

        citations = data.get('citations', [])
        all_issues = []

        print(f"🔍 Validating {len(citations)} citations from {database_path.name}...")

        for citation in citations:
            issues = self.validate_citation(citation)
            all_issues.extend(issues)

        # Compute statistics
        stats = {
            'total_citations': len(citations),
            'total_issues': len(all_issues),
            'critical_issues': sum(1 for i in all_issues if i.severity == 'critical'),
            'warnings': sum(1 for i in all_issues if i.severity == 'warning'),
            'invalid_dois': sum(1 for i in all_issues if i.issue_type == 'invalid_doi'),
            'invalid_authors': sum(1 for i in all_issues if i.issue_type == 'invalid_author'),
            'invalid_urls': sum(1 for i in all_issues if i.issue_type == 'invalid_url'),
            'invalid_metadata': sum(1 for i in all_issues if i.issue_type == 'invalid_metadata'),
        }

        return all_issues, stats

    def generate_report(self, issues: List[ValidationIssue], draft_name: str) -> str:
        """
        Generate a human-readable validation report.

        Args:
            issues: List of validation issues
            draft_name: Name of draft for report header

        Returns:
            Formatted report string
        """
        if not issues:
            return f"✅ {draft_name}: All citations passed validation!\n"

        report = [f"\n{'='*80}"]
        report.append(f"CITATION VALIDATION REPORT: {draft_name}")
        report.append(f"{'='*80}\n")

        # Group by severity
        critical = [i for i in issues if i.severity == 'critical']
        warnings = [i for i in issues if i.severity == 'warning']

        if critical:
            report.append(f"❌ CRITICAL ISSUES ({len(critical)}):")
            report.append("-" * 80)
            for issue in critical:
                report.append(f"\n[{issue.citation_id}] {issue.message}")
                report.append(f"  {issue.citation_text}")

        if warnings:
            report.append(f"\n\n⚠️  WARNINGS ({len(warnings)}):")
            report.append("-" * 80)
            for issue in warnings:
                report.append(f"\n[{issue.citation_id}] {issue.message}")
                report.append(f"  {issue.citation_text}")

        report.append(f"\n{'='*80}")
        report.append(f"TOTAL ISSUES: {len(issues)} ({len(critical)} critical, {len(warnings)} warnings)")
        report.append(f"{'='*80}\n")

        return '\n'.join(report)


def main():
    """Main entry point for CLI validation."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate citations for academic integrity')
    parser.add_argument('database', nargs='?', help='Path to citation_database.json (or validate all)')
    parser.add_argument('--all', action='store_true', help='Validate all 3 draft databases')

    args = parser.parse_args()

    validator = CitationValidator()

    # Determine which databases to validate
    if args.all or not args.database:
        base_dir = Path(__file__).parent.parent
        databases = [
            (base_dir / "tests/outputs/opensource_draft/citation_database.json", "Open Source Draft"),
            (base_dir / "tests/outputs/ai_pricing_draft/citation_database.json", "AI Pricing Draft"),
            (base_dir / "tests/outputs/co2_draft_german/citation_database.json", "CO2 German Draft"),
        ]
    else:
        databases = [(Path(args.database), Path(args.database).parent.name)]

    # Validate each database
    total_critical = 0
    total_warnings = 0

    for db_path, draft_name in databases:
        if not db_path.exists():
            print(f"⚠️  Skipping {draft_name}: Database not found at {db_path}")
            continue

        issues, stats = validator.validate_database(db_path)
        report = validator.generate_report(issues, draft_name)
        print(report)

        total_critical += stats['critical_issues']
        total_warnings += stats['warnings']

    # Final summary
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total Critical Issues: {total_critical}")
    print(f"Total Warnings: {total_warnings}")

    if total_critical > 0:
        print(f"\n❌ VALIDATION FAILED - {total_critical} critical issues found")
        print("   These citations are likely hallucinated/invalid and must be fixed.")
        return 1
    elif total_warnings > 0:
        print(f"\n⚠️  VALIDATION PASSED WITH WARNINGS - {total_warnings} warnings")
        print("   Review these citations for potential issues.")
        return 0
    else:
        print("\n✅ ALL CITATIONS VALID")
        return 0


if __name__ == '__main__':
    exit(main())
