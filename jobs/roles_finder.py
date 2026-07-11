"""Roles finder (Phase E): live job openings at freshly-funded startups.

Resolution order per company (result cached in companies.careers_url):
  1. Known careers_url from Layer 1 extraction.
  2. Free ATS probe — Greenhouse/Lever/Ashby expose public JSON job boards at
     guessable slugs; a hit gives clean structured roles with zero AI cost.
  3. (--deep only) Gemini Flash with Google Search grounding finds the careers
     page URL; plain pages then go through Flash extraction (~a rupee each).

No LinkedIn, no scraping that violates ToS.
"""
import json
import re

from database import db
from utils import http
from utils.logger import get_logger

log = get_logger("roles")

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"

ROLES_SCHEMA = {
    "type": "object",
    "properties": {
        "is_careers_page": {"type": "boolean"},
        "roles": {"type": "array", "items": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "location": {"type": "string"},
                           "department": {"type": "string"}},
            "required": ["title"],
        }},
    },
    "required": ["is_careers_page", "roles"],
}


def _slug_candidates(company: dict) -> list[str]:
    slugs = [company["name_normalized"]]
    if company.get("website"):
        domain = re.sub(r"^https?://(www\.)?", "", company["website"]).split("/")[0]
        slugs.append(domain.split(".")[0])
    # dedupe, keep order
    return list(dict.fromkeys(s for s in slugs if s))


def _get_json(url: str):
    try:
        resp = http.get(url)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def probe_ats(company: dict) -> tuple[str, str, list[dict]] | None:
    """Try public ATS job boards. Returns (kind, slug, roles) on a hit."""
    for slug in _slug_candidates(company):
        j = _get_json(GREENHOUSE.format(slug=slug))
        if j and isinstance(j.get("jobs"), list):
            roles = [{"title": r.get("title", ""), "location": (r.get("location") or {}).get("name"),
                      "department": None, "url": r.get("absolute_url")} for r in j["jobs"]]
            return "greenhouse", slug, roles
        j = _get_json(LEVER.format(slug=slug))
        if isinstance(j, list) and j:
            roles = [{"title": r.get("text", ""),
                      "location": (r.get("categories") or {}).get("location"),
                      "department": (r.get("categories") or {}).get("team"),
                      "url": r.get("hostedUrl")} for r in j]
            return "lever", slug, roles
        j = _get_json(ASHBY.format(slug=slug))
        if j and isinstance(j.get("jobs"), list) and j["jobs"]:
            roles = [{"title": r.get("title", ""), "location": r.get("location"),
                      "department": r.get("department"), "url": r.get("jobUrl")} for r in j["jobs"]]
            return "ashby", slug, roles
    return None


def find_careers_url_via_search(company: dict) -> str | None:
    """Gemini Flash + Google Search grounding → careers page URL (--deep only)."""
    from google.genai import types
    from analysis.vertex_client import get_client
    hints = " ".join(str(company.get(k) or "") for k in ("hq_city", "industry"))
    prompt = (f"Find the official careers/jobs page URL for \"{company['name']}\", "
              f"an Indian startup ({hints}). Reply with ONLY the URL. "
              f"If you cannot find an official careers page, reply exactly: NONE")
    try:
        r = get_client().models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.0),
        )
        m = re.search(r"https?://\S+", r.text or "")
        return m.group(0).rstrip(".,)") if m else None
    except Exception as e:
        log.warning("careers search failed for %s: %s", company["name"], e)
        return None


def extract_roles_from_page(url: str) -> list[dict] | None:
    """Plain careers page → Flash structured extraction.

    Returns None when the URL doesn't load or isn't a careers page (so callers
    don't cache a bad URL); an empty list means a valid page with no openings.
    """
    from google.genai import types
    from analysis.vertex_client import get_client
    try:
        page = http.get(url)
        if page.status_code != 200:
            return None
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", page.text,
                      flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)[:30000]
        r = get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=f"CAREERS PAGE TEXT:\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=("Extract open job roles from this careers page text. "
                                    "Only roles explicitly listed as open positions; do not invent."),
                response_mime_type="application/json",
                response_schema=ROLES_SCHEMA, temperature=0.0),
        )
        out = json.loads(r.text)
        if not out.get("is_careers_page"):
            return None
        return [{"title": x.get("title", ""), "location": x.get("location"),
                 "department": x.get("department"), "url": url} for x in out["roles"]]
    except Exception as e:
        log.warning("page extraction failed for %s: %s", url, e)
        return None


def roles_for_company(conn, company: dict, deep: bool = False) -> tuple[list[dict], str]:
    """Fetch live roles for one company. Returns (roles, source_kind)."""
    hit = probe_ats(company)
    if hit:
        kind, slug, roles = hit
        return roles, kind

    url = company.get("careers_url")
    if url and (not url.startswith("http") or url.strip().lower() in db.NULLISH):
        url = None
    discovered = False
    if not url and deep:
        url = find_careers_url_via_search(company)
        discovered = True
    if url:
        roles = extract_roles_from_page(url)
        if roles is None:  # dead link or not a careers page — don't cache it
            return [], "none"
        if discovered:  # cache only URLs that actually validated
            conn.execute("UPDATE companies SET careers_url = %s WHERE id = %s",
                         (url, company["id"]))
            conn.commit()
        return roles, "page"
    return [], "none"


def store_roles(conn, company_id: int, roles: list[dict], kind: str) -> int:
    n = 0
    for r in roles:
        if not r.get("title"):
            continue
        conn.execute(
            """
            INSERT INTO job_roles (company_id, title, location, department, url, source_kind)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id, title, location) DO UPDATE SET last_seen = now()
            """,
            (company_id, r["title"][:300], r.get("location"), r.get("department"),
             r.get("url"), kind),
        )
        n += 1
    return n
