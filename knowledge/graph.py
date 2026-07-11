"""Knowledge-graph edge detection between companies.

Four rule detectors run on structured data (free, deterministic); same_market
uses embedding cosine similarity (detected_by='ai', no extra model calls).
Edges are undirected, upserted, and safe to re-run — build_graph() is
incremental by nature since it always recomputes from current data.
"""
from database import db
from utils.logger import get_logger

log = get_logger("graph")

SAME_MARKET_THRESHOLD = 0.80


def detect_same_investor(conn) -> int:
    rows = conn.execute(
        """
        SELECT DISTINCT r1.company_id AS a, r2.company_id AS b, i.name
        FROM round_investors ri1
        JOIN round_investors ri2 ON ri1.investor_id = ri2.investor_id
        JOIN funding_rounds r1 ON r1.id = ri1.round_id
        JOIN funding_rounds r2 ON r2.id = ri2.round_id
        JOIN investors i ON i.id = ri1.investor_id
        WHERE r1.company_id < r2.company_id
        """
    ).fetchall()
    for r in rows:
        db.upsert_edge(conn, r["a"], r["b"], "same_investor", 1.0,
                       f"both backed by {r['name']}", "rule")
    return len(rows)


def detect_same_stage_quarter(conn) -> int:
    rows = conn.execute(
        """
        SELECT DISTINCT r1.company_id AS a, r2.company_id AS b, r1.stage,
               to_char(r1.announced_date, 'YYYY-"Q"Q') AS quarter
        FROM funding_rounds r1
        JOIN funding_rounds r2
          ON r1.stage = r2.stage
         AND r1.stage NOT IN ('unknown', '')
         AND date_trunc('quarter', r1.announced_date) = date_trunc('quarter', r2.announced_date)
         AND r1.company_id < r2.company_id
        WHERE r1.announced_date IS NOT NULL AND r2.announced_date IS NOT NULL
        """
    ).fetchall()
    for r in rows:
        db.upsert_edge(conn, r["a"], r["b"], "same_stage_quarter", 1.0,
                       f"both raised {r['stage']} in {r['quarter']}", "rule")
    return len(rows)


def detect_same_business_model(conn) -> int:
    rows = conn.execute(
        """
        SELECT c1.id AS a, c2.id AS b, c1.business_model
        FROM companies c1
        JOIN companies c2
          ON lower(trim(c1.business_model)) = lower(trim(c2.business_model))
         AND c1.id < c2.id
        WHERE c1.business_model IS NOT NULL
          AND lower(trim(c1.business_model)) NOT IN ('', 'null', 'none', 'n/a', 'unknown')
        """
    ).fetchall()
    for r in rows:
        db.upsert_edge(conn, r["a"], r["b"], "same_business_model", 1.0,
                       f"business model: {r['business_model']}", "rule")
    return len(rows)


def detect_competitors(conn) -> int:
    """Layer 3 lists alternatives[] — when one names another tracked company."""
    arts = conn.execute(
        """
        SELECT r.article_id, r.company_id, r.result_json
        FROM analysis_results r
        WHERE r.layer_number = 3 AND r.company_id IS NOT NULL
        """
    ).fetchall()
    companies = conn.execute(
        "SELECT id, name, name_normalized FROM companies"
    ).fetchall()
    by_norm = {c["name_normalized"]: c for c in companies}
    n = 0
    for art in arts:
        for alt in (art["result_json"].get("alternatives") or []):
            norm = db.normalize_name(alt)
            hit = by_norm.get(norm)
            if hit and hit["id"] != art["company_id"]:
                db.upsert_edge(conn, art["company_id"], hit["id"], "competitor", 0.9,
                               f"Layer 3 names '{alt}' as an alternative", "rule")
                n += 1
    return n


def detect_same_market(conn, threshold: float = SAME_MARKET_THRESHOLD) -> int:
    """Embedding cosine similarity between analysis vectors of different companies."""
    rows = conn.execute(
        """
        SELECT DISTINCT fr1.company_id AS a, fr2.company_id AS b,
               1 - (e1.embedding <=> e2.embedding) AS sim
        FROM embeddings e1
        JOIN embeddings e2 ON e1.article_id < e2.article_id
             AND e1.content_kind = 'analysis' AND e2.content_kind = 'analysis'
        JOIN funding_rounds fr1 ON fr1.article_id = e1.article_id
        JOIN funding_rounds fr2 ON fr2.article_id = e2.article_id
        WHERE fr1.company_id <> fr2.company_id
          AND 1 - (e1.embedding <=> e2.embedding) >= %s
        """,
        (threshold,),
    ).fetchall()
    for r in rows:
        db.upsert_edge(conn, r["a"], r["b"], "same_market", float(r["sim"]),
                       f"analysis similarity {r['sim']:.2f}", "ai")
    return len(rows)


def build_graph(conn) -> dict[str, int]:
    counts = {
        "same_investor": detect_same_investor(conn),
        "same_stage_quarter": detect_same_stage_quarter(conn),
        "same_business_model": detect_same_business_model(conn),
        "competitor": detect_competitors(conn),
        "same_market": detect_same_market(conn),
    }
    conn.commit()
    log.info("graph edges upserted: %s", counts)
    return counts
