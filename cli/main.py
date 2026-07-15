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
    cur = lo
    while cur < hi:
        nxt = min(cur + timedelta(days=window), hi)
        articles = gn.discover_window(cur, nxt)  # slow part — no DB conn held
        # fresh connection per window: Supabase drops connections held for hours
        with db.get_conn() as conn:
            if _gate(conn, "pipeline_enabled"):
                return
            new = dup = 0
            for a in articles:
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


@app.command("backfill-status")
def backfill_status():
    """Are the historical sweep / text-download jobs still running, and how far along?"""
    import subprocess
    from database import db

    def alive(pattern: str) -> bool:
        return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0

    sweep = alive("backfill-discover")
    fetch = alive("cli.main fetch-text")
    console.print(f"discovery sweep: {'[green]RUNNING[/green]' if sweep else '[dim]not running[/dim]'}")
    console.print(f"text download:   {'[green]RUNNING[/green]' if fetch else '[dim]not running[/dim]'}")
    with db.get_conn() as conn:
        r = conn.execute(
            "SELECT count(*) n, min(published_at) lo, max(published_at) hi FROM articles"
        ).fetchone()
        by = conn.execute(
            "SELECT processing_status s, count(*) c FROM articles GROUP BY 1 ORDER BY 1"
        ).fetchall()
    console.print(f"\narticles: {r['n']}  (published {r['lo']:%d %b %Y} → {r['hi']:%d %b %Y})")
    for row in by:
        console.print(f"  {row['s']}: {row['c']}")
    if not sweep and not fetch:
        console.print("\n[bold]Both jobs idle.[/bold] Sweep is complete when coverage reaches "
                      "early Jul 2026 and 'pending' stops growing; pending articles still "
                      "waiting for text will be picked up by the next fetch run.")


@app.command("fetch-text")
def fetch_text(limit: int = typer.Option(50, help="Max articles to fetch this run")):
    """Download full article text for pending articles."""
    from scrapers.fetch_text import fetch_article_text
    from database import db

    import psycopg as _psycopg

    ok, failed = 0, 0
    remaining = limit
    db_errors = 0
    # batches of 25 on fresh connections; a dropped connection mid-batch is caught
    # and the loop reconnects and continues (commit is per-article, so at most the
    # in-flight article is retried). Failing articles bump retry_count and drop out
    # of the query at 3 — the loop ends when no eligible pending articles remain.
    while remaining > 0:
        try:
            with db.get_conn() as conn:
                if _gate(conn, "pipeline_enabled"):
                    return
                pending = db.get_articles_by_status(conn, "pending", min(25, remaining))
                if not pending:
                    break
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
            remaining -= len(pending)
            db_errors = 0
        except _psycopg.OperationalError as e:
            db_errors += 1
            if db_errors >= 5:
                console.print(f"[red]DB unreachable after 5 straight attempts: {e}[/red]")
                raise
            console.print(f"[yellow]DB connection dropped — reconnecting ({db_errors}/5)[/yellow]")
    console.print(f"[green]{ok} articles fetched[/green], {failed} failed")


