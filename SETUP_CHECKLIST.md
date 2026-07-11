# One-time setup checklist (Ritika)

## TL;DR — current state (2026-07-11)

**Setup is DONE except Netlify (§4, waits for the frontend).** Everything is live and
verified end-to-end:

| What | State |
|------|-------|
| Supabase | ✅ project live (`ap-southeast-1`), schema applied, articles flowing |
| GCP / Vertex AI | ✅ project `startup-extractor`, gcloud config `ritika`, pipeline ran all 8 layers (~₹17/article) |
| GCS bucket | ✅ `startup-extractor-batch` (for the backfill later) |
| GitHub | ✅ private repo `ritikadas98/startup-extractor`, commits authored by Ritika |
| Daily automation | ✅ GitHub Actions, 06:00 IST, keyless GCP auth (WIF, no key file) |
| GCP credits | ~₹1.22L available; the ₹28k free-trial credit **expires 20 Aug 2026** — use it first (it covers the backfill ~10×) |

**Next action:** review analysis quality (`analyze` output) and tune prompts **before**
any bulk processing — see CLAUDE.md "NEXT".

The rest of this file is the step-by-step guide, kept for reference / redoing any part.

---

Everything below needs **your** accounts. The code is already built and tested — these
steps just connect it to your Supabase, Google Cloud, and GitHub accounts.

**Read this first:**

- **Browser steps** → always use **your Chrome profile**, not the Mac's default one.
  Click your profile picture in Chrome's top-right corner and switch to your profile
  before opening any link below. If a site shows you already logged in as Ayan,
  you're in the wrong profile.
- **Terminal steps** → open the **Terminal** app (press `Cmd+Space`, type `Terminal`,
  press Enter). Commands shown in code blocks are typed there, one line at a time,
  pressing Enter after each. You can copy-paste them.
- **Every terminal session starts the same way.** Before running any project command, run:
  ```bash
  cd ~/startup_intel
  source .venv/bin/activate
  ```
  The second line activates the project's Python environment — your prompt will show
  `(.venv)` at the start when it worked. If you close Terminal and come back later,
  run both lines again.
- This Mac is Ayan's, so his GitHub/Google logins already exist on it. The steps below
  are written so your accounts get **added alongside** his without touching his setup.
  Where there's a risk of using the wrong account, the step says how to check.

---

## 1. Supabase — the database (~10 min)

Supabase hosts the Postgres database where all scraped articles and analyses are stored.

### 1a. Create the project

1. In your Chrome profile, go to https://supabase.com and click **Sign in**
   (top right). Sign in with your GitHub account (or email — either is fine).
