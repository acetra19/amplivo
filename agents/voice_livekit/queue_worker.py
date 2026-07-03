"""Process voice queue – logs leads ready for LiveKit calls (enable LiveKit later)."""

from __future__ import annotations

import asyncio
import logging

from uuid import UUID

from packages.shared.db import get_lead_by_id
from packages.shared.queue import dequeue_voice_call, voice_queue_length

logger = logging.getLogger(__name__)


async def process_once() -> bool:
    item = await dequeue_voice_call()
    if not item:
        return False

    lead = await get_lead_by_id(UUID(item["lead_id"]))
    if not lead:
        logger.warning("Voice queue: lead %s not found", item["lead_id"])
        return True

    logger.info(
        "VOICE CALL READY | lead=%s email=%s phone=%s reason=%s",
        item["lead_id"],
        lead["email"],
        lead["phone"] or "no phone",
        item.get("reason", "unknown"),
    )
    return True


async def run_worker(interval_sec: int = 30) -> None:
    logger.info("Voice queue worker started (logging mode – connect LiveKit when ready)")
    while True:
        remaining = await voice_queue_length()
        if remaining:
            logger.info("Voice queue: %d pending", remaining)
        while await process_once():
            pass
        await asyncio.sleep(interval_sec)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
