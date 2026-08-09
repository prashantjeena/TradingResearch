"""Tests for Phase 20 provider-backed news enrichment."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
import json
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from news.news_enrichment import NEWS_COLUMNS, NewsEnricher


class _FakeResponse:
    """Context-manager response containing an encoded provider payload."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store a JSON-serializable provider payload.

        Args:
            payload: Simulated Alpha Vantage JSON response.

        Returns:
            None.

        Raises:
            None.
        """
        self._content = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        """Return the simulated response for a context manager.

        Returns:
            This simulated response.

        Raises:
            None.
        """
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        """Complete the simulated response context without suppression.

        Args:
            exception_type: Type of any raised exception.
            exception: Raised exception instance, if any.
            traceback: Traceback object, if any.

        Returns:
            None.

        Raises:
            None.
        """
        return None

    def read(self) -> bytes:
        """Return the encoded mock provider payload.

        Returns:
            JSON payload bytes.

        Raises:
            None.
        """
        return self._content


class NewsEnricherTests(unittest.TestCase):
    """Verify resilient provider-backed informational enrichment."""

    def setUp(self) -> None:
        """Create an enricher and a representative daily report.

        Returns:
            None.

        Raises:
            None.
        """
        self.enricher = NewsEnricher()
        self.report = pd.DataFrame(
            {
                "Rank": [1, 2],
                "Ticker": ["INFY.NS", "RELIANCE.NS"],
                "EntryDate": pd.to_datetime(["2024-01-10", "2024-01-09"]),
                "RankScore": [10, 8],
            }
        )

    def test_empty_input_returns_empty_frame_with_news_columns(self) -> None:
        """Append the stable news schema without adding rows.

        Returns:
            None.

        Raises:
            None.
        """
        empty_report = self.report.iloc[0:0]

        result = self.enricher.enrich(empty_report)

        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), [*empty_report.columns, *NEWS_COLUMNS])

    @patch("news.news_enrichment.NEWS_API_KEY", "test-key")
    @patch("news.news_enrichment._utc_now", return_value=datetime(2026, 8, 7, 12, tzinfo=timezone.utc))
    @patch("news.news_enrichment.urlopen")
    def test_successful_enrichment_uses_most_relevant_recent_article(
        self,
        mock_urlopen: object,
        mock_now: object,
    ) -> None:
        """Populate each news field from the most relevant recent article.

        Returns:
            None.

        Raises:
            None.
        """
        mock_urlopen.return_value = _FakeResponse(
            {
                "feed": [
                    {
                        "title": "Most relevant article",
                        "time_published": "20260807T090000",
                        "overall_sentiment_label": "Neutral",
                        "ticker_sentiment": [
                            {"ticker": "INFY.NS", "ticker_sentiment_label": "Bullish"}
                        ],
                    },
                    {
                        "title": "Less relevant article",
                        "time_published": "20260807T100000",
                        "overall_sentiment_label": "Bearish",
                    },
                ]
            }
        )

        result = self.enricher.enrich(self.report.iloc[[0]])

        self.assertTrue(result.iloc[0]["NewsAvailable"])
        self.assertEqual(result.iloc[0]["NewsHeadline"], "Most relevant article")
        self.assertEqual(result.iloc[0]["NewsPublished"], datetime(2026, 8, 7, 9, tzinfo=timezone.utc))
        self.assertEqual(result.iloc[0]["NewsSentiment"], "Bullish")

    @patch("news.news_enrichment.NEWS_API_KEY", "test-key")
    @patch("news.news_enrichment._utc_now", return_value=datetime(2026, 8, 7, 12, tzinfo=timezone.utc))
    @patch("news.news_enrichment.urlopen", return_value=_FakeResponse({"feed": []}))
    def test_no_news_found_keeps_placeholders(self, mock_urlopen: object, mock_now: object) -> None:
        """Leave all news fields unavailable when the provider finds no articles.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.enricher.enrich(self.report.iloc[[0]])

        self.assertFalse(result.iloc[0]["NewsAvailable"])
        for column in NEWS_COLUMNS[1:]:
            self.assertTrue(pd.isna(result.iloc[0][column]))

    @patch("news.news_enrichment.NEWS_API_KEY", "test-key")
    @patch("news.news_enrichment.urlopen", side_effect=OSError("provider unavailable"))
    def test_provider_failure_is_logged_and_does_not_fail_report(
        self,
        mock_urlopen: object,
    ) -> None:
        """Keep placeholders and continue when a provider request fails.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertLogs("news.news_enrichment", level="ERROR"):
            result = self.enricher.enrich(self.report.iloc[[0]])

        self.assertFalse(result.iloc[0]["NewsAvailable"])

    @patch("news.news_enrichment.NEWS_API_KEY", "synthetic-test-key")
    @patch("news.news_enrichment.urlopen", side_effect=OSError("provider unavailable"))
    def test_logs_never_include_the_api_key(
        self,
        mock_urlopen: object,
    ) -> None:
        """Keep provider-error logging free of configured secret values.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertLogs("news.news_enrichment", level="ERROR") as captured_logs:
            self.enricher.enrich(self.report.iloc[[0]])

        self.assertNotIn("synthetic-test-key", "\n".join(captured_logs.output))

    @patch("news.news_enrichment.NEWS_API_KEY", "")
    @patch("news.news_enrichment.urlopen")
    def test_blank_key_disables_news_once_without_provider_calls(
        self,
        mock_urlopen: object,
    ) -> None:
        """Warn once and retain placeholders when no local key is configured.

        Returns:
            None.

        Raises:
            None.
        """
        with self.assertLogs("news.news_enrichment", level="WARNING") as captured_logs:
            first = self.enricher.enrich(self.report.iloc[[0]])
            second = self.enricher.enrich(self.report.iloc[[1]])

        self.assertEqual(len(captured_logs.records), 1)
        self.assertFalse(first.iloc[0]["NewsAvailable"])
        self.assertFalse(second.iloc[0]["NewsAvailable"])
        self.assertEqual(mock_urlopen.call_count, 0)

    @patch("news.news_enrichment.NEWS_API_KEY", "test-key")
    @patch("news.news_enrichment._utc_now", return_value=datetime(2026, 8, 7, 12, tzinfo=timezone.utc))
    @patch("news.news_enrichment.urlopen")
    def test_multiple_tickers_are_enriched_independently(
        self,
        mock_urlopen: object,
        mock_now: object,
    ) -> None:
        """Request and map one recent article independently for each ticker.

        Returns:
            None.

        Raises:
            None.
        """
        mock_urlopen.side_effect = [
            _FakeResponse(
                {
                    "feed": [
                        {
                            "title": "Infosys news",
                            "time_published": "20260807T090000",
                            "overall_sentiment_label": "Bullish",
                        }
                    ]
                }
            ),
            _FakeResponse(
                {
                    "feed": [
                        {
                            "title": "Reliance news",
                            "time_published": "20260807T080000",
                            "overall_sentiment_label": "Bearish",
                        }
                    ]
                }
            ),
        ]

        result = self.enricher.enrich(self.report)

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(list(result["NewsHeadline"]), ["Infosys news", "Reliance news"])

    @patch("news.news_enrichment._fetch_recent_article", return_value=None)
    def test_source_columns_values_and_row_order_are_preserved(self, mock_fetch: object) -> None:
        """Retain every original report value and its existing row sequence.

        Returns:
            None.

        Raises:
            None.
        """
        result = self.enricher.enrich(self.report)

        assert_frame_equal(result.loc[:, self.report.columns], self.report)
        self.assertEqual(list(result.index), list(self.report.index))

    @patch("news.news_enrichment._fetch_recent_article", return_value=None)
    def test_enrich_does_not_mutate_input(self, mock_fetch: object) -> None:
        """Leave the supplied daily report unchanged.

        Returns:
            None.

        Raises:
            None.
        """
        original = self.report.copy(deep=True)

        self.enricher.enrich(self.report)

        assert_frame_equal(self.report, original)

if __name__ == "__main__":
    unittest.main()
