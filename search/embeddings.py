"""Embeddings for analyzed articles: semantic search + AI-assisted graph edges.

One 768-dim vector per fully-analyzed article (content_kind='analysis',
layer_number=0), composed from the title + Layer 2 summary + Layer 3 business
facts — the parts that describe what the company IS, not the funding mechanics.
"""
from analysis.vertex_client import get_client
from config.settings import EMBEDDING_MODEL, EMBEDDING_DIM
from utils.logger import get_logger

log = get_logger("embeddings")

MAX_CHARS = 8000  # stay well inside the embedding model's context


def embed_text(text: str) -> list[float]:
    from google.genai import types
    r = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text[:MAX_CHARS],
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return list(r.embeddings[0].values)


def compose_analysis_text(title: str, l2: dict | None, l3: dict | None) -> str:
    parts = [title or ""]
    if l2:
        parts.append(l2.get("one_minute_summary") or l2.get("what_happened") or "")
    if l3:
        for key in ("problem_solved", "customers", "revenue_model",
                    "competitive_advantage", "market_attractiveness"):
            if l3.get(key):
                parts.append(f"{key.replace('_', ' ')}: {l3[key]}")
        if l3.get("alternatives"):
            parts.append("alternatives: " + ", ".join(l3["alternatives"]))
    return "\n".join(p for p in parts if p)


def embed_pending(conn, limit: int = 100) -> int:
    """Embed complete articles that don't have an analysis embedding yet."""
    from database import db
    rows = db.articles_needing_embedding(conn, limit)
    done = 0
    for row in rows:
        text = compose_analysis_text(
            row["title"],
            db.get_layer_result(conn, row["id"], 2),
            db.get_layer_result(conn, row["id"], 3),
        )
        if not text.strip():
            continue
        vec = embed_text(text)
        db.insert_embedding(conn, row["id"], 0, "analysis", vec)
        conn.commit()
        done += 1
    log.info("embedded %d articles", done)
    return done
