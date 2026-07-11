"""All database reads/writes go through this module (psycopg 3, direct Postgres)."""
import json
import re

import psycopg
from psycopg.rows import dict_row

from config.settings import SUPABASE_DB_URL, SCHEMA_SQL
from database.models import ScrapedArticle, LayerResult


def get_conn() -> psycopg.Connection:
    if not SUPABASE_DB_URL:
        raise RuntimeError("SUPABASE_DB_URL is not set — copy .env.example to .env and fill it in")
    return psycopg.connect(SUPABASE_DB_URL, row_factory=dict_row)


def init_db() -> None:
    sql = SCHEMA_SQL.read_text()
    with get_conn() as conn:
        conn.execute(sql)


def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\b(pvt|private|ltd|limited|inc|technologies|technology|labs|india)\b\.?", "", name)
    return re.sub(r"[^a-z0-9]+", "", name)


# --- articles ---

def insert_article(conn: psycopg.Connection, a: ScrapedArticle, url_hash: str) -> int | None:
    """Insert a scraped article; returns new id, or None if it was a duplicate."""
    row = conn.execute(
        """
        INSERT INTO articles (url, url_hash, title, source, published_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (a.url, url_hash, a.title, a.source, a.published_at),
    ).fetchone()
    return row["id"] if row else None


def is_url_seen(conn: psycopg.Connection, url_hash: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM articles WHERE url_hash = %s", (url_hash,)
    ).fetchone() is not None


def get_articles_by_status(conn: psycopg.Connection, status: str, limit: int = 100) -> list[dict]:
    return conn.execute(
        """
        SELECT id, url, title, source, published_at, article_text, retry_count
        FROM articles WHERE processing_status = %s AND retry_count < 3
        ORDER BY published_at DESC NULLS LAST LIMIT %s
        """,
        (status, limit),
    ).fetchall()


def get_article(conn: psycopg.Connection, article_id: int) -> dict | None:
    return conn.execute("SELECT * FROM articles WHERE id = %s", (article_id,)).fetchone()


def set_article_text(conn: psycopg.Connection, article_id: int, text: str) -> None:
    conn.execute(
        """
        UPDATE articles SET article_text = %s, word_count = %s,
               processing_status = 'fetched', updated_at = now()
        WHERE id = %s
        """,
        (text, len(text.split()), article_id),
    )


def set_article_status(conn: psycopg.Connection, article_id: int, status: str,
                       error: str | None = None, bump_retry: bool = False) -> None:
    conn.execute(
        """
        UPDATE articles SET processing_status = %s, processing_error = %s,
               retry_count = retry_count + %s, updated_at = now()
        WHERE id = %s
        """,
        (status, error, 1 if bump_retry else 0, article_id),
    )


def requeue_stuck_articles(conn: psycopg.Connection) -> int:
    """Articles left in 'processing' by a crashed run go back to 'fetched'."""
    cur = conn.execute(
        "UPDATE articles SET processing_status = 'fetched' "
        "WHERE processing_status = 'processing' AND retry_count < 3"
    )
    return cur.rowcount


# --- analysis ---

def get_completed_layers(conn: psycopg.Connection, article_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT layer_number FROM analysis_results WHERE article_id = %s", (article_id,)
    ).fetchall()
    return {r["layer_number"] for r in rows}


def store_layer_result(conn: psycopg.Connection, article_id: int,
                       company_id: int | None, r: LayerResult) -> None:
    conn.execute(
        """
        INSERT INTO analysis_results
            (article_id, company_id, layer_number, layer_name, model_used, result_json,
             tokens_input, tokens_output, cache_read_tokens, cost_usd, processing_time_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (article_id, layer_number) DO UPDATE SET
            result_json = EXCLUDED.result_json, model_used = EXCLUDED.model_used,
            company_id = EXCLUDED.company_id, cost_usd = EXCLUDED.cost_usd,
            tokens_input = EXCLUDED.tokens_input, tokens_output = EXCLUDED.tokens_output
        """,
        (article_id, company_id, r.layer_number, r.layer_name, r.model_used,
         json.dumps(r.result), r.tokens_input, r.tokens_output, r.cache_read_tokens,
         r.cost_usd, r.processing_time_ms),
    )


def get_layer_result(conn: psycopg.Connection, article_id: int, layer_number: int) -> dict | None:
    row = conn.execute(
        "SELECT result_json FROM analysis_results WHERE article_id = %s AND layer_number = %s",
        (article_id, layer_number),
    ).fetchone()
    return row["result_json"] if row else None


# --- pipeline settings (control switches) ---

def get_setting(conn: psycopg.Connection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM pipeline_settings WHERE key = %s", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: psycopg.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_settings (key, value, updated_at) VALUES (%s, %s, now())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
        """,
        (key, value),
    )


def all_settings(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        "SELECT key, value, updated_at FROM pipeline_settings ORDER BY key"
    ).fetchall()


def month_spend_usd(conn: psycopg.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(sum(cost_usd), 0) AS spend FROM analysis_results
        WHERE created_at >= date_trunc('month', now())
        """
    ).fetchone()
    return float(row["spend"])


def get_recent_tldrs(conn: psycopg.Connection, days: int = 1, limit: int = 20,
                     source: str | None = None) -> list[dict]:
    """Layer-2 summaries of recently analyzed articles, newest first."""
    return conn.execute(
        """
        SELECT a.id, a.title, a.source, a.url, a.published_at, r.result_json
        FROM analysis_results r JOIN articles a ON a.id = r.article_id
        WHERE r.layer_number = 2
          AND r.created_at >= now() - make_interval(days => %s)
          AND (%s::text IS NULL OR a.source = %s)
        ORDER BY a.published_at DESC NULLS LAST
        LIMIT %s
        """,
        (days, source, source, limit),
    ).fetchall()


# --- companies / rounds / investors / founders ---

def upsert_company(conn: psycopg.Connection, name: str, **fields) -> int:
    norm = normalize_name(name)
    if not norm:
        raise ValueError(f"unusable company name: {name!r}")
    cols = {k: v for k, v in fields.items() if v}
    row = conn.execute(
        """
        INSERT INTO companies (name, name_normalized, website, careers_url, linkedin_url,
                               hq_city, industry, business_model, employee_estimate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (name_normalized) DO UPDATE SET
            website = COALESCE(companies.website, EXCLUDED.website),
            careers_url = COALESCE(companies.careers_url, EXCLUDED.careers_url),
            linkedin_url = COALESCE(companies.linkedin_url, EXCLUDED.linkedin_url),
            hq_city = COALESCE(companies.hq_city, EXCLUDED.hq_city),
            industry = COALESCE(companies.industry, EXCLUDED.industry),
            business_model = COALESCE(companies.business_model, EXCLUDED.business_model),
            employee_estimate = COALESCE(companies.employee_estimate, EXCLUDED.employee_estimate)
        RETURNING id
        """,
        (name, norm, cols.get("website"), cols.get("careers_url"), cols.get("linkedin_url"),
         cols.get("hq_city"), cols.get("industry"), cols.get("business_model"),
         cols.get("employee_estimate")),
    ).fetchone()
    return row["id"]


def upsert_investor(conn: psycopg.Connection, name: str, investor_type: str | None = None) -> int:
    norm = normalize_name(name)
    row = conn.execute(
        """
        INSERT INTO investors (name, name_normalized, investor_type) VALUES (%s, %s, %s)
        ON CONFLICT (name_normalized) DO UPDATE SET
            investor_type = COALESCE(investors.investor_type, EXCLUDED.investor_type)
        RETURNING id
        """,
        (name, norm, investor_type),
    ).fetchone()
    return row["id"]


def upsert_funding_round(conn: psycopg.Connection, company_id: int, article_id: int,
                         **f) -> int:
    row = conn.execute(
        """
        INSERT INTO funding_rounds
            (company_id, article_id, amount_usd, amount_raw, currency, stage,
             announced_date, total_raised_usd)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (company_id, article_id) DO UPDATE SET
            amount_usd = EXCLUDED.amount_usd, stage = EXCLUDED.stage
        RETURNING id
        """,
        (company_id, article_id, f.get("amount_usd"), f.get("amount_raw"),
         f.get("currency"), f.get("stage"), f.get("announced_date"),
         f.get("total_raised_usd")),
    ).fetchone()
    return row["id"]


def link_round_investor(conn: psycopg.Connection, round_id: int, investor_id: int,
                        is_lead: bool = False) -> None:
    conn.execute(
        "INSERT INTO round_investors (round_id, investor_id, is_lead) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (round_id, investor_id, is_lead),
    )


def upsert_founder(conn: psycopg.Connection, company_id: int, name: str,
                   role: str | None = None, linkedin_url: str | None = None) -> None:
    row = conn.execute(
        """
        SELECT f.id FROM founders f
        JOIN company_founders cf ON cf.founder_id = f.id
        WHERE cf.company_id = %s AND lower(f.name) = lower(%s)
        """,
        (company_id, name),
    ).fetchone()
    if row:
        return
    fid = conn.execute(
        "INSERT INTO founders (name, role, linkedin_url) VALUES (%s, %s, %s) RETURNING id",
        (name, role, linkedin_url),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO company_founders (company_id, founder_id) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING",
        (company_id, fid),
    )


# --- summaries ---

def status_summary(conn: psycopg.Connection) -> dict:
    counts = {r["processing_status"]: r["n"] for r in conn.execute(
        "SELECT processing_status, count(*) n FROM articles GROUP BY processing_status"
    ).fetchall()}
    totals = conn.execute(
        "SELECT (SELECT count(*) FROM articles) articles,"
        "       (SELECT count(*) FROM companies) companies,"
        "       (SELECT count(*) FROM funding_rounds) rounds,"
        "       (SELECT count(*) FROM analysis_results) analyses,"
        "       (SELECT count(*) FROM company_relationships) edges"
    ).fetchone()
    return {"by_status": counts, **totals}


def cost_summary(conn: psycopg.Connection) -> list[dict]:
    return conn.execute(
        """
        SELECT model_used, count(*) calls, sum(tokens_input) tokens_in,
               sum(tokens_output) tokens_out, round(sum(cost_usd)::numeric, 4) cost_usd
        FROM analysis_results GROUP BY model_used ORDER BY cost_usd DESC
        """
    ).fetchall()
