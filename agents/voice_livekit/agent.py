"""LiveKit voice agent skeleton – qualifies warm leads by phone."""

from __future__ import annotations

import logging

from packages.shared.config import settings

logger = logging.getLogger(__name__)

VOICE_INSTRUCTIONS = """You are a friendly B2B sales assistant calling on behalf of an agency.
Your goal: confirm interest, answer basic product questions, and book a demo or send trial link.
Speak clearly, in English. Keep responses under 30 seconds.
If the person is not interested, thank them and end politely.
Never claim features you are unsure about – offer to send documentation instead."""


def create_voice_agent():
    """Return LiveKit agent entrypoint. Requires livekit-agents installed."""
    try:
        from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
        from livekit.agents.voice import Agent, AgentSession
        from livekit.plugins import deepgram, elevenlabs, silero
    except ImportError as exc:
        raise RuntimeError("Install livekit-agents and plugins: pip install -r requirements.txt") from exc

    async def entrypoint(ctx: JobContext):
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

        session = AgentSession(
            vad=silero.VAD.load(),
            stt=deepgram.STT(api_key=settings.deepgram_api_key),
            tts=elevenlabs.TTS(api_key=settings.elevenlabs_api_key),
        )

        agent = Agent(instructions=VOICE_INSTRUCTIONS)
        await session.start(agent=agent, room=ctx.room)
        await session.say(
            "Hi, this is Alex from the sales team. "
            "You recently replied to our email – do you have two minutes to chat?"
        )

    return entrypoint, cli, WorkerOptions


def run_voice_worker():
    """CLI entry: python -m agents.voice_livekit.agent"""
    entrypoint, cli, WorkerOptions = create_voice_agent()
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not settings.livekit_url:
        logger.error("Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET in .env")
    else:
        run_voice_worker()
