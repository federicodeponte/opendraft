#!/usr/bin/env python3
"""
ABOUTME: Tests for offline citation validator behavior
ABOUTME: Covers CrossRef DOI retry handling for transient API failures
"""

import os
import sys

import requests

# Add engine directory to path so utils can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))

from utils.citation_validator import CitationValidator  # noqa: E402


class StubResponse:
    """Small response double for DOI validator tests."""

    def __init__(self, status_code: int):
        self.status_code = status_code


def test_validate_doi_retries_timeout_then_success(monkeypatch):
    """CrossRef DOI validation should retry transient network failures."""
    responses = [requests.exceptions.Timeout("timed out"), StubResponse(200)]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(requests, "get", fake_get)

    assert CitationValidator(timeout=1).validate_doi("10.1000/example") is True
    assert len(calls) == 2


def test_validate_doi_returns_unknown_after_retry_exhaustion(monkeypatch):
    """Persistent CrossRef network errors should preserve unknown DOI status."""
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise requests.exceptions.ConnectionError("connection failed")

    monkeypatch.setattr(requests, "get", fake_get)

    assert CitationValidator(timeout=1).validate_doi("10.1000/flaky") is None
    assert len(calls) == 3


def test_validate_doi_retries_rate_limit_then_success(monkeypatch):
    """HTTP 429 from CrossRef should be treated as transient."""
    responses = [StubResponse(429), StubResponse(200)]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    assert (
        CitationValidator(timeout=1).validate_doi("10.1000/rate-limited")
        is True
    )
    assert len(calls) == 2


def test_validate_doi_retries_server_error_then_success(monkeypatch):
    """CrossRef 5xx responses should be retried before falling back."""
    responses = [StubResponse(503), StubResponse(200)]
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    assert (
        CitationValidator(timeout=1).validate_doi("10.1000/server-error")
        is True
    )
    assert len(calls) == 2


def test_validate_doi_does_not_retry_not_found(monkeypatch):
    """HTTP 404 means the DOI was not found and should not be retried."""
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return StubResponse(404)

    monkeypatch.setattr(requests, "get", fake_get)

    assert (
        CitationValidator(timeout=1).validate_doi("10.1000/missing")
        is False
    )
    assert len(calls) == 1
