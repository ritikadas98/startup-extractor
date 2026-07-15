"""job_target_score: ranks companies by fit with the job-search strategy.

Transparent, additive, tweakable — deliberately not a model. Weights encode the
sprint strategy: AI-first / B2B SaaS, freshly funded seed-Series B, Bengaluru
or remote, small team ("first PM hire"), with a live PM-class opening as the
strongest signal.

  tier_weight   AI/B2B SaaS 1.0 · fintech 0.6 · other 0.3
  stage_fit     pre-seed - series-b  +0.3
  freshness     funded <30d +0.3, linear decay to 0 at 90d
  location_fit  Bengaluru or remote  +0.2
  has_pm_role   live PM-class opening today  +0.5
  size_fit      headcount < 20  +0.2

Recomputed by `score-targets` (also run automatically after find-roles).
"""
import re
from datetime import date

from database import db
from utils.logger import get_logger

log = get_logger("scoring")

TIER_A = ["ai", "artificial intelligence", "machine learning", "saas",
          "b2b software", "enterprise software", "developer tool", "devtool", "llm"]
TIER_B = ["fintech", "financial", "payments", "lending", "insur"]

EARLY_STAGES = {"pre-seed", "seed", "pre-series-a", "series-a", "series-b"}


def _tier(industry: str | None, business_model: str | None) -> float:
    text = f"{industry or ''} {business_model or ''}".lower()
    if any(k in text for k in TIER_A):
        return 1.0
    if any(k in text for k in TIER_B):
        return 0.6
    return 0.3


def _freshness(announced) -> float:
    if not announced:
        return 0.0
    days = (date.today() - announced).days
    if days <= 30:
        return 0.3
    if days >= 90:
        return 0.0
    return 0.3 * (90 - days) / 60


def _size_fit(employee_estimate: str | None) -> float:
    if not employee_estimate:
        return 0.0
    m = re.search(r"\d+", str(employee_estimate))
    return 0.2 if (m and int(m.group()) < 20) else 0.0


def _location_fit(hq_city: str | None) -> float:
    t = (hq_city or "").lower()
    return 0.2 if ("bengaluru" in t or "bangalore" in t or "remote" in t) else 0.0


def recompute_scores(conn) -> int:
    """Recompute job_target_score for every company. Cheap — pure SQL + rules."""
    from jobs.classifier import PM_CLASSES
    rows = conn.execute(
        """
        SELECT co.id, co.industry, co.business_model, co.hq_city, co.employee_estimate,
               ov.latest_stage, ov.latest_round_date,
               EXISTS (SELECT 1 FROM job_roles jr WHERE jr.company_id = co.id
                       AND jr.role_class = ANY(%s) AND NOT jr.dismissed) AS has_pm_role
        FROM companies co JOIN companies_overview ov ON ov.id = co.id
        """,
        (list(PM_CLASSES),),
    ).fetchall()
    for r in rows:
        score = (
            _tier(r["industry"], r["business_model"])
            + (0.3 if (r["latest_stage"] or "") in EARLY_STAGES else 0.0)
            + _freshness(r["latest_round_date"])
            + _location_fit(r["hq_city"])
            + (0.5 if r["has_pm_role"] else 0.0)
            + _size_fit(r["employee_estimate"])
        )
        conn.execute("UPDATE companies SET job_target_score = %s WHERE id = %s",
                     (round(score, 3), r["id"]))
    conn.commit()
    log.info("job_target_score recomputed for %d companies", len(rows))
    return len(rows)
