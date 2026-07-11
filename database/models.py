"""Dataclasses mirroring database rows (the subset the pipeline passes around)."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScrapedArticle:
    url: str
    title: str
    source: str
    published_at: datetime | None = None
    summary: str = ""          # RSS-provided snippet, not the full text
    article_text: str = ""     # filled by fetch-text


@dataclass
class Article:
    id: int
    url: str
    title: str | None
    source: str
    published_at: datetime | None
    article_text: str | None
    processing_status: str
    retry_count: int = 0


@dataclass
class LayerResult:
    layer_number: int
    layer_name: str
    model_used: str
    result: dict
    tokens_input: int = 0
    tokens_output: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    processing_time_ms: int = 0


@dataclass
class Company:
    id: int
    name: str
    name_normalized: str
    website: str | None = None
    careers_url: str | None = None
    linkedin_url: str | None = None
    hq_city: str | None = None
    industry: str | None = None
    business_model: str | None = None
    employee_estimate: str | None = None
    north_star_metric: str | None = None
    job_target_score: float = 0.0
