"""Gamification engine – XP, levels, achievements, daily quests."""

from __future__ import annotations

import json
from datetime import date

from packages.shared.db import get_connection

LEVEL_TITLES = [
    (1, "Rookie"),
    (2, "Prospect Hunter"),
    (3, "Pipeline Builder"),
    (4, "Deal Closer"),
    (5, "Revenue Machine"),
    (6, "Sales Legend"),
    (8, "Agency Overlord"),
    (10, "Unicorn Hunter"),
]

XP_REWARDS = {
    "lead_created": 10,
    "lead_icp_match": 25,
    "email_sent": 5,
    "email_reply": 20,
    "reply_interested": 50,
    "lead_qualified": 40,
    "trial_started": 200,
    "conversion": 500,
    "settings_saved": 25,
}

DAILY_QUESTS = [
    {"slug": "send_emails", "title": "Send 5 emails", "target": 5, "xp": 50, "event": "email_sent"},
    {"slug": "get_reply", "title": "Get 1 reply", "target": 1, "xp": 75, "event": "email_reply"},
    {"slug": "qualify_lead", "title": "Qualify 1 lead", "target": 1, "xp": 100, "event": "lead_qualified"},
]


def xp_for_level(level: int) -> int:
    """Cumulative XP required to reach level (level 1 = 0 XP)."""
    return (level - 1) ** 2 * 100


def level_from_xp(xp: int) -> int:
    level = 1
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def title_for_level(level: int) -> str:
    title = "Rookie"
    for min_lvl, name in LEVEL_TITLES:
        if level >= min_lvl:
            title = name
    return title


