"""Vertex AI (Gemini) client: model routing, structured output, cost tracking."""
import json
import time
from functools import lru_cache

from config.settings import (
    GCP_PROJECT_ID, GCP_REGION, LAYER_MODEL_MAP, LAYER_NAMES,
    MODEL_PRICING, PROMPTS_DIR,
)
from database.models import LayerResult
from utils.logger import get_logger

log = get_logger("vertex")


@lru_cache(maxsize=1)
def get_client():
    from google import genai
    from google.genai import types
    if not GCP_PROJECT_ID:
        raise RuntimeError("GCP_PROJECT_ID is not set — fill in .env")
    # timeout: a hung socket must fail (and be retried) rather than block forever
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_REGION,
                        http_options=types.HttpOptions(timeout=180_000))


@lru_cache(maxsize=16)
def _prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()


def _cost(model: str, tokens_in: int, tokens_out: int, cached: int) -> float:
    p = MODEL_PRICING[model]
    fresh_in = max(tokens_in - cached, 0)
    return (fresh_in * p["input"] + cached * p["cached"] + tokens_out * p["output"]) / 1e6


def call_layer(layer_num: int, article_text: str, metadata: dict,
               prior_layers: dict[int, dict] | None = None) -> LayerResult:
    """Run one analysis layer. prior_layers lets later layers see Layer 1/3 output."""
    from google.genai import types
    from analysis.schemas import LAYER_SCHEMAS

    model = LAYER_MODEL_MAP[layer_num]
    system = _prompt("system_base") + "\n\n" + _prompt(f"layer{layer_num}")

    parts = [f"ARTICLE METADATA:\n{json.dumps(metadata, default=str)}"]
    if prior_layers:
        for n, result in sorted(prior_layers.items()):
            parts.append(f"PRIOR ANALYSIS (layer {n} — {LAYER_NAMES[n]}):\n{json.dumps(result)}")
    parts.append(f"ARTICLE TEXT:\n{article_text}")

    start = time.monotonic()
    response = get_client().models.generate_content(
        model=model,
        contents="\n\n".join(parts),
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=LAYER_SCHEMAS[layer_num],
            temperature=0.4,
        ),
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)

    # models occasionally emit U+2016 (‖) where the article had ₹ — normalize
    result = json.loads(response.text.replace("‖", "₹"))
    usage = response.usage_metadata
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = ((getattr(usage, "candidates_token_count", 0) or 0)
                  + (getattr(usage, "thoughts_token_count", 0) or 0))
    cached = getattr(usage, "cached_content_token_count", 0) or 0

    return LayerResult(
        layer_number=layer_num,
        layer_name=LAYER_NAMES[layer_num],
        model_used=model,
        result=result,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        cache_read_tokens=cached,
        cost_usd=_cost(model, tokens_in, tokens_out, cached),
        processing_time_ms=elapsed_ms,
    )
