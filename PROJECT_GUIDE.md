# The Plain-English Guide to startup_intel

*For someone who wants to understand — not just run — this project. No jargon without
an explanation. Written 2026-07-11, after the system went fully live.*

---

## 1. What this actually is

Every morning, Indian startup news sites publish stories like *"Aukera raises ₹90 crore
to expand its lab-grown diamond stores."* Most people read the headline and move on.

This system reads the **full article**, then writes **eight layers of analysis** about
it — what happened, why it matters, how the business works, what a product manager
would do there, why investors said yes, what lessons it teaches, what interview
questions it could generate, and which business frameworks apply. All of it is saved
forever in a database, so over months it compounds into a personal knowledge base about
the Indian startup ecosystem — one that also happens to know which freshly-funded
companies are hiring.

The goal, in the project's own words: **learning first, job search second.**

```
 news sites ──► scrape ──► dedup ──► fetch full text ──► 8-layer AI analysis ──► database
 (5 sources)   (find new)  (skip     (download the       (Gemini models         (Supabase,
                            copies)   actual article)     on Google Cloud)       queryable forever)
```

Everything above runs automatically every morning at 06:00 IST. No human needed.

---

## 2. The journey of one article

The best way to understand the system is to follow one story through it:

1. **06:00 IST — discovery.** A robot (GitHub Actions — think of it as a free computer
   in the cloud that wakes up on a schedule) runs the scraper. It checks the RSS feeds
   of Entrackr, Inc42, YourStory, ET Tech, plus three Google News searches. Say it
   finds *"Aukera raises ₹90 crore"* on Entrackr.

2. **URL dedup.** Before saving, the system checks: have we seen this exact link
   before? Links are "normalized" first (tracking junk like `?utm_source=...` is
   stripped) so the same article shared two ways counts once.

3. **Fetch text.** The headline alone isn't enough to analyze, so the system downloads
   the article page and extracts the readable text from the HTML.

4. **Layer 1 — the cheap gatekeeper.** The article text goes to Gemini Flash (Google's
   fast, inexpensive AI model, ~₹1–3 per article) which extracts hard facts as
   structured data: company, amount, stage, investors, founders, city, industry — and
   since July 11, **hiring signals** (is the company hiring? which roles? what did they
   say about expansion?). Layer 1 also answers one crucial question: *is this actually
   a startup funding story?* If not — opinion piece, market report, IPO news — the
   pipeline stops right here. One cheap call instead of eight.

5. **Story dedup — the expensive-mistake preventer.** The same funding round gets
   covered by 3–5 outlets, each with a different URL, so step 2 can't catch it. Here
   the system asks: *have we already deeply analyzed this same company + same stage +
   roughly the same amount within the last 14 days?* If yes, this copy is marked as a
   duplicate, linked to the original, and stops. Cost of a duplicate: ~₹0.3 instead
   of ~₹17.

6. **Layers 2–8 — the deep read.** Only genuinely new funding events get here. Seven
   more AI calls, most to Gemini Pro (the smarter, pricier model), each with its own
   instructions file and each forced to answer in a strict JSON format:
   - **L2 Executive summary** — the one-minute version (this feeds the `tldr` command)
   - **L3 Business analysis** — problem, customers, revenue model, moat, competitors
   - **L4 Product analysis** — north-star metric, growth strategy, roadmap risks
   - **L5 Investment analysis** — why now, why these investors, remaining risks
   - **L6 PM lessons** — transferable product/growth/strategy/pricing lessons
   - **L7 Interview prep** — realistic PM interview questions + model answers
   - **L8 Frameworks** — which business frameworks (JTBD, flywheels…) apply and how

7. **Storage.** Every layer's output lands in the database with its exact cost in
   dollars, token counts, and processing time. Companies, funding rounds, investors,
   and founders get their own linked tables — so you can later ask questions like
   "which Bangalore fintechs raised Series A this quarter and are hiring PMs?"

---

## 3. The tech, and why each piece was chosen

