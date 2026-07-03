"""Settings API routes – keys & deploy config via GUI."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from packages.shared.gamification import award_xp
from packages.shared.settings_store import export_env_file, get_all_masked, save_settings, test_connections

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    values: dict[str, str]
    pin: str | None = None


@router.get("")
async def get_settings():
    return await get_all_masked()


@router.put("")
async def update_settings(payload: SettingsUpdate):
    try:
        result = await save_settings(payload.values, payload.pin)
        if result["count"] > 0:
            try:
                await award_xp("settings_saved", f"Updated {result['count']} settings")
            except Exception:
                pass
        return {"ok": True, **result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/test")
async def test_settings():
    return await test_connections()


@router.get("/export-env")
async def download_env():
    content = await export_env_file()
    return {"env": content}


@router.get("/pin-required")
async def pin_required():
    from packages.shared.settings_store import get_runtime
    pin = await get_runtime("settings_pin")
    return {"required": bool(pin)}
