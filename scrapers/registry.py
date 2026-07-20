"""Load enabled scrapers from config/sources.yaml — the pluggable-source mechanism."""
import importlib

import yaml

from config.settings import SOURCES_YAML
from scrapers.base_scraper import BaseScraper


def load_scrapers(only: str | None = None) -> dict[str, BaseScraper]:
    cfg = yaml.safe_load(SOURCES_YAML.read_text())["sources"]
    scrapers: dict[str, BaseScraper] = {}
    for name, spec in cfg.items():
        if only and name != only:
            continue
        if not only and not spec.get("enabled", False):
            continue
        cls = getattr(importlib.import_module(spec["module"]), spec["class"])
        kwargs = {}
        if "feed_url" in spec:
            kwargs["feed_url"] = spec["feed_url"]
        if "queries" in spec:
            kwargs["queries"] = spec["queries"]
        scrapers[name] = cls(**kwargs)
    return scrapers


def reference_sources() -> set[str]:
    """Sources whose articles are kept for reading/search only — never AI-analyzed."""
    cfg = yaml.safe_load(SOURCES_YAML.read_text())["sources"]
    return {name for name, spec in cfg.items() if spec.get("reference")}
