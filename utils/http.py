"""Shared HTTP session. truststore makes Python use the OS trust store
(needed behind TLS-inspecting proxies; harmless elsewhere)."""
import random

import requests
import truststore

truststore.inject_into_ssl()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]


def get(url: str, timeout: int = 20) -> requests.Response:
    resp = requests.get(
        url, timeout=timeout, allow_redirects=True,
        headers={"User-Agent": random.choice(USER_AGENTS),
                 "Accept-Language": "en-IN,en;q=0.9"},
    )
    resp.raise_for_status()
    return resp