| Piece | What it is | Why this one |
|---|---|---|
| **Python + Typer CLI** | The language everything is written in; commands like `python -m cli.main scrape` | Boring, reliable, easy for any future tool (or AI assistant) to extend |
| **Supabase** | A hosted Postgres database with a free tier | Free for this scale, managed (no server to babysit), and its row-level-security feature makes the future public frontend safe |
| **Vertex AI (Gemini)** | Google Cloud's way of using Gemini models | **Every single AI call goes through Vertex** — one client, in one file (`analysis/vertex_client.py`). Chosen because Ritika's free GCP credits apply here, and because Vertex bills to a project (no API key to leak) |
| **Gemini Flash vs Pro** | Two model tiers: fast-cheap vs smart-expensive | Routing per layer: facts and summaries → Flash; judgment-heavy analysis (L3–6, L8) → Pro. ~90% of cost is the Pro layers, which is why gating and dedup matter |
| **GitHub Actions** | Free scheduled computer in the cloud | Runs the whole pipeline daily at 06:00 IST; free for private repos at this usage |
| **GitHub repo** | `ritikadas98/startup-extractor`, private | Code lives in Ritika's account; every commit is authored by her |

---

## 4. The decisions log — what was decided and why

These are the judgment calls made while building, in rough order of importance:

**Structured output everywhere.** Every AI call must return JSON matching a strict
schema (defined in `analysis/schemas.py`). The model literally cannot answer in the
wrong shape. This is why the database is queryable instead of a pile of essays.

**Layer 1 gates everything.** Non-funding articles cost one Flash call (~₹2.6 measured)
instead of eight calls (~₹17.4). The scraper's keyword filter is deliberately loose —
it's cheaper to let Layer 1 reject borderline articles than to miss real ones.

**Story-level dedup runs *after* Layer 1, not before.** You need to know the company/
amount/stage to recognize "same event, different outlet" — and Layer 1 extracts exactly
that for ~2% of the full cost. Verified live: a duplicate cost $0.0031 vs $0.205.

