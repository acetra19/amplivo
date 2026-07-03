"""Product knowledge retrieval (full-text; embeddings optional later)."""

from __future__ import annotations

from packages.shared.config import settings
from packages.shared.db import get_connection
from packages.shared.settings_store import get_runtime


async def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    slug = await get_runtime("affiliate_product_slug") or settings.affiliate_product_slug
    async with get_connection() as conn:
        product = await conn.fetchrow(
            "SELECT id FROM affiliate_products WHERE slug = $1 AND is_active = true",
            slug,
        )
        if not product:
            return []

        rows = await conn.fetch(
            """SELECT title, content, source
               FROM knowledge_chunks
               WHERE product_id = $1
                 AND to_tsvector('english', title || ' ' || content)
                     @@ plainto_tsquery('english', $2)
               ORDER BY ts_rank(
                 to_tsvector('english', title || ' ' || content),
                 plainto_tsquery('english', $2)
               ) DESC
               LIMIT $3""",
            product["id"], query, limit,
        )
        if rows:
            return [dict(r) for r in rows]

        rows = await conn.fetch(
            """SELECT title, content, source FROM knowledge_chunks
               WHERE product_id = $1 ORDER BY created_at LIMIT $2""",
            product["id"], limit,
        )
        return [dict(r) for r in rows]


def format_knowledge_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No product documentation loaded yet."
    parts = []
    for c in chunks:
        parts.append(f"### {c['title']} ({c['source']})\n{c['content']}")
    return "\n\n".join(parts)
