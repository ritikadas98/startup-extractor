# startup_intel — project instructions

AI-powered knowledge system converting Indian startup funding news into 8-layer analyses
(extraction, summary, business, product, investment, PM lessons, interview prep, frameworks).
Goal: a compounding PM-learning knowledge base, NOT a news aggregator. Learning > job search.
Full plan: `docs/PLAN.md`. One-time account setup: `SETUP_CHECKLIST.md`.

## CRITICAL: shared device, separate accounts

This Mac belongs to Ayan Shukla, but this project is **Ritika's** — her GitHub, GCP, and
Supabase accounts (in her non-default Chrome profile) are used for everything.

- NEVER touch `git config --global` (that's Ayan's identity). Use per-repo config only.
- NEVER commit or push until per-repo git identity is set to Ritika and `gh` is authed
  as her account (Ayan's `ayan-shukla` login also exists in gh — check `gh auth status`).
- gcloud: use the named configuration `ritika`.
- After the first commit, verify: `git log --format='%an %ae'` shows Ritika, not Ayan.

## Stack

Python 3.13 (`.venv/`) + Typer CLI · Supabase Postgres + pgvector (direct psycopg via
`SUPABASE_DB_URL`) · Vertex AI Gemini (2.5-flash for layers 1/2/7, 2.5-pro for 3/4/5/6/8,
structured JSON output, cost tracked per call) · GitHub Actions cron 00:30 UTC = 06:00 IST.

```bash
source .venv/bin/activate
python -m cli.main init-db | scrape --days 1 | fetch-text --limit 50 | analyze --limit 5 | status | cost-summary
```

## Status (as of 2026-07-11)

DONE and tested:
- 5 scrapers (Entrackr, Inc42, YourStory, ET Tech, Google News) — live-tested, 155 candidates/3 days.
  Google News URLs decoded to publisher URLs via batchexecute endpoint (`scrapers/google_news_rss.py`).
- TLS on this Mac requires `truststore` (OS trust store) — already wired in `utils/http.py`;
  all HTTP must go through that module.
- Supabase live: project region ap-southeast-1, `.env` set, `init-db` applied against it.
  (Note: a brand-new free-tier DB can throw `QueryCanceled: statement timeout` on first
  writes — cold start; just retry, scrape is idempotent.)
- GCP live: project `startup-extractor`, gcloud config `ritika` (ritikadas98@gmail.com),
  ADC done, bucket `startup-extractor-batch` created. gcloud lives at
  `/opt/homebrew/share/google-cloud-sdk/bin` (not on PATH by default).
- **Full pipeline verified end-to-end 2026-07-11**: scrape → fetch-text → analyze ran a
  real article through all 8 layers. Cost: $0.202/article interactive (pro layers
  dominate) — recheck the $40–80 backfill estimate against real per-article cost before
  Phase G.

- GitHub live: private repo `ritikadas98/startup-extractor`, per-repo identity = Ritika
  (verified in git log). Ayan's global gitconfig rewrites GitHub HTTPS→SSH (`insteadOf`);
  this repo has a local counter-rule pinning `ritikadas98/` URLs to HTTPS — don't remove.
- Actions auth is **keyless** (Workload Identity Federation, pool `github`, provider
  `github-provider`, repo-restricted) — GCP forbids SA keys on this project. Secrets:
  GCP_PROJECT_ID, GCP_REGION, SUPABASE_DB_URL only; no GCP_SA_KEY.

Setup checklist: fully done except Netlify (Phase F, frontend not built yet).

NEXT, in order:
1. `analyze --limit 10` and **manually review analysis quality / iterate prompts BEFORE
   any bulk processing** — quality gate for the historical backfill (240 days, Vertex
   Batch Prediction).
2. Phase C: embeddings (`gemini-embedding-001`, 768-dim, `embeddings` table exists) +
   knowledge graph (`knowledge/` — rule detectors: same_investor, competitor via Layer-3
   alternatives[], same_business_model, same_stage_quarter; AI-assisted same_market).
3. Phase D: `scheduler/daily_runner.py` + wire remaining steps into `.github/workflows/daily.yml`.
4. Phase E: reports (daily briefing, weekly trends, monthly, job-target scoring 100-pt rubric in PLAN).
   Includes **roles finder**: user gives filters at run time (role keywords, location,
   stage, sector, funding recency) → query companies table (freshly funded = hiring
   signal) → fetch live openings per company: detect ATS from `careers_url` (Greenhouse
   `boards-api.greenhouse.io`, Lever `api.lever.co/v0/postings`, Ashby — all public JSON,
   no auth) with a flash-extraction fallback for plain careers pages; store in a
   `job_roles` table, rank via the 100-pt rubric. NO LinkedIn scraping (ToS). CLI:
   `find-roles --role "product" --location bangalore --funded-within 90`.
5. Phase F (parallel, after C): minimal 4-page Next.js frontend in `web/` on Netlify
   (read-only via Supabase anon key + RLS; pages: briefing, companies, company detail, search).
6. Phase G: historical backfill — LAST, only after step 1's quality gate.

## Conventions

- All DB access through `database/db.py`; schema changes only via `database/schema.sql` (idempotent DDL).
- New source = new file in `scrapers/` extending `BaseScraper`/`RSSFeedScraper` + entry in
  `config/sources.yaml`. Nothing else changes.
- Layer prompts live in `prompts/layerN.txt`; response schemas in `analysis/schemas.py`;
  model routing in `config/settings.py` `LAYER_MODEL_MAP`.
- Analysis is resume-safe: `UNIQUE(article_id, layer_number)` upsert; only missing layers re-run.
- Layer 1 gates layers 2–8 (non-funding articles stop after one flash call).
