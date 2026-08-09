"""Read-only recent-news enrichment for daily reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from config import NEWS_API_KEY, NEWS_LOOKBACK_HOURS, NEWS_PROVIDER


NEWS_COLUMNS: tuple[str, ...] = (
    "NewsAvailable",
    "NewsHeadline",
    "NewsPublished",
    "NewsSentiment",
)
"""Ordered informational fields appended by ``NewsEnricher``."""


class NewsEnrichmentError(ValueError):
    """Raised when a configured news provider cannot return usable article data."""


@dataclass(frozen=True, slots=True)
class _NewsArticle:
    """Normalized article fields used to populate informational report metadata."""

    headline: str
    published: datetime
    sentiment: str | None


LOGGER = logging.getLogger(__name__)
_ALPHA_VANTAGE_ENDPOINT = "https://www.alphavantage.co/query"
_REQUEST_TIMEOUT_SECONDS = 10


class NewsEnricher:
    """Append recent provider news metadata to daily reports without trading impact."""

    def __init__(self) -> None:
        """Initialize one-run missing-configuration warning state.

        Returns:
            None.

        Raises:
            None.
        """
        self._missing_key_warning_logged = False

    def enrich(self, report: pd.DataFrame) -> pd.DataFrame:
        """Return a copied report enriched with recent provider news metadata.

        Args:
            report: Daily report DataFrame to enrich with informational metadata.

        Returns:
            A new DataFrame preserving all report rows, columns, values, and
            row order, with ``NEWS_COLUMNS`` appended. Tickers with no recent
            article or a provider failure retain unavailable-news placeholders.

        Raises:
            None.
        """
        enriched_report = report.copy()
        if not NEWS_API_KEY:
            if not self._missing_key_warning_logged:
                LOGGER.warning(
                    "News enrichment is disabled because the Alpha Vantage API key is not configured."
                )
                self._missing_key_warning_logged = True
            return _append_unavailable_news(enriched_report)

        articles_by_ticker: dict[object, _NewsArticle | None] = {}
        for ticker in report["Ticker"].drop_duplicates():
            try:
                articles_by_ticker[ticker] = _fetch_recent_article(str(ticker))
            except (NewsEnrichmentError, OSError, TypeError, ValueError) as error:
                LOGGER.error("News enrichment failed for %s: %s", ticker, error)
                articles_by_ticker[ticker] = None

        articles = report["Ticker"].map(articles_by_ticker)
        enriched_report["NewsAvailable"] = articles.map(lambda article: article is not None)
        enriched_report["NewsHeadline"] = articles.map(
            lambda article: article.headline if article is not None else None
        )
        enriched_report["NewsPublished"] = articles.map(
            lambda article: article.published if article is not None else None
        )
        enriched_report["NewsSentiment"] = articles.map(
            lambda article: article.sentiment if article is not None else None
        )
        return enriched_report


def _append_unavailable_news(report: pd.DataFrame) -> pd.DataFrame:
    """Append deterministic unavailable-news values without provider access.

    Args:
        report: Copied daily report to enrich with unavailable-news metadata.

    Returns:
        The supplied report with the stable ``NEWS_COLUMNS`` appended.

    Raises:
        None.
    """
    report["NewsAvailable"] = False
    report["NewsHeadline"] = None
    report["NewsPublished"] = None
    report["NewsSentiment"] = None
    return report


def _fetch_recent_article(ticker: str) -> _NewsArticle | None:
    """Retrieve the most relevant eligible recent article for one ticker.

    Args:
        ticker: Provider-recognized ticker symbol from the daily report.

    Returns:
        The first relevant article published within the configured lookback, or
        ``None`` when the provider returns no eligible article.

    Raises:
        NewsEnrichmentError: If provider configuration or the response is invalid.
        OSError: If the provider request cannot be completed.
        ValueError: If the provider response cannot be decoded as JSON.
    """
    if NEWS_PROVIDER != "alpha_vantage":
        raise NewsEnrichmentError(f"Unsupported news provider: {NEWS_PROVIDER!r}.")
    if not NEWS_API_KEY:
        raise NewsEnrichmentError("NEWS_API_KEY is not configured.")

    now = _utc_now()
    cutoff = now - timedelta(hours=NEWS_LOOKBACK_HOURS)
    query = urlencode(
        {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "time_from": cutoff.strftime("%Y%m%dT%H%M"),
            "sort": "RELEVANCE",
            "apikey": NEWS_API_KEY,
        }
    )
    with urlopen(f"{_ALPHA_VANTAGE_ENDPOINT}?{query}", timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise NewsEnrichmentError("News provider returned an invalid response.")
    for error_field in ("Error Message", "Information", "Note"):
        if error_message := payload.get(error_field):
            raise NewsEnrichmentError(str(error_message))

    feed = payload.get("feed", [])
    if not isinstance(feed, list):
        raise NewsEnrichmentError("News provider returned an invalid article feed.")

    for article in feed:
        normalized_article = _normalize_article(article, ticker)
        if normalized_article is not None and normalized_article.published >= cutoff:
            return normalized_article
    return None


def _normalize_article(article: Any, ticker: str) -> _NewsArticle | None:
    """Normalize one Alpha Vantage article into report metadata fields.

    Args:
        article: Candidate article object from the provider response.
        ticker: Ticker used to choose ticker-specific sentiment when available.

    Returns:
        Normalized article data, or ``None`` if required article fields are invalid.

    Raises:
        None.
    """
    if not isinstance(article, dict):
        return None

    headline = article.get("title")
    published = _parse_published_at(article.get("time_published"))
    if not isinstance(headline, str) or published is None:
        return None

    sentiment = article.get("overall_sentiment_label")
    ticker_sentiment = article.get("ticker_sentiment", [])
    if isinstance(ticker_sentiment, list):
        for item in ticker_sentiment:
            if isinstance(item, dict) and item.get("ticker") == ticker:
                sentiment = item.get("ticker_sentiment_label", sentiment)
                break

    return _NewsArticle(
        headline=headline,
        published=published,
        sentiment=sentiment if isinstance(sentiment, str) else None,
    )


def _parse_published_at(value: Any) -> datetime | None:
    """Parse Alpha Vantage's UTC article timestamp format.

    Args:
        value: Provider timestamp expected in ``YYYYMMDDTHHMMSS`` format.

    Returns:
        A timezone-aware UTC datetime, or ``None`` for an invalid timestamp.

    Raises:
        None.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time.

    Returns:
        Current UTC timestamp.

    Raises:
        None.
    """
    return datetime.now(timezone.utc)