2. Once you're in the dashboard, click **New project** (green button).
3. Fill in the form:
   - **Organization**: pick your personal org (it's created automatically on signup).
   - **Project name**: `startup-intel` (anything works).
   - **Database password**: click **Generate a password** — then **copy it and save it
     somewhere safe** (Notes app is fine). You need it in step 1c and can't view it
     again later, only reset it.
     - *Tip: if you type your own password, use only letters and numbers. Symbols like
       `@`, `#`, `%` break the connection string later unless specially encoded.*
   - **Region**: `South Asia (Mumbai)` / `ap-south-1`.
   - **Pricing plan**: Free.
4. Click **Create new project**. A progress screen shows for ~2 minutes while the
   database is provisioned. Wait until the project dashboard loads fully.

### 1b. Enable the vector extension

The pipeline needs the `pgvector` extension (used later for semantic search).

1. In the left sidebar, click the **SQL Editor** icon (looks like a terminal/page icon).
2. Click **New query** if a blank editor isn't already open.
3. Paste exactly this and click **Run** (or press `Cmd+Enter`):
   ```sql
   create extension if not exists vector;
   ```
4. Success looks like: `Success. No rows returned`. That's it.

### 1c. Get the connection string

1. At the **top of the page**, click the **Connect** button (next to the project name).
2. A dialog opens. Under **Connection String** find the **Session pooler** section
   (NOT "Direct connection", NOT "Transaction pooler" — the Session pooler works on
   any network and supports everything the pipeline needs).
3. Copy the URI. It looks like:
   ```
   postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
4. Replace the literal text `[YOUR-PASSWORD]` (including the square brackets) with the
   database password you saved in step 1a. Keep the final string handy for the next step.

### 1d. Create the `.env` file on the Mac

`.env` is a private file (never uploaded anywhere) that holds your credentials.

1. In Terminal:
   ```bash
   cd ~/startup_intel
   cp .env.example .env
   open -a TextEdit .env
   ```
   The last command opens the file in TextEdit.
2. Find the line starting with `SUPABASE_DB_URL=` and replace everything after the `=`
   with your full connection string from step 1c (password filled in, no square
   brackets, no quotes, no spaces). Save the file (`Cmd+S`) and close TextEdit.

### 1e. Verify — create the database tables

```bash
cd ~/startup_intel
source .venv/bin/activate
python -m cli.main init-db
```

- **Success**: it prints `Schema applied.` in green. Your database now has all its tables.
- **If it hangs for ~30s then errors with "connection ... failed"**: the URI or password
  is wrong. Re-check step 1c/1d — most common issue is the `[YOUR-PASSWORD]` placeholder
  still being there, or a typo in the password.
- **If it says "password authentication failed"**: the password is wrong. In Supabase:
  Project Settings → Database → **Reset database password**, then update `.env`.

Running `init-db` again later is harmless — it only creates what's missing.

---

## 2. Google Cloud / Vertex AI — the AI models (~20 min)

Vertex AI runs the Gemini models that produce the 8-layer analyses. This is the only
part that costs money (your free Vertex credits apply).

### 2a. Create the project (browser)

1. In your Chrome profile, go to https://console.cloud.google.com and make sure the
   account avatar in the **top-right corner is YOU**, not Ayan. If not, click it and
   switch accounts.
2. At the top of the page, click the **project picker** (a dropdown next to the
   "Google Cloud" logo — it may say "Select a project"). In the dialog, click
   **New project** (top right).
3. **Project name**: `startup-intel`. Below the name field, Google shows the
   **Project ID** it generated (e.g. `startup-intel-451216`). **Write this ID down** —
   it's what the code uses, and it is often *not* identical to the name. Click **Create**.
4. Wait for the notification bell (top right) to show the project was created, then use
   the project picker to **switch into** the new project. From here on, always confirm
   the picker shows `startup-intel` before clicking anything.

### 2b. Enable billing

Vertex AI won't run without billing enabled, even with free credits.

1. Left hamburger menu (☰) → **Billing**.
2. If it says the project has no billing account: click **Link a billing account** and
   pick yours (or create one — this is where your free-trial credits live). Follow the
   prompts; a card may be required but credits are consumed first.

### 2c. Enable the Vertex AI API

1. ☰ menu → **APIs & Services** → **Enabled APIs & services** → click **+ Enable APIs
   and services** (top).
2. In the search box type `Vertex AI API`, click the result named exactly
   **Vertex AI API**, then click **Enable**. Takes ~1 minute.

### 2d. Log in on the Mac (terminal)

gcloud (Google's command-line tool) is already installed on this Mac but not on the
PATH. These steps create a **separate gcloud profile for you** so Ayan's Google setup
is untouched.

Run these one at a time:

```bash
export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH"
```
*(Makes gcloud usable in this Terminal window. If you open a new Terminal window later,
run it again — or ask Claude to add it to the shell config permanently.)*

```bash
gcloud config configurations create ritika
```
*(Creates your own named profile. If it says it already exists, run
`gcloud config configurations activate ritika` instead.)*

```bash
gcloud auth login
```
*(Your browser opens. **Pick YOUR Google account** — the same one from step 2a. If the
browser opens in the wrong Chrome profile, copy the URL into a window of your profile.
Click Allow.)*

```bash
gcloud config set project YOUR-PROJECT-ID
```
*(Replace `YOUR-PROJECT-ID` with the Project ID you wrote down in step 2a, e.g.
`startup-intel-451216`.)*

```bash
gcloud auth application-default login
```
*(Browser opens **again** — yes, a second login; this one is the credential the Python
code itself uses. Same account, click Allow.)*

Verify it stuck:
```bash
gcloud config list
```
Should show `account = ` your email and `project = ` your project ID.

### 2e. Add the project ID to `.env`

Open `.env` again (`open -a TextEdit ~/startup_intel/.env`) and fill in:
```
GCP_PROJECT_ID=your-project-id-here
GCP_REGION=us-central1
```
(`GCP_REGION` is probably already set to `us-central1` — leave it as is.) Save and close.

### 2f. Create the storage bucket (for the backfill, later)

Needed only for the big historical backfill, but easiest to do now while you're logged in:
```bash
gcloud storage buckets create gs://YOUR-PROJECT-ID-batch --location=us-central1
```
Then put the bucket name in `.env` as `GCS_BUCKET=YOUR-PROJECT-ID-batch` (just the
name, no `gs://` prefix).

*(If you see a notice recommending `gcloud storage` over `gsutil`, that's just Google
deprecating the older `gsutil` tool — both still work; the command above already uses
the new one.)*

### 2g. Verify — run one real analysis

This needs at least one scraped article, so run the full mini-pipeline:

```bash
cd ~/startup_intel
source .venv/bin/activate
python -m cli.main scrape --days 1        # prints "N new articles stored" in green
python -m cli.main fetch-text --limit 5   # prints "N articles fetched"
python -m cli.main analyze --limit 1      # the real test — takes 1–3 minutes
```

- **Success**: `analyze` prints `1 articles processed` in green, and
  `python -m cli.main status` shows analysis rows. `python -m cli.main cost-summary`
  shows what it cost (a fraction of a cent).
- **"Permission denied" / "API not enabled" errors**: step 2b or 2c isn't finished, or
  the login in 2d used the wrong Google account.
- **"Could not automatically determine credentials"**: the
  `gcloud auth application-default login` step (2d, last login) was skipped.

---

## 3. GitHub — code hosting + daily automation (~10 min)

GitHub stores the code and runs the pipeline automatically every morning at 06:00 IST
(via GitHub Actions).

⚠️ **This machine already has Ayan's GitHub logged in.** The steps below add your
account next to his and make sure everything for this repo happens as **you**. Don't
skip the verification sub-steps.

### 3a. Set your identity for THIS repo only

```bash
cd ~/startup_intel
git config user.name  "Your Name"
git config user.email "your-github-email@example.com"
```
Use the email your GitHub account is registered with. Note there is **no `--global`**
in those commands — that's deliberate; global config is Ayan's and must not change.

Check it took:
```bash
git config user.name && git config user.email
```
Should print your name and email.

### 3b. Log in to GitHub on the command line

```bash
gh auth login
```
Answer the prompts like this (arrow keys + Enter):
- *Where do you use GitHub?* → **GitHub.com**
- *Preferred protocol?* → **HTTPS**
- *Authenticate Git with your GitHub credentials?* → **Yes**
- *How would you like to authenticate?* → **Login with a web browser**
- It shows a one-time code like `ABCD-1234` — copy it, press Enter, and the browser
  opens. **Make sure you're in YOUR Chrome profile / logged into YOUR GitHub**, enter
  the code, click **Authorize**.

Now verify the right account is **active**:
```bash
gh auth status
```
You'll see two accounts listed (Ayan's and yours). Yours must say **Active account:
true**. If Ayan's is active instead, run:
```bash
gh auth switch --user YOUR-GITHUB-USERNAME
```

