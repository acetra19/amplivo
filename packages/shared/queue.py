"""Redis queues for voice calls and async jobs."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from packages.shared.config import settings

VOICE_QUEUE_KEY = "agentur:voice_queue"


async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def enqueue_voice_call(lead_id: UUID, reason: str = "interested") -> dict:
    client = await get_redis()
    item = {"lead_id": str(lead_id), "reason": reason}
    await client.rpush(VOICE_QUEUE_KEY, json.dumps(item))
    length = await client.llen(VOICE_QUEUE_KEY)
    await client.aclose()
    return {"queued": True, "lead_id": str(lead_id), "reason": reason, "queue_length": length}


async def dequeue_voice_call() -> dict[str, Any] | None:
    client = await get_redis()
    raw = await client.lpop(VOICE_QUEUE_KEY)
    await client.aclose()
    if not raw:
        return None
    return json.loads(raw)


async def voice_queue_length() -> int:
    client = await get_redis()
    length = await client.llen(VOICE_QUEUE_KEY)
    await client.aclose()
    return length


async def ping_redis() -> bool:
    try:
        client = await get_redis()
        ok = await client.ping()
        await client.aclose()
        return ok is True
    except Exception:
        return False
