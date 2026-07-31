"""OpusClip API client – dry-run safe for Amplivo Clips MVP."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from packages.shared.settings_store import get_runtime

BASE = "https://api.opus.pro/api"


class OpusClipError(RuntimeError):
    pass


async def _api_key() -> str:
    return (await get_runtime("opusclip_api_key")) or ""


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _first_clip_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    # Common shapes: {list: [...]}, {data: [...]}, {clips: [...]}
    for key in ("list", "data", "clips", "items"):
        items = payload.get(key)
        if isinstance(items, list) and items:
            first = items[0] if isinstance(items[0], dict) else {}
            url = (
                first.get("uri")
                or first.get("url")
                or first.get("downloadUrl")
                or first.get("download_url")
                or first.get("exportUrl")
            )
            if url:
                return str(url)
    return None


async def create_project_from_url(source_url: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Submit a long-form URL for clipping. Returns project + optional clip URL."""
    key = await _api_key()
    if dry_run or not key:
        project_id = f"dry_{uuid.uuid4().hex[:12]}"
        return {
            "dry_run": True,
            "project_id": project_id,
            "clip_url": f"https://clips.amplivo.net/dry/{project_id}.mp4",
            "status": "ready",
            "raw": {"status": "simulated"},
        }

    headers = _headers(key)
    payload = {
        "videoUrl": source_url,
        "curationPref": {
            "clipDurations": [[0, 90]],
            "genre": "Auto",
            "skipCurate": False,
        },
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(f"{BASE}/clip-projects", headers=headers, json=payload)
        if resp.status_code >= 400:
            raise OpusClipError(f"OpusClip HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

    project_id = str(
        data.get("projectId") or data.get("id") or data.get("project_id") or ""
    )
    clip_url = _first_clip_url(data)
    return {
        "dry_run": False,
        "project_id": project_id,
        "clip_url": clip_url,
        "status": "ready" if clip_url else "producing",
        "raw": data,
    }


async def fetch_exportable_clips(project_id: str) -> dict[str, Any]:
    """Poll exportable clips for a project. Empty list means still processing."""
    key = await _api_key()
    if not key:
        raise OpusClipError("missing_opusclip_api_key")
    if project_id.startswith("dry_"):
        return {
            "dry_run": True,
            "project_id": project_id,
            "clip_url": f"https://clips.amplivo.net/dry/{project_id}.mp4",
            "status": "ready",
            "raw": {},
        }

    headers = _headers(key)
    params = {"q": "findByProjectId", "projectId": project_id, "pageNum": 1, "pageSize": 10}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(f"{BASE}/exportable-clips", headers=headers, params=params)
        if resp.status_code >= 400:
            raise OpusClipError(f"OpusClip poll HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

    clip_url = _first_clip_url(data)
    return {
        "dry_run": False,
        "project_id": project_id,
        "clip_url": clip_url,
        "status": "ready" if clip_url else "producing",
        "raw": data,
    }


async def wait_for_clip(
    project_id: str,
    *,
    attempts: int = 3,
    delay_sec: float = 8.0,
) -> dict[str, Any]:
    """Short poll helper for sync API paths (drain continues later if still producing)."""
    last: dict[str, Any] = {"project_id": project_id, "status": "producing", "clip_url": None}
    for i in range(attempts):
        last = await fetch_exportable_clips(project_id)
        if last.get("clip_url"):
            return last
        if i + 1 < attempts:
            await asyncio.sleep(delay_sec)
    return last