async def award_xp(event_type: str, description: str | None = None, metadata: dict | None = None) -> dict:
    amount = XP_REWARDS.get(event_type, 0)
    if amount <= 0:
        return {"xp_awarded": 0}

    today = date.today()
    new_achievements: list[str] = []

    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO xp_events (event_type, xp_amount, description, metadata)
               VALUES ($1, $2, $3, $4::jsonb)""",
            event_type, amount, description, json.dumps(metadata or {}),
        )
        row = await conn.fetchrow(
            """UPDATE operator_profile SET
                 xp_total = xp_total + $1,
                 last_active = $2,
                 streak_days = CASE
                   WHEN last_active = $2 - 1 THEN streak_days + 1
                   WHEN last_active = $2 THEN streak_days
                   ELSE 1
                 END,
                 updated_at = now()
               WHERE id = 1
               RETURNING xp_total, streak_days""",
            amount, today,
        )

        for quest in DAILY_QUESTS:
            if quest["event"] != event_type:
                continue
            await conn.execute(
                """INSERT INTO daily_quest_progress (quest_date, quest_slug, current_value, target_value, xp_reward)
                   VALUES ($1, $2, 1, $3, $4)
                   ON CONFLICT (quest_date, quest_slug) DO UPDATE SET
                     current_value = daily_quest_progress.current_value + 1""",
                today, quest["slug"], quest["target"], quest["xp"],
            )
            q = await conn.fetchrow(
                """SELECT current_value, target_value, completed, xp_reward
                   FROM daily_quest_progress WHERE quest_date = $1 AND quest_slug = $2""",
                today, quest["slug"],
            )
            if q and not q["completed"] and q["current_value"] >= q["target_value"]:
                await conn.execute(
                    "UPDATE daily_quest_progress SET completed = true WHERE quest_date = $1 AND quest_slug = $2",
                    today, quest["slug"],
                )
                bonus = q["xp_reward"]
                await conn.execute(
                    "UPDATE operator_profile SET xp_total = xp_total + $1 WHERE id = 1", bonus,
                )
                row = await conn.fetchrow("SELECT xp_total, streak_days FROM operator_profile WHERE id = 1")
                await conn.execute(
                    """INSERT INTO xp_events (event_type, xp_amount, description)
                       VALUES ('quest_complete', $1, $2)""",
                    bonus, f"Daily quest: {quest['title']}",
                )

        new_achievements = await _check_achievements(conn)

    xp_total = row["xp_total"]
    level = level_from_xp(xp_total)
    return {
        "xp_awarded": amount,
        "xp_total": xp_total,
        "level": level,
        "title": title_for_level(level),
        "new_achievements": new_achievements,
        "streak_days": row["streak_days"],
    }


async def _check_achievements(conn) -> list[str]:
    unlocked: list[str] = []
    checks = await conn.fetchrow(
        """SELECT
             (SELECT COUNT(*) FROM leads) AS leads,
             (SELECT COUNT(*) FROM interactions WHERE channel='email' AND direction='outbound') AS emails,
             (SELECT COUNT(*) FROM interactions WHERE channel='email' AND direction='inbound') AS replies,
             (SELECT COUNT(*) FROM interactions WHERE sentiment='interested') AS interested,
             (SELECT COUNT(*) FROM leads WHERE status='qualified') AS qualified,
             (SELECT COUNT(*) FROM conversions WHERE event_type='trial_start') AS trials,
             (SELECT COUNT(*) FROM conversions WHERE event_type='signup') AS conversions,
             (SELECT xp_total FROM operator_profile WHERE id=1) AS xp,
             (SELECT streak_days FROM operator_profile WHERE id=1) AS streak"""
    )

    rules = [
        ("first_lead", checks["leads"] >= 1),
        ("first_email", checks["emails"] >= 1),
        ("ten_emails", checks["emails"] >= 10),
        ("first_reply", checks["replies"] >= 1),
        ("first_interested", checks["interested"] >= 1),
        ("first_qualified", checks["qualified"] >= 1),
        ("first_trial", checks["trials"] >= 1),
        ("first_conversion", checks["conversions"] >= 1),
        ("level_5", level_from_xp(checks["xp"]) >= 5),
        ("streak_7", checks["streak"] >= 7),
    ]

    for slug, condition in rules:
        if not condition:
            continue
        exists = await conn.fetchval(
            "SELECT 1 FROM achievements_unlocked WHERE achievement_slug = $1", slug,
        )
        if exists:
            continue
        defn = await conn.fetchrow(
            "SELECT xp_reward FROM achievement_defs WHERE slug = $1", slug,
        )
        if not defn:
            continue
        await conn.execute(
            "INSERT INTO achievements_unlocked (achievement_slug) VALUES ($1)", slug,
        )
        if defn["xp_reward"]:
            await conn.execute(
                "UPDATE operator_profile SET xp_total = xp_total + $1 WHERE id = 1",
                defn["xp_reward"],
            )
        unlocked.append(slug)

    return unlocked


async def get_dashboard_state() -> dict:
    today = date.today()
    async with get_connection() as conn:
        profile = await conn.fetchrow("SELECT * FROM operator_profile WHERE id = 1")
        achievements = await conn.fetch(
            """SELECT d.slug, d.title, d.description, d.icon, d.xp_reward,
                      u.unlocked_at IS NOT NULL AS unlocked, u.unlocked_at
               FROM achievement_defs d
               LEFT JOIN achievements_unlocked u ON u.achievement_slug = d.slug
               ORDER BY d.sort_order"""
        )
        recent_xp = await conn.fetch(
            "SELECT event_type, xp_amount, description, created_at FROM xp_events ORDER BY created_at DESC LIMIT 15",
        )
        agent_feed = await conn.fetch(
            """SELECT agent_name, output_summary, status, started_at
               FROM agent_runs ORDER BY started_at DESC LIMIT 10"""
        )
        quests = await conn.fetch(
            """SELECT quest_slug, current_value, target_value, completed, xp_reward
               FROM daily_quest_progress WHERE quest_date = $1""",
            today,
        )

    xp = profile["xp_total"]
    level = level_from_xp(xp)
    next_level = level + 1
    xp_current_level = xp_for_level(level)
    xp_next_level = xp_for_level(next_level)
    progress = 0.0
    if xp_next_level > xp_current_level:
        progress = (xp - xp_current_level) / (xp_next_level - xp_current_level) * 100

    quest_map = {q["quest_slug"]: dict(q) for q in quests}
    daily = []
    for q in DAILY_QUESTS:
        p = quest_map.get(q["slug"], {})
        daily.append({
            "slug": q["slug"],
            "title": q["title"],
            "current": p.get("current_value", 0),
            "target": q["target"],
            "completed": p.get("completed", False),
            "xp_reward": q["xp"],
        })

    return {
        "profile": {
            "display_name": profile["display_name"],
            "xp_total": xp,
            "level": level,
            "title": title_for_level(level),
            "xp_progress_pct": round(min(progress, 100), 1),
            "xp_to_next_level": max(0, xp_next_level - xp),
            "streak_days": profile["streak_days"],
        },
        "achievements": [dict(a) for a in achievements],
        "daily_quests": daily,
        "recent_xp": [dict(e) for e in recent_xp],
        "agent_feed": [dict(a) for a in agent_feed],
        "achievements_unlocked": sum(1 for a in achievements if a["unlocked"]),
        "achievements_total": len(achievements),
    }
