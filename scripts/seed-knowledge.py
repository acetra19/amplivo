#!/usr/bin/env python3
"""Re-run knowledge seed on existing database (safe to run multiple times)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from packages.shared.db import get_connection

SEED_FILES = [
    "database/03-knowledge-seed.sql",
    "database/06-systeme-knowledge-seed.sql",
]


async def main() -> None:
    async with get_connection() as conn:
        for rel_path in SEED_FILES:
            sql_path = ROOT / rel_path
            sql = sql_path.read_text(encoding="utf-8")
            statements = [
                s.strip() for s in sql.split(";")
                if s.strip() and not s.strip().startswith("--")
            ]
            for stmt in statements:
                await conn.execute(stmt)
            print(f"Applied {rel_path}")
    count = await _count_chunks()
    print(f"Knowledge seed applied. Total chunks: {count}")


async def _count_chunks() -> int:
    async with get_connection() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunks") or 0


if __name__ == "__main__":
    asyncio.run(main())
