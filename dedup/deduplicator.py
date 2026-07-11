"""URL normalization + hashing. Two articles with the same normalized URL are duplicates."""
import hashlib
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "source", "cmpid", "igshid", "mc_cid", "mc_eid",
}


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING_PARAMS
    ))
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    # scheme pinned to https so http/https variants of one article dedupe
    return urlunparse(("https", host, path, "", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()
