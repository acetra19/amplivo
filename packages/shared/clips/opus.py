"""OpusClip API client – dry-run safe for Amplivo Clips MVP."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from packages.shared.settings_store import get_runtime


class OpusClipError(RuntimeError):
    pass


async def _api_key() -> str:
    return (await get_runtime("opusclip_api_key")) or ""


async def create_project_from_url(source_url: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit a long-form URL for clipping. Returns project + clip placeholders."""
    key = await _api_key()
    if dry_run or not key:
        project_id = f"dry_{uuid.uuid4().hex[:12]}"
        return {
            "dry_run": True,
            "project_id": project_id,
            "clip_url": f"https://clips.amplivo.net/dry/{project_id}.mp4",
            "raw": {"status": "simulated"},
        }

    # Public OpusClip API surface evolves; keep a minimal create call.
    # Docs: https://help.opus.pro/api-reference/overview
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"url": source_url}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.opus.pro/api/v1/projects",
            headers=headers,
            json=payload,
        )
        if resp.status_code >= 400:
            raise OpusClipError(f"OpusClip HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    project_id = str(data.get("id") or data.get("project_id") or "")
    clip_url = None
    clips = data.get("clips") or data.get("data") or []
    if isinstance(clips, list) and clips:
        first = clips[0] if isinstance(clips[0], dict) else {}
        clip_url = first.get("url") or first.get("download_url")
    return {
        "dry_run": False,
        "project_id": project_id,
        "clip_url": clip_url,
        "raw": data,
    }
