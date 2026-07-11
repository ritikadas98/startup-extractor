"""Google News RSS search scraper. Google News links point at news.google.com
redirect URLs; we decode them back to the publisher URL so dedup works across
sources and text fetching hits the real page. Old-format ids decode offline
from base64; new-format ids need Google's internal batchexecute endpoint."""
import base64
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

from database.models import ScrapedArticle
from scrapers.base_scraper import BaseScraper, looks_like_funding_news, _entry_datetime, parse_feed
from utils import http
from utils.logger import get_logger

log = get_logger("google_news")

RSS_SEARCH = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
BATCHEXECUTE = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def _decode_offline(article_id: str) -> str | None:
    """Old-format ids embed the URL in base64."""
    try:
        decoded = base64.urlsafe_b64decode(article_id + "===")
        start = decoded.find(b"http")
        if start == -1:
            return None
        end = decoded.find(b"\xd2", start)
        candidate = (decoded[start:end] if end != -1 else decoded[start:]).decode("utf-8", "ignore")
        candidate = candidate.split("\x01")[0].strip()
        return candidate if candidate.startswith("http") else None
    except Exception:
        return None


def _decode_via_api(article_id: str) -> str | None:
    """New-format (AU_yqL…) ids: fetch signature+timestamp from the article page,
    then ask batchexecute for the real URL."""
    try:
        from bs4 import BeautifulSoup
        page = http.get(f"https://news.google.com/rss/articles/{article_id}")
        div = BeautifulSoup(page.text, "lxml").select_one("c-wiz > div[data-n-a-sg]")
        if div is None:
            return None
        signature, timestamp = div["data-n-a-sg"], div["data-n-a-ts"]
        inner = [
            "garturlreq",
            [["X", "X", ["X", "X"], None, None, 1, 1, "IN:en", None, 1,
              None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id, int(timestamp), signature,
        ]
        payload = "f.req=" + quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]]))
        resp = requests.post(
            BATCHEXECUTE, data=payload, timeout=20,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                     "User-Agent": http.USER_AGENTS[0]},
        )
        resp.raise_for_status()
        chunk = json.loads(resp.text.split("\n\n")[1])
        return json.loads(chunk[0][2])[1]
    except Exception as e:
        log.debug("api decode failed for %s: %s", article_id[:24], e)
        return None


def decode_google_news_url(url: str) -> str:
    if "news.google.com" not in url or "/articles/" not in url:
        return url
    article_id = url.split("/articles/")[1].split("?")[0]
    return _decode_offline(article_id) or _decode_via_api(article_id) or url


class GoogleNewsRSS(BaseScraper):
    name = "google_news"

    def __init__(self, queries: list[str] | None = None):
        self.queries = queries or ["indian startup raises funding"]

    def discover(self, days_back: int = 1) -> list[ScrapedArticle]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        seen: set[str] = set()
        articles: list[ScrapedArticle] = []
        for query in self.queries:
            # when: caps out around 30d; older windows go through discover_window()
            q = f"{query} when:{days_back}d" if days_back <= 30 else query
            self._collect(q, seen, articles, cutoff=cutoff)
        log.info("google_news: %d unique funding candidates across %d queries",
                 len(articles), len(self.queries))
        return articles

    def discover_window(self, start, end) -> list[ScrapedArticle]:
        """Historical discovery for the backfill: after:/before: date operators.

        start/end are dates; the window is [start, end). Google returns at most
        ~100 entries per query, so keep windows to ~a week.
        """
        seen: set[str] = set()
        articles: list[ScrapedArticle] = []
        for query in self.queries:
            q = f"{query} after:{start.isoformat()} before:{end.isoformat()}"
            self._collect(q, seen, articles)
        log.info("google_news window %s→%s: %d unique funding candidates",
                 start, end, len(articles))
        return articles

    def _collect(self, q: str, seen: set[str], articles: list[ScrapedArticle],
                 cutoff: datetime | None = None) -> None:
        parsed = parse_feed(RSS_SEARCH.format(query=quote(q)))
        if parsed is None:
            return
        for e in parsed.entries:
            published = _entry_datetime(e)
            if cutoff and published and published < cutoff:
                continue
            title = e.get("title", "")
            if not looks_like_funding_news(title):
                continue
            url = decode_google_news_url(e.get("link", ""))
            if "news.google.com" in url:
                continue  # undecodable → unfetchable and undedupable; skip
            if url in seen:
                continue
            seen.add(url)
            time.sleep(0.3)  # be gentle with the decode endpoint
            # publisher name arrives in the <source> tag
            publisher = e.get("source", {}).get("title", "")
            articles.append(ScrapedArticle(
                url=url, title=title, source=self.name,
                published_at=published,
                summary=publisher,
            ))
