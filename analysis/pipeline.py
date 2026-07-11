"""Orchestrates the 8 analysis layers per article, with layer-level resume."""
from datetime import date

from analysis.vertex_client import call_layer
from database import db
from utils.logger import get_logger

log = get_logger("pipeline")

MIN_CONFIDENCE = 0.3
# later layers see earlier results for grounding
PRIOR_CONTEXT = {2: [1], 3: [1], 4: [1, 3], 5: [1, 3], 6: [1, 3], 7: [1, 3], 8: [1, 3]}


def process_article(conn, article: dict) -> dict:
    """Run all missing layers for one article. Returns {layers_run, cost_usd, skipped}."""
    article_id = article["id"]
    completed = db.get_completed_layers(conn, article_id)
    if len(completed) == 8:
        return {"layers_run": 0, "cost_usd": 0.0, "skipped": "already complete"}

    metadata = {"title": article.get("title"), "source": article.get("source"),
                "published_at": article.get("published_at"), "url": article.get("url")}
    text = article.get("article_text") or ""
    if not text:
        db.set_article_status(conn, article_id, "failed", "no article text", bump_retry=True)
        conn.commit()
        return {"layers_run": 0, "cost_usd": 0.0, "skipped": "no text"}

    db.set_article_status(conn, article_id, "processing")
    conn.commit()

    total_cost, layers_run = 0.0, 0
    results: dict[int, dict] = {}

    try:
        # Layer 1 gates everything: non-funding articles stop here
        if 1 in completed:
            results[1] = db.get_layer_result(conn, article_id, 1)
        else:
            r1 = call_layer(1, text, metadata)
            results[1] = r1.result
            total_cost += r1.cost_usd
            layers_run += 1
            company_id = _store_extraction(conn, article_id, r1.result)
            db.store_layer_result(conn, article_id, company_id, r1)
            conn.commit()

        l1 = results[1]
        if not l1.get("is_funding_article", True) or l1.get("confidence_score", 1.0) < MIN_CONFIDENCE:
            db.set_article_status(conn, article_id, "complete",
                                  "skipped: not a funding article / low confidence")
            conn.commit()
            log.info("article %s: layer 1 gated out (%s)", article_id, l1.get("company_name"))
            return {"layers_run": layers_run, "cost_usd": total_cost, "skipped": "gated by layer 1"}

        company_id = _company_id_for(conn, l1.get("company_name", ""))

        for n in range(2, 9):
            if n in completed:
                results[n] = db.get_layer_result(conn, article_id, n)
                continue
            prior = {k: results[k] for k in PRIOR_CONTEXT[n] if k in results}
            r = call_layer(n, text, metadata, prior_layers=prior)
            results[n] = r.result
            db.store_layer_result(conn, article_id, company_id, r)
            conn.commit()
            total_cost += r.cost_usd
            layers_run += 1

        db.set_article_status(conn, article_id, "complete")
        conn.commit()
        log.info("article %s complete: %d layers, $%.4f", article_id, layers_run, total_cost)
        return {"layers_run": layers_run, "cost_usd": total_cost, "skipped": None}

    except Exception as e:
        conn.rollback()
        db.set_article_status(conn, article_id, "failed", str(e)[:500], bump_retry=True)
        conn.commit()
        log.error("article %s failed: %s", article_id, e)
        raise


def _company_id_for(conn, name: str) -> int | None:
    if not name:
        return None
    try:
        return db.upsert_company(conn, name)
    except ValueError:
        return None


def _store_extraction(conn, article_id: int, l1: dict) -> int | None:
    """Persist Layer 1 facts into companies/funding_rounds/investors/founders."""
    name = l1.get("company_name") or ""
    if not l1.get("is_funding_article", True) or not name:
        return None
    try:
        company_id = db.upsert_company(
            conn, name,
            website=l1.get("website"), careers_url=l1.get("careers_url"),
            linkedin_url=l1.get("linkedin_url"), hq_city=l1.get("hq_city"),
            industry=l1.get("industry"), business_model=l1.get("business_model"),
            employee_estimate=l1.get("employee_estimate"),
        )
    except ValueError:
        return None

    round_id = db.upsert_funding_round(
        conn, company_id, article_id,
        amount_usd=l1.get("amount_usd"), amount_raw=l1.get("amount_raw"),
        currency=l1.get("currency"), stage=l1.get("stage"),
        announced_date=_parse_date(l1.get("funding_date")),
        total_raised_usd=l1.get("total_funding_to_date_usd"),
    )
    for inv in l1.get("investors") or []:
        if inv.get("name"):
            inv_id = db.upsert_investor(conn, inv["name"], inv.get("type"))
            db.link_round_investor(conn, round_id, inv_id, bool(inv.get("is_lead")))
    for f in l1.get("founders") or []:
        if f.get("name"):
            db.upsert_founder(conn, company_id, f["name"], f.get("role"))
    return company_id


def _parse_date(raw) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None