@app.command()
def analyze(article_id: int = typer.Option(None, help="Analyze one specific article"),
            limit: int = typer.Option(5, help="Max articles to analyze this run"),
            since: str = typer.Option(None, help="Only articles published on/after YYYY-MM-DD"),
            extract_only: bool = typer.Option(False, "--extract-only",
                help="Stop after Layer 1 (facts+dedup only, ~₹1/article); layers 2-8 can be added later")):
    """Run the 8-layer Gemini analysis on fetched articles."""
    import psycopg as _psycopg
    from analysis.pipeline import process_article
    from database import db

    def _over_budget(conn) -> bool:
        budget = float(db.get_setting(conn, "monthly_budget_usd", "0") or 0)
        spent = db.month_spend_usd(conn)
        if budget and spent >= budget:
            console.print(f"[yellow]Stopped: monthly budget reached "
                          f"(${spent:.2f} of ${budget:.2f}) — raise it with "
                          f"`set-budget` or wait for next month.[/yellow]")
            return True
        return False

    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled", "analysis_enabled") or _over_budget(conn):
            return
        db.requeue_stuck_articles(conn)
        conn.commit()
        if article_id:
            art = db.get_article(conn, article_id)
            if not art:
                console.print(f"[red]No article with id {article_id}[/red]")
                raise typer.Exit(1)
            r = process_article(conn, art, extract_only=extract_only)
            console.print(f"[green]1 article processed[/green], cost ${r['cost_usd']:.4f}")
            return

    # batch mode: fresh connection per chunk + reconnect on drops (long runs)
    processed, total, db_errors = 0, 0.0, 0
    while processed < limit:
        try:
            with db.get_conn() as conn:
                if _over_budget(conn):
                    break
                batch = db.get_articles_by_status(conn, "fetched",
                                                  min(5, limit - processed), since)
                if not batch:
                    break
                for art in batch:
                    try:
                        r = process_article(conn, art, extract_only=extract_only)
                        total += r["cost_usd"]
                    except Exception:
                        continue  # already logged + marked failed; keep going
                processed += len(batch)
            db_errors = 0
        except _psycopg.OperationalError as e:
            db_errors += 1
            if db_errors >= 5:
                console.print(f"[red]DB unreachable after 5 straight attempts: {e}[/red]")
                raise
            console.print(f"[yellow]DB connection dropped — retrying in 30s ({db_errors}/5)[/yellow]")
            import time as _time
            _time.sleep(30)
    console.print(f"[green]{processed} articles processed[/green], "
                  f"total cost ${total:.4f}")


def _company_context(conn, company_id: int) -> str:
    """One outreach-ready line: latest round + one-line thesis from Layer 3."""
    from database import db
    ov = conn.execute(
        "SELECT latest_stage, latest_amount_usd, latest_round_date "
        "FROM companies_overview WHERE id = %s", (company_id,)).fetchone()
    thesis = conn.execute(
        """
        SELECT result_json->>'problem_solved' AS t FROM analysis_results
        WHERE company_id = %s AND layer_number = 3
        ORDER BY article_id DESC LIMIT 1
        """, (company_id,)).fetchone()
    bits = []
    if ov and (ov["latest_stage"] or ov["latest_amount_usd"]):
        stage = ov["latest_stage"] if (ov["latest_stage"] or "") not in ("unknown", "") else ""
        amt = f" ${ov['latest_amount_usd']/1e6:.1f}M" if ov["latest_amount_usd"] else ""
        when = f" on {ov['latest_round_date']:%d %b}" if ov["latest_round_date"] else ""
        bits.append(f"raised {stage}{amt}{when}".replace("raised  ", "raised "))
    if thesis and thesis["t"]:
        first = thesis["t"].split(". ")[0][:140]
        bits.append(first)
    return " · ".join(bits)


@app.command("score-targets")
def score_targets():
    """Recompute job_target_score for every company (ranking for find-roles)."""
    from jobs.scoring import recompute_scores
    from database import db
    with db.get_conn() as conn:
        if _gate(conn, "job_mode"):
            return
        n = recompute_scores(conn)
        top = conn.execute(
            "SELECT name, job_target_score FROM companies "
            "ORDER BY job_target_score DESC LIMIT 5").fetchall()
    console.print(f"[green]{n} companies scored.[/green] Top targets:")
    for t in top:
        console.print(f"  {t['job_target_score']:.2f}  {t['name']}")


@app.command("dismiss-role")
def dismiss_role(role_id: int = typer.Argument(..., help="Role id shown by find-roles")):
    """Hide a role from future find-roles output."""
    from database import db
    with db.get_conn() as conn:
        row = conn.execute(
            "UPDATE job_roles SET dismissed = TRUE WHERE id = %s RETURNING title",
            (role_id,)).fetchone()
        conn.commit()
    console.print(f"[yellow]Dismissed:[/yellow] {row['title']}" if row
                  else f"[red]No role with id {role_id}[/red]")


