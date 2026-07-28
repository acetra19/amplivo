"""CLI: discover ICP leads and optionally import into Amplivo.

Usage:
  python scripts/find-leads.py --max 30 --out data/discovered-leads.csv
  python scripts/find-leads.py --max 20 --import --api https://api.amplivo.net
  python scripts/find-leads.py --max 10 --webhook https://n8n.amplivo.net/webhook/new-lead
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from packages.shared.lead_finder import DEFAULT_QUERIES, SEED_URLS, LeadFinder  # noqa: E402


async def import_leads(
    leads: list,
    *,
    api: str | None,
    webhook: str | None,
) -> tuple[int, int]:
    ok = fail = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for lead in leads:
            payload = lead.to_api_payload()
            url = webhook or f"{(api or '').rstrip('/')}/leads"
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                score = data.get("score", {})
                if isinstance(score, dict):
                    score = score.get("score", "?")
                print(f"  OK  {lead.email} (score={score})")
                ok += 1
            except httpx.HTTPError as exc:
                print(f"  FAIL {lead.email}: {exc}")
                fail += 1
            await asyncio.sleep(0.3)
    return ok, fail


def write_csv(path: Path, leads: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "email", "first_name", "company", "job_title", "website",
        "industry", "employee_count", "country", "source",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for lead in leads:
            row = lead.to_api_payload()
            writer.writerow({k: row.get(k, "") for k in fields})
    print(f"Wrote {len(leads)} leads -> {path}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Discover ICP leads for Amplivo")
    parser.add_argument("--max", type=int, default=30, help="Max leads to discover")
    parser.add_argument("--out", type=Path, default=Path("data/discovered-leads.csv"))
    parser.add_argument("--import", dest="do_import", action="store_true")
    parser.add_argument("--api", default="https://api.amplivo.net")
    parser.add_argument("--webhook", help="n8n new-lead webhook (sends first email)")
    parser.add_argument("--no-search", action="store_true", help="Only use seed URLs")
    parser.add_argument("--seeds-only", action="store_true", help="Alias for --no-search")
    args = parser.parse_args()

    finder = LeadFinder(max_leads=args.max)
    queries = [] if (args.no_search or args.seeds_only) else list(DEFAULT_QUERIES)
    print(f"Discovering up to {args.max} leads (queries={len(queries)}, seeds={len(SEED_URLS)})...")
    leads = await finder.discover(queries=queries or None, seed_urls=SEED_URLS)
    print(f"Found {len(leads)} unique business emails.")

    if not leads:
        print("No leads found. Try again later or add more seed URLs.")
        return

    write_csv(args.out, leads)
    for lead in leads:
        print(f"  - {lead.email} | {lead.company} | {lead.website}")

    if args.do_import or args.webhook:
        print("\nImporting…")
        ok, fail = await import_leads(leads, api=args.api, webhook=args.webhook)
        print(f"\nDone: {ok} imported, {fail} failed.")
    else:
        print("\nDry-run only. Re-run with --import to store in Amplivo DB.")


if __name__ == "__main__":
    asyncio.run(main())
