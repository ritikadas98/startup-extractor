"""Per-domain polite delays for HTTP scraping."""
import random
import time
from urllib.parse import urlparse


class RateLimiter:
    def __init__(self, min_delay: float = 3.0, max_delay: float = 7.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        domain = urlparse(url).netloc
        elapsed = time.monotonic() - self._last.get(domain, 0.0)
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last[domain] = time.monotonic()
