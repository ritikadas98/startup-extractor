"""Base class every source scraper extends. A scraper only discovers articles
(URL + title + date); full text is fetched separately by fetch_text.py."""
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from database.models import ScrapedArticle
from utils import http
from utils.logger import get_logger

log = get_logger("scraper")


def parse_feed(feed_url: str):
    """Fetch a feed over our HTTP session (OS trust store, real UA) and parse it."""
    try:
        resp = http.get(feed_url)
    except requests.RequestException as e:
        log.warning("feed fetch failed %s: %s", feed_url, e)
        return None
    return feedparser.parse(resp.content)

FUNDING_KEYWORDS = (
    "raise", "raises", "raised", "funding", "funds", "series a", "series b",
    "series c", "seed", "pre-seed", "investment", "invests", "backed",
    "valuation", "round", "crore", "million", "mn", "venture",
)


def looks_like_funding_news(title: str, summary: str = "") -> bool:
    text = f"{title} {summary}".lower()
    return any(k in text for k in FUNDING_KEYWORDS)


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    def discover(self, days_back: int = 1) -> list[ScrapedArticle]:
        """Return candidate articles published within days_back."""


class RSSFeedScraper(BaseScraper):
    """Generic RSS scraper: subclasses set name + feed_url."""
    feed_url: str = ""

    def __init__(self, feed_url: str | None = None):
        if feed_url:
            self.feed_url = feed_url

    def discover(self, days_back: int = 1) -> list[ScrapedArticle]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        parsed = parse_feed(self.feed_url)
        if parsed is None or (parsed.bozo and not parsed.entries):
            if parsed is not None:
                log.warning("%s: feed error: %s", self.name, parsed.get("bozo_exception"))
            return []
        articles = []
        for e in parsed.entries:
            published = _entry_datetime(e)
            if published and published < cutoff:
                continue
            title = e.get("title", "")
            summary = e.get("summary", "")
            if not looks_like_funding_news(title, summary):
                continue
            articles.append(ScrapedArticle(
                url=e.get("link", ""), title=title, source=self.name,
                published_at=published, summary=summary,
            ))
        log.info("%s: %d funding candidates (of %d entries)",
                 self.name, len(articles), len(parsed.entries))
        return articles


def _entry_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None
