"""Fetch full article text for discovered URLs. trafilatura does the heavy
lifting (boilerplate removal); requests+BS4 paragraph fallback for stubborn pages."""
import requests
import trafilatura
from bs4 import BeautifulSoup

from config.settings import MIN_ARTICLE_WORDS
from utils import http
from utils.rate_limiter import RateLimiter
from utils.text_cleaner import clean_text
from utils.logger import get_logger

log = get_logger("fetch_text")

limiter = RateLimiter()


def fetch_article_text(url: str) -> str | None:
    """Returns cleaned article text, or None if extraction failed/too short."""
    limiter.wait(url)
    try:
        resp = http.get(url)
    except requests.RequestException as e:
        log.warning("fetch failed %s: %s", url, e)
        return None

    text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
    if not text or len(text.split()) < MIN_ARTICLE_WORDS:
        text = _paragraph_fallback(resp.text)
    if not text or len(text.split()) < MIN_ARTICLE_WORDS:
        return None
    return clean_text(text)


def _paragraph_fallback(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return " ".join(p for p in paragraphs if len(p.split()) > 8)
