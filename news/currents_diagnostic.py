"""Isolated Currents News API diagnostics for selected Indian companies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import CURRENTS_API_KEY, NEWS_LOOKBACK_HOURS


CURRENTS_TEST_COMPANIES: dict[str, str] = {
    "RELIANCE.NS": "Reliance Industries",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
}
"""Small diagnostic-only mapping; it is not a production universe mapping."""

_CURRENTS_SEARCH_ENDPOINT = "https://api.currentsapi.services/v1/search"
_REQUEST_TIMEOUT_SECONDS = 10


class CurrentsDiagnosticError(ValueError):
    """Raised when a Currents diagnostic request cannot produce usable news."""


@dataclass(frozen=True, slots=True)
class CurrentsArticle:
    """Normalized Currents article fields needed for provider evaluation."""

    headline: str
    published: datetime
    source: str | None
    description: str | None


class CurrentsNewsDiagnosticClient:
    """Retrieve recent company-name news without integrating with the pipeline."""

    def fetch_recent_company_news(self, company_name: str) -> tuple[CurrentsArticle, ...]:
        """Return recent Currents articles for one explicit company-name search.

        Args:
            company_name: Human-readable company name, never a Yahoo ticker.

        Returns:
            Recent normalized articles published within the configured lookback.

        Raises:
            CurrentsDiagnosticError: If the key is unavailable or Currents
                returns an error or malformed payload.
            OSError: If the request cannot be completed.
            ValueError: If the response is not JSON.
        """
        if not CURRENTS_API_KEY:
            raise CurrentsDiagnosticError("Currents API key is not configured.")

        query = urlencode(
            {
                "keywords": company_name,
                "language": "en",
                "page_size": 10,
            }
        )
        request = Request(
            f"{_CURRENTS_SEARCH_ENDPOINT}?{query}",
            headers={"Authorization": f"Bearer {CURRENTS_API_KEY}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise CurrentsDiagnosticError(
                f"Currents request failed with HTTP status {error.code}."
            ) from error

        if not isinstance(payload, dict):
            raise CurrentsDiagnosticError("Currents returned an invalid response.")
        if payload.get("status") == "error":
            raise CurrentsDiagnosticError(str(payload.get("message", "Currents returned an error.")))
        news = payload.get("news", [])
        if not isinstance(news, list):
            raise CurrentsDiagnosticError("Currents returned an invalid news list.")

        cutoff = _utc_now() - timedelta(hours=NEWS_LOOKBACK_HOURS)
        articles = (_normalize_article(article) for article in news)
        return tuple(article for article in articles if article is not None and article.published >= cutoff)


def article_mentions_company(article: CurrentsArticle, company_name: str) -> bool:
    """Check the article's headline or description for the searched company name.

    This narrow check supports human review in the diagnostic report. It is not
    a substitute for provider-level company entity resolution and must not be
    used for trading decisions.

    Args:
        article: Normalized Currents article to inspect.
        company_name: Explicit human-readable company name searched.

    Returns:
        True when the exact company name occurs in the headline or description.

    Raises:
        None.
    """
    searchable_text = " ".join(part for part in (article.headline, article.description) if part)
    return company_name.casefold() in searchable_text.casefold()


def _normalize_article(article: Any) -> CurrentsArticle | None:
    """Normalize one Currents response article.

    Args:
        article: Untrusted item from Currents' ``news`` list.

    Returns:
        A normalized article, or None when required fields are invalid.

    Raises:
        None.
    """
    if not isinstance(article, dict):
        return None
    headline = article.get("title")
    published = _parse_published(article.get("published"))
    if not isinstance(headline, str) or published is None:
        return None
    source = article.get("author")
    description = article.get("description")
    return CurrentsArticle(
        headline=headline,
        published=published,
        source=source if isinstance(source, str) else None,
        description=description if isinstance(description, str) else None,
    )


def _parse_published(value: Any) -> datetime | None:
    """Parse Currents' timezone-aware published timestamp.

    Args:
        value: Timestamp string from a Currents article.

    Returns:
        Timezone-aware UTC datetime, or None for invalid values.

    Raises:
        None.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time.

    Returns:
        Current UTC timestamp.

    Raises:
        None.
    """
    return datetime.now(timezone.utc)