**Keyless cloud authentication (the WIF story).** The original plan was to give GitHub
Actions a downloadable Google Cloud key file. GCP now blocks creating those on new
projects (it's a security footgun — a file that never expires and can leak). Instead of
overriding the protection, we used **Workload Identity Federation**: GitHub proves its
identity to Google cryptographically per-run, and Google only trusts tokens coming
specifically from Ritika's repo. Nothing exists that can be stolen.

**The shared-Mac safeguards.** This Mac is Ayan's; the project is Ritika's. The repo
has its own local git identity (Ritika), and a local rule that defeats Ayan's global
"rewrite GitHub URLs to SSH" config (his SSH key would otherwise be used). Rule of
thumb: never touch global config; check `gh auth status` before any GitHub operation.

**X/Twitter rejected, alternatives chosen.** Reading tweets via the official API starts
at $200/month — disproportionate when the whole pipeline runs on ~₹5k/month. Scraping X
violates their terms. Instead: hiring signals are extracted from articles we already
process (free), and Telegram/Reddit (both with free, legitimate APIs) are queued for the
roles-finder phase.

**No LinkedIn scraping, no paywalled sources.** Terms-of-service violations are fragile
foundations. Careers pages and public ATS APIs (Greenhouse/Lever/Ashby — structured
job data, no auth needed) are both legitimate and more reliable.

**Control switches live in the database, not in code.** `pause`, `resume`, `set-budget`
write to a settings table that **both** the laptop and the cloud runner read. One
command stops everything everywhere; a monthly budget cap hard-stops AI spending no
matter who triggers it. Built because the owner should never need to understand GitHub
to turn her own system off.

**Copyright posture.** Full article text is stored privately for analysis, but must
never be displayed publicly — the future frontend will show only our AI analyses,
titles, and links to the originals. Facts and original analysis are shareable;
republishing articles is not.

**One quirk worth remembering:** Postgres's JSONB storage silently re-orders JSON keys
by length. Symptom: "answer" displayed before "question" in the review page. Any future
UI must render fields in schema order, not storage order.

---

## 5. Money — measured, not estimated

All numbers below are from real runs (₹85/$):

| Item | Cost |
|---|---|
| One full 8-layer analysis (flash-only, since 2026-07-12) | **$0.058 (~₹4.9)** |
| One non-funding article (gated at L1) | ~$0.01 (~₹0.85) |
| One duplicate copy (gated after L1) | $0.003 (~₹0.3) |
| Supabase, GitHub Actions, Netlify | ₹0 (free tiers) |

(The smarter-but-pricier Pro model originally ran the 5 deep layers at ~₹17.4/article;
the user chose flash-only for cost. Any layer can be switched back with one line in
`config/settings.py`.)

**Monthly run-rate** (story dedup + flash-only, ~8–12 unique funding events/day):
**~₹1.8–2.5k/month**, capped by the budget switch (`set-budget`).

**One-time historical backfill**: ~1,350 discovered articles → roughly 600–800 full
analyses after gating/dedup ≈ **~₹4–5k** flash-only through the normal pipeline.

**Credits reality-check (corrected 2026-07-12):** the ₹27.9k signup credit (expires
**20 Aug 2026**) is general-purpose and covers our Gemini usage — the backfill and
daily runs until then are free. The ₹94.5k "GenAI App Builder" credit is likely
scoped to a Google product we don't use (Vertex AI Search) — pending verification via
its terms link in the billing console. **Plan for ~₹4.5–6.5k/month real cost from
September**, unless model-routing optimization (Flash for more layers) brings it down,
or a Google for Startups credit application succeeds.

---

## 6. Operating manual

Every session starts with:
```bash
cd ~/startup_intel && source .venv/bin/activate
```

| Command | What it does |
|---|---|
| `python -m cli.main status` | Counts: articles by state, companies, rounds, analyses |
| `python -m cli.main tldr --full` | Read today's analyses as one-minute briefings |
| `python -m cli.main cost-summary` | Exact AI spend by model |
| `python -m cli.main settings` | All control switches + this month's spend |
| `python -m cli.main pause` | Stop everything (laptop **and** cloud) until `resume` |
| `python -m cli.main pause --analysis` | Stop AI spending only; keep collecting articles for free |
| `python -m cli.main resume` | Turn everything back on |
| `python -m cli.main set-budget 25` | Monthly hard cap on AI spend, in USD |
| `python -m cli.main scrape / fetch-text / analyze` | Run pipeline steps manually |
| `python -m cli.main find-roles --role product --location bangalore` | Live openings at freshly-funded startups (`--deep` = AI-discover careers pages, ~₹3/company) |
| `python -m cli.main embed` / `build-graph` | Refresh semantic vectors + company-relationship edges (also run daily automatically) |

The daily cloud run does scrape → fetch → analyze automatically; these commands exist
for manual control and catching up.

---

## 7. Where things stand, and what's next

**Built and verified:** scrapers (5 sources) · URL + story dedup · 8-layer analysis
with cost tracking · hiring-signals extraction · daily cloud automation (keyless auth) ·
TL;DR briefings · pause/resume/budget controls · quality gate passed ("mostly pass",
2026-07-11).

**Next, in order:**
1. **Historical backfill (Phase G, date-sensitive)** — analyze ~240 days of past
   funding news via Vertex Batch Prediction, targeted at the credit expiring 20 Aug.
2. **Embeddings + knowledge graph (Phase C)** — connect companies by shared investors,
   competition, business model; enables "show me every quick-commerce play and how
   their strategies differ."
3. **Reports (Phase E)** — daily briefing, weekly trends, job-target scoring, the
   **roles finder** (your filters → freshly-funded companies → live openings from their
   ATS/careers pages), Telegram/Reddit signals, and the JOB_MODE off-switch.
4. **Frontend (Phase F)** — a small read-only website (briefing / companies / company
   detail / search), which is also how the knowledge base becomes shareable with others.
