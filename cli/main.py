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


def _gate(conn, *keys: str) -> bool:
    """True if any of the given switches is off (prints why). Exit 0 keeps cron green."""
    from database import db
    for key in keys:
        if db.get_setting(conn, key, "true") != "true":
            console.print(f"[yellow]Skipped: '{key}' is off — run `resume` to re-enable.[/yellow]")
            return True
    return False


@app.command()
def scrape(source: str = typer.Option(None, help="One source name, or all enabled if omitted"),
           days: int = typer.Option(1, help="Look-back window in days")):
    """Discover new articles from RSS sources and store deduplicated URLs."""
    from scrapers.registry import load_scrapers
    from dedup.deduplicator import url_hash
    from database import db

    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled"):
            return
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


@app.command("backfill-discover")
def backfill_discover(
        start: str = typer.Option(..., help="Window start, YYYY-MM-DD"),
        end: str = typer.Option(..., help="Window end (exclusive), YYYY-MM-DD"),
        window: int = typer.Option(7, help="Days per Google News query window")):
    """Phase G: discover historical articles via date-windowed Google News queries.

    Idempotent — URLs already seen are skipped, so it's safe to re-run or resume.
    """
    from datetime import date, timedelta
    from scrapers.registry import load_scrapers
    from dedup.deduplicator import url_hash
    from database import db

    gn = load_scrapers(only="google_news")["google_news"]
    lo, hi = date.fromisoformat(start), date.fromisoformat(end)
    total_new = total_dup = 0
    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled"):
            return
        cur = lo
        while cur < hi:
            nxt = min(cur + timedelta(days=window), hi)
            new = dup = 0
            for a in gn.discover_window(cur, nxt):
                if not a.url:
                    continue
                if db.insert_article(conn, a, url_hash(a.url)) is None:
                    dup += 1
                else:
                    new += 1
            conn.commit()
            console.print(f"{cur} → {nxt}: [green]{new} new[/green], {dup} dup")
            total_new += new; total_dup += dup
            cur = nxt
    console.print(f"[bold green]{total_new} new articles stored[/bold green], "
                  f"{total_dup} duplicates skipped")


@app.command("fetch-text")
def fetch_text(limit: int = typer.Option(50, help="Max articles to fetch this run")):
    """Download full article text for pending articles."""
    from scrapers.fetch_text import fetch_article_text
    from database import db

    ok, failed = 0, 0
    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled"):
            return
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
        if _gate(conn, "pipeline_enabled", "analysis_enabled"):
            return
        budget = float(db.get_setting(conn, "monthly_budget_usd", "0") or 0)
        spent = db.month_spend_usd(conn)
        if budget and spent >= budget:
            console.print(f"[yellow]Skipped: monthly budget reached "
                          f"(${spent:.2f} of ${budget:.2f}) — raise it with "
                          f"`set-budget` or wait for next month.[/yellow]")
            return
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
def embed(limit: int = typer.Option(100, help="Max articles to embed this run")):
    """Create semantic embeddings for fully-analyzed articles (Phase C)."""
    from search.embeddings import embed_pending
    from database import db
    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled"):
            return
        n = embed_pending(conn, limit)
    console.print(f"[green]{n} articles embedded[/green]")


@app.command("build-graph")
def build_graph_cmd():
    """Detect company relationships → knowledge-graph edges (Phase C)."""
    from knowledge.graph import build_graph
    from database import db
    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled"):
            return
        counts = build_graph(conn)
    for k, v in counts.items():
        console.print(f"  {k}: {v}")
    console.print("[green]Graph updated.[/green]")


@app.command()
def pause(analysis: bool = typer.Option(False, "--analysis",
          help="Pause only the AI analysis (scraping keeps collecting, free)")):
    """Stop the pipeline — locally AND the daily cloud run (they read the same switch)."""
    from database import db
    key = "analysis_enabled" if analysis else "pipeline_enabled"
    with db.get_conn() as conn:
        db.set_setting(conn, key, "false")
        conn.commit()
    what = "AI analysis" if analysis else "entire pipeline (scrape + fetch + analyze)"
    console.print(f"[yellow]Paused: {what}.[/yellow] Daily cloud runs will no-op until `resume`.")


@app.command()
def resume():
    """Re-enable everything paused."""
    from database import db
    with db.get_conn() as conn:
        db.set_setting(conn, "pipeline_enabled", "true")
        db.set_setting(conn, "analysis_enabled", "true")
        conn.commit()
    console.print("[green]Resumed: pipeline fully enabled.[/green]")


@app.command("set-budget")
def set_budget(usd: float = typer.Argument(..., help="Monthly cap in USD; 0 = no cap")):
    """Cap monthly AI spend — analyze refuses to start once the month hits this."""
    from database import db
    with db.get_conn() as conn:
        db.set_setting(conn, "monthly_budget_usd", str(usd))
        spent = db.month_spend_usd(conn)
        conn.commit()
    console.print(f"[green]Budget set to ${usd:.2f}/month[/green] "
                  f"(this month so far: ${spent:.2f})")


@app.command()
def settings():
    """Show all pipeline control switches and this month's spend."""
    from database import db
    with db.get_conn() as conn:
        rows = db.all_settings(conn)
        spent = db.month_spend_usd(conn)
    t = Table(title="pipeline settings")
    t.add_column("switch"); t.add_column("value"); t.add_column("updated")
    for r in rows:
        t.add_row(r["key"], r["value"], r["updated_at"].strftime("%Y-%m-%d %H:%M"))
    console.print(t)
    console.print(f"Spend this month: [bold]${spent:.2f}[/bold]")


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


@app.command()
def tldr(days: int = typer.Option(1, help="Look-back window in days (by analysis time)"),
         limit: int = typer.Option(20, help="Max articles to show"),
         source: str = typer.Option(None, help="Filter to one source, e.g. entrackr"),
         full: bool = typer.Option(False, help="Also show why-it-matters and takeaways")):
    """TL;DR of recently analyzed articles (Layer-2 executive summaries)."""
    from database import db
    with db.get_conn() as conn:
        rows = db.get_recent_tldrs(conn, days, limit, source)
    if not rows:
        console.print("[yellow]No analyzed articles in this window — run analyze first.[/yellow]")
        raise typer.Exit()
    for r in rows:
        j = r["result_json"]
        date = r["published_at"].strftime("%d %b") if r["published_at"] else "?"
        console.print(f"\n[bold]{r['title']}[/bold]  [dim]({r['source']}, {date})[/dim]")
        console.print(j.get("one_minute_summary") or j.get("what_happened", ""))
        if full:
            if j.get("why_it_matters"):
                console.print(f"[cyan]Why it matters:[/cyan] {j['why_it_matters']}")
            for b in j.get("key_takeaways", []):
                console.print(f"  • {b}")
        console.print(f"[dim]{r['url']}[/dim]")


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
