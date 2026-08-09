"""Mocked tests for isolated Currents company-news diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from news.currents_diagnostic import (
    CURRENTS_TEST_COMPANIES,
    CurrentsDiagnosticError,
    CurrentsNewsDiagnosticClient,
    article_mentions_company,
)


class _FakeResponse:
    """Context-manager response containing an encoded Currents payload."""

    def __init__(self, payload: object) -> None:
        """Store a JSON-serializable response payload."""
        self._content = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        """Return this response for context-manager use."""
        return self

    def __exit__(self, *arguments: object) -> None:
        """Finish context-manager use without suppressing errors."""
        return None

    def read(self) -> bytes:
        """Return encoded JSON response content."""
        return self._content


class CurrentsDiagnosticTests(unittest.TestCase):
    """Verify company-name requests and safe response handling without network I/O."""

    def setUp(self) -> None:
        """Create a client and fixed clock for response filtering."""
        self.client = CurrentsNewsDiagnosticClient()
        self.now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)

    @patch("news.currents_diagnostic.CURRENTS_API_KEY", "synthetic-currents-key")
    @patch("news.currents_diagnostic._utc_now")
    @patch("news.currents_diagnostic.urlopen")
    def test_parses_recent_company_articles_and_uses_company_name_query(
        self, mock_urlopen: object, mock_now: object
    ) -> None:
        """Request a company name and retain only recent valid articles."""
        mock_now.return_value = self.now
        mock_urlopen.return_value = _FakeResponse(
            {
                "status": "ok",
                "news": [
                    {
                        "title": "Reliance Industries announces expansion",
                        "description": "Reliance Industries Limited reported an update.",
                        "author": "Example publication",
                        "published": "2026-08-07 10:00:00 +0000",
                    },
                    {
                        "title": "Old Reliance Industries item",
                        "published": "2026-08-04 10:00:00 +0000",
                    },
                ],
            }
        )

        articles = self.client.fetch_recent_company_news("Reliance Industries")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].source, "Example publication")
        self.assertTrue(article_mentions_company(articles[0], "Reliance Industries"))
        request = mock_urlopen.call_args.args[0]
        self.assertIn("keywords=Reliance+Industries", request.full_url)
        self.assertNotIn("RELIANCE.NS", request.full_url)
        self.assertNotIn("apiKey", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-currents-key")

    @patch("news.currents_diagnostic.CURRENTS_API_KEY", "")
    @patch("news.currents_diagnostic.urlopen")
    def test_missing_key_is_safe_and_does_not_make_a_request(self, mock_urlopen: object) -> None:
        """Reject missing configuration without touching the provider."""
        with self.assertRaises(CurrentsDiagnosticError):
            self.client.fetch_recent_company_news("Infosys")
        self.assertEqual(mock_urlopen.call_count, 0)

    @patch("news.currents_diagnostic.CURRENTS_API_KEY", "synthetic-currents-key")
    @patch("news.currents_diagnostic.urlopen", return_value=_FakeResponse({"status": "ok", "news": []}))
    def test_empty_response_is_safe(self, mock_urlopen: object) -> None:
        """Return no articles when Currents finds no matching news."""
        self.assertEqual(self.client.fetch_recent_company_news("Infosys"), ())

    @patch("news.currents_diagnostic.CURRENTS_API_KEY", "synthetic-currents-key")
    @patch("news.currents_diagnostic.urlopen", return_value=_FakeResponse({"status": "ok", "news": {}}))
    def test_malformed_response_raises_clear_error(self, mock_urlopen: object) -> None:
        """Reject a non-list news payload safely."""
        with self.assertRaises(CurrentsDiagnosticError):
            self.client.fetch_recent_company_news("HDFC Bank")

    @patch("news.currents_diagnostic.CURRENTS_API_KEY", "synthetic-currents-key")
    @patch("news.currents_diagnostic.urlopen")
    def test_http_403_is_safe_and_does_not_expose_the_key(self, mock_urlopen: object) -> None:
        """Convert provider denial into a safe diagnostic error message."""
        mock_urlopen.side_effect = HTTPError(
            "https://api.currentsapi.services/v1/search",
            403,
            "Forbidden",
            hdrs=None,
            fp=None,
        )

        with self.assertRaises(CurrentsDiagnosticError) as context:
            self.client.fetch_recent_company_news("Infosys")

        self.assertIn("HTTP status 403", str(context.exception))
        self.assertNotIn("synthetic-currents-key", str(context.exception))

    def test_diagnostic_mapping_is_limited_to_the_three_requested_companies(self) -> None:
        """Keep this phase free of an unverified full-universe mapping."""
        self.assertEqual(
            CURRENTS_TEST_COMPANIES,
            {
                "RELIANCE.NS": "Reliance Industries",
                "INFY.NS": "Infosys",
                "HDFCBANK.NS": "HDFC Bank",
            },
        )


if __name__ == "__main__":
    unittest.main()
