"""Central configuration: env loading, model routing, paths."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- Google Cloud / Vertex AI ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")

# --- Supabase (direct Postgres) ---
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "")

# --- Paths ---
PROMPTS_DIR = PROJECT_ROOT / "prompts"
OUTPUT_DIR = PROJECT_ROOT / "output"
BRIEFINGS_DIR = OUTPUT_DIR / "briefings"
REPORTS_DIR = OUTPUT_DIR / "reports"
SOURCES_YAML = PROJECT_ROOT / "config" / "sources.yaml"
SCHEMA_SQL = PROJECT_ROOT / "database" / "schema.sql"

# --- Model routing: layer number -> Gemini model ---
FLASH = "gemini-2.5-flash"
PRO = "gemini-2.5-pro"
# Flash-only routing (user decision 2026-07-12, cost: ~₹6/article vs ~₹17.4 with
# Pro on layers 3-6/8). To restore Pro for any layer, change its value back to PRO.
LAYER_MODEL_MAP = {
    1: FLASH,  # structured extraction
    2: FLASH,  # executive summary
    3: FLASH,  # business analysis
    4: FLASH,  # product analysis
    5: FLASH,  # investment analysis
    6: FLASH,  # PM learning
    7: FLASH,  # interview prep
    8: FLASH,  # framework mapping
}

LAYER_NAMES = {
    1: "extraction",
    2: "summary",
    3: "business",
    4: "product",
    5: "investment",
    6: "pm_learning",
    7: "interview",
    8: "frameworks",
}

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768

# $ per 1M tokens (interactive pricing; batch is ~50% of this)
MODEL_PRICING = {
    FLASH: {"input": 0.30, "output": 2.50, "cached": 0.075},
    PRO: {"input": 1.25, "output": 10.00, "cached": 0.31},
}

MAX_RETRIES = 3
MIN_ARTICLE_WORDS = 80  # below this, article text considered a failed fetch
