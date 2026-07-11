"""startup_intel CLI. Run as: python -m cli.main <command>"""
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Startup Intelligence & PM Knowledge System", no_args_is_help=True)
console = Console()


@app.command("init-db")
def init_db():
    """Apply database/schema.sql to Supabase (idempotent)."""
    from database import db
    db.init_db()
    console.print("[green]Schema applied.[/green]")


@app.command()
def scrape(source: str = typer.Option(None, help="One source name, or all enabled if omitted"),
           days: int = typer.Option(1, help="Look-back window in days")):
    """Discover new articles from RSS sources and store deduplicated URLs."""
    from scrapers.registry import load_scrapers
    from dedup.deduplicator import url_hash
    from database import db

    scrapers = load_scrapers(only=source)
    if not scrapers:
        console.print(f"[red]No scraper named '{source}' in config/sources.yaml[/red]")
        raise typer.Exit(1)

    new, dup = 0, 0
    with db.get_conn() as conn:
        for name, s in scrapers.items():
            for a in s.discover(days_back=days):
                if not a.url:
                    continue
                if db.insert_article(conn, a, url_hash(a.url)) is None:
                    dup += 1
                else:
                    new += 1
        conn.commit()
    console.print(f"[green]{new} new articles stored[/green], {dup} duplicates skipped")


@app.command("fetch-text")
def fetch_text(limit: int = typer.Option(50, help="Max articles to fetch this run")):
    """Download full article text for pending articles."""
    from scrapers.fetch_text import fetch_article_text
    from database import db

    ok, failed = 0, 0
    with db.get_conn() as conn:
        pending = db.get_articles_by_status(conn, "pending", limit)
        for art in pending:
            text = fetch_article_text(art["url"])
            if text:
                db.set_article_text(conn, art["id"], text)
                ok += 1
            else:
                db.set_article_status(conn, art["id"], "pending",
                                      "text extraction failed", bump_retry=True)
                failed += 1
            conn.commit()
    console.print(f"[green]{ok} articles fetched[/green], {failed} failed "
                  f"(of {len(pending)} pending)")


@app.command()
def analyze(article_id: int = typer.Option(None, help="Analyze one specific article"),
            limit: int = typer.Option(5, help="Max articles to analyze this run")):
    """Run the 8-layer Gemini analysis on fetched articles."""
    from analysis.pipeline import process_article
    from database import db

    with db.get_conn() as conn:
        db.requeue_stuck_articles(conn)
        conn.commit()
        if article_id:
            art = db.get_article(conn, article_id)
            if not art:
                console.print(f"[red]No article with id {article_id}[/red]")
                raise typer.Exit(1)
            articles = [art]
        else:
            articles = db.get_articles_by_status(conn, "fetched", limit)

        total = 0.0
        for art in articles:
            try:
                r = process_article(conn, art)
                total += r["cost_usd"]
            except Exception:
                continue  # already logged + marked failed; keep going
        console.print(f"[green]{len(articles)} articles processed[/green], "
                      f"total cost ${total:.4f}")


@app.command()
def status():
    """Article counts by status plus table totals."""
    from database import db
    with db.get_conn() as conn:
        s = db.status_summary(conn)
    t = Table(title="startup_intel status")
    t.add_column("metric"); t.add_column("count", justify="right")
    for k, v in s["by_status"].items():
        t.add_row(f"articles: {k}", str(v))
    for k in ("articles", "companies", "rounds", "analyses", "edges"):
        t.add_row(k, str(s[k]))
    console.print(t)


@app.command("cost-summary")
def cost_summary_cmd():
    """Vertex AI spend by model."""
    from database import db
    with db.get_conn() as conn:
        rows = db.cost_summary(conn)
    t = Table(title="Vertex AI cost")
    for col in ("model", "calls", "tokens in", "tokens out", "cost USD"):
        t.add_column(col, justify="right")
    for r in rows:
        t.add_row(r["model_used"], str(r["calls"]), str(r["tokens_in"]),
                  str(r["tokens_out"]), str(r["cost_usd"]))
    console.print(t)


if __name__ == "__main__":
    app()