### 3c. First commit and push

```bash
cd ~/startup_intel
git add -A
git commit -m "Initial pipeline: scrapers, dedup, 8-layer Vertex analysis, CLI"
gh repo create startup-intel --private --source . --push
```
The last command creates a **private** repo named `startup-intel` under your GitHub
account and uploads the code.

**Verify — this is the important one:**
```bash
git log --format='%an %ae'
```
Must print **your** name and email, not Ayan's. Also open
`https://github.com/YOUR-USERNAME/startup-intel` in your browser — the repo should
exist under your account.

*(If the commit shows Ayan's name: step 3a was missed. Fix the config as in 3a, then
run `git commit --amend --reset-author --no-edit` and `git push --force`.)*

### 3d. Add the secrets for the daily automation

**✅ Done 2026-07-11 (via terminal, not the browser).** What was set up, for the record:

GitHub Actions authenticates to GCP **keylessly** via Workload Identity Federation —
GCP's newer projects forbid downloadable service-account keys (policy
`iam.disableServiceAccountKeyCreation`), and keyless is the recommended approach anyway
(nothing to leak or rotate). The pieces:

- Service account `github-actions@startup-extractor.iam.gserviceaccount.com` with roles
  **Vertex AI User** + **Storage Object Admin**.
- Workload identity pool `github` with OIDC provider `github-provider`, which trusts
  GitHub Actions tokens **only from the `ritikadas98/startup-extractor` repo**.
- The repo's `.github/workflows/daily.yml` uses `google-github-actions/auth@v2` with
  that provider (needs `permissions: id-token: write`, already in the file).
- Three repo secrets (Settings → Secrets and variables → Actions): `GCP_PROJECT_ID`,
  `GCP_REGION`, `SUPABASE_DB_URL`. There is **no `GCP_SA_KEY`** — no key exists.

If this ever needs redoing, the equivalent gcloud commands are:
```bash
gcloud iam service-accounts create github-actions
gcloud projects add-iam-policy-binding startup-extractor \
  --member="serviceAccount:github-actions@startup-extractor.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"   # repeat with roles/storage.objectAdmin
gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global --workload-identity-pool=github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'ritikadas98/startup-extractor'"
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@startup-extractor.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/498496822134/locations/global/workloadIdentityPools/github/attribute.repository/ritikadas98/startup-extractor"
```

### 3e. Verify — run the automation once by hand

1. Repo page → **Actions** tab → in the left list click **daily-intelligence** →
   **Run workflow** button (right side) → green **Run workflow**.
2. A run appears in the list (refresh if needed). Click it to watch. It should finish
   with a **green check** in a few minutes.
3. **Red X?** Click into the run, click the failed step, and read the last lines of the
   log — 90% of the time it's a typo in one of the four secrets. Fix the secret
   (Settings → Secrets → pencil icon) and run the workflow again.

From now on this runs automatically every day at 06:00 IST.

---

## 4. Netlify — the website (later, Phase F — skip for now)

The frontend isn't built yet. Once the `web/` folder exists:

1. In your Chrome profile: https://netlify.com → sign up with your GitHub account.
2. **Add new site** → **Import an existing project** → **GitHub** → authorize → pick
   the `startup-intel` repo.
3. Set **Base directory** to `web/`, then under environment variables add
   `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (both from Supabase:
   Project Settings → API).
4. Deploy.

---

## Done? Final check

Run:
```bash
cd ~/startup_intel && source .venv/bin/activate && python -m cli.main status
```
If it prints a table with article and analysis counts, everything is wired up. 🎉
