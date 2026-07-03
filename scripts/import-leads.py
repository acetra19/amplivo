"""Import leads from CSV – no Apollo needed in lean phase.

Usage:
    python scripts/import-leads.py leads.csv
    python scripts/import-leads.py leads.csv --webhook http://localhost:5678/webhook/new-lead
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def parse_int(value: str | None) -> int | None:
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def import_csv(path: Path, webhook: str | None, api_base: str) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        print("CSV is empty.")
        return

    ok, fail = 0, 0
    with httpx.Client(timeout=60) as client:
        for row in rows:
            email = (row.get("email") or "").strip()
            if not email:
                fail += 1
                continue

            payload = {
                "email": email,
                "first_name": (row.get("first_name") or "").strip() or None,
                "last_name": (row.get("last_name") or "").strip() or None,
                "company": (row.get("company") or "").strip() or None,
                "job_title": (row.get("job_title") or "").strip() or None,
                "industry": (row.get("industry") or "marketing_agency").strip(),
                "employee_count": parse_int(row.get("employee_count")),
                "country": (row.get("country") or "DE").strip(),
                "source": (row.get("source") or "csv").strip(),
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            url = webhook or f"{api_base.rstrip('/')}/leads"
            try:
                resp = client.post(url, json=payload if webhook else payload)
                resp.raise_for_status()
                data = resp.json()
                score = data.get("score", {}).get("score", "?")
                print(f"  OK  {email} (score={score})")
                ok += 1
            except httpx.HTTPError as exc:
                print(f"  FAIL {email}: {exc}")
                fail += 1

    print(f"\nDone: {ok} imported, {fail} failed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import leads from CSV")
    parser.add_argument("csv_file", type=Path, help="Path to CSV file")
    parser.add_argument(
        "--webhook",
        help="n8n new-lead webhook URL (triggers scoring + outbound send)",
    )
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    if not args.csv_file.exists():
        print(f"File not found: {args.csv_file}")
        sys.exit(1)

    print(f"Importing {args.csv_file} ({'webhook' if args.webhook else 'api only'})...")
    import_csv(args.csv_file, args.webhook, args.api)


if __name__ == "__main__":
    main()