@app.command("find-roles")
def find_roles(role: str = typer.Option(None, help="Title keyword filter, e.g. 'product'"),
               pm: bool = typer.Option(False, "--pm", help="Only PM-class roles (PM/APM/analyst/adjacent)"),
               location: str = typer.Option(None, help="Location keyword, e.g. 'bangalore'"),
               funded_within: int = typer.Option(90, help="Companies funded in the last N days"),
               limit: int = typer.Option(10, help="Max companies to check"),
               new_since: int = typer.Option(None, "--new-since", help="Only roles FIRST SEEN in the last N days (reads stored roles, no fetching)"),
               deep: bool = typer.Option(False, help="AI-search for careers pages when unknown (~₹3/company)")):
    """Ranked job openings at freshly-funded startups (best-fit companies first)."""
    from jobs.roles_finder import roles_for_company, store_roles, location_matches
    from jobs.classifier import classify_title, PM_CLASSES
    from database import db

    def match(title: str, loc: str | None, role_class: str | None) -> bool:
        if pm and (role_class or classify_title(title)) not in PM_CLASSES:
            return False
        if role and role.lower() not in title.lower():
            return False
        return location_matches(location, loc)

    with db.get_conn() as conn:
        if _gate(conn, "pipeline_enabled", "job_mode"):
            return

        if new_since:
            rows = conn.execute(
                """
                SELECT jr.id, jr.title, jr.location, jr.url, jr.role_class,
                       c.id AS company_id, c.name, c.hq_city, c.job_target_score
                FROM job_roles jr JOIN companies c ON c.id = jr.company_id
                WHERE jr.first_seen >= now() - make_interval(days => %s)
                  AND NOT jr.dismissed
                ORDER BY c.job_target_score DESC NULLS LAST, jr.first_seen DESC
                """, (new_since,)).fetchall()
            rows = [r for r in rows if match(r["title"], r["location"], r["role_class"])]
            if not rows:
                console.print(f"[yellow]No matching roles first seen in the last {new_since} days.[/yellow]")
                return
            console.print(f"[bold]{len(rows)} new roles in the last {new_since} days:[/bold]\n")
            last_co = None
            for r in rows:
                if r["company_id"] != last_co:
                    ctx = _company_context(conn, r["company_id"])
                    console.print(f"[bold]{r['name']}[/bold] "
                                  f"[dim](score {r['job_target_score'] or 0:.2f}"
                                  f"{' · ' + ctx if ctx else ''})[/dim]")
                    last_co = r["company_id"]
                loc = f" — {r['location']}" if r["location"] else ""
                console.print(f"  • [{r['id']}] {r['title']}{loc}")
            return

        companies = db.recently_funded_companies(conn, funded_within, limit)
        if not companies:
            console.print("[yellow]No recently funded companies in that window.[/yellow]")
            raise typer.Exit()
        console.print(f"Checking {len(companies)} best-fit companies "
                      f"(ranked by job_target_score)…\n")
        shown = 0
        near_misses = []
        for c in companies:
            roles, kind = roles_for_company(conn, dict(c), deep=deep)
            store_roles(conn, c["id"], roles, kind)
            conn.commit()
            matches = [r for r in roles if match(r["title"], r.get("location"), None)]
            if not matches:
                if roles:
                    near_misses.append(f"{c['name']} ({len(roles)} openings)")
                continue
            shown += 1
            ctx = _company_context(conn, c["id"])
            console.print(f"[bold]{c['name']}[/bold]  [dim](score {c['job_target_score'] or 0:.2f}"
                          f" · {c['hq_city'] or '?'}{' · ' + ctx if ctx else ''} · via {kind})[/dim]")
            for r in matches[:10]:
                loc = f" — {r['location']}" if r.get("location") else ""
                console.print(f"  • {r['title']}{loc}")
                if r.get("url"):
                    console.print(f"    [dim]{r['url']}[/dim]")
            console.print()
        # roles just stored may unlock the +0.5 has_pm_role factor — refresh scores
        from jobs.scoring import recompute_scores
        recompute_scores(conn)
        if not shown:
            console.print("[yellow]No open roles matched the filters.[/yellow]")
            if near_misses:
                console.print("Openings exist but didn't match: " + ", ".join(near_misses))
            else:
                console.print("No careers pages known yet — try --deep to discover them "
                              "via AI search (~₹3/company).")


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
