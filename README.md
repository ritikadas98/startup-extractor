# startup_intel

AI-powered knowledge system that converts Indian startup funding news into structured
business intelligence, PM case studies, and interview-ready insights. Not a news
aggregator — a compounding personal knowledge base.

## Architecture

- **Pipeline**: Python 3.13, Typer CLI
- **Storage**: Supabase Postgres (+ pgvector for semantic search)
- **Analysis**: Vertex AI Gemini — 8 layers per article
  (`2.5-flash` for extraction/summary/interview, `2.5-pro` for business/product/investment/PM-learning/frameworks)
- **Automation**: GitHub Actions cron, 06:00 IST daily
- **Frontend**: minimal Next.js app in `web/` (read-only, Netlify)

## Commands

```bash
source .venv/bin/activate
python -m cli.main init-db                 # apply schema.sql to Supabase
python -m cli.main scrape --days 1         # discover articles (all enabled sources)
python -m cli.main fetch-text --limit 50   # download article text
python -m cli.main analyze --limit 5       # run 8-layer Gemini analysis
python -m cli.main status
python -m cli.main cost-summary
```

## Setup

See `SETUP_CHECKLIST.md` for the one-time account setup (Supabase, GCP/Vertex, GitHub).
Copy `.env.example` to `.env` and fill in. Add a source by creating a scraper in
`scrapers/` and an entry in `config/sources.yaml`.
