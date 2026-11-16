#!/usr/bin/env python3
"""Run approved Metascribe event imports and publish transparent per-event status.

Existing CSV files are left untouched when a new collection fails.
"""
import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EVENTS = {
    "studs-snotlings-2026": "public/data/studs-and-snotlings-2026.csv",
    "nrw-alpine-2026": "public/data/nrw-alpine-cup-2026.csv",
    "wtc-2026": "public/data/wtc-wh40k-2026.csv",
    "krakow-2026": "public/data/warhammer-open-krakow-2026.csv",
    "gateway-2026": "public/data/gateway-open-teams-2026.csv",
    "scottish-open-2026": "public/data/scottish-open-teams-2026.csv",
    "south-pacific-8s-2026": "public/data/south-pacific-8s-2026.csv",
    "uktc-summer-itt-2026": "public/data/uktc-summer-itt-2026.csv",
    "uktc-autumn-itt-2026": "public/data/uktc-autumn-itt-2026.csv",
    "challengers-2026": "public/data/challengers-cup-2026.csv",
    "kent-teams-november-2026": "public/data/kent-teams-november-2026.csv",
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--event", choices=[*EVENTS, "all"], default="all")
    args = p.parse_args()
    selected = EVENTS if args.event == "all" else {args.event: EVENTS[args.event]}
    results = {}
    pending = {"uktc-autumn-itt-2026"}
    for event, filename in selected.items():
        path = Path(filename)
        proc = subprocess.run(
            [sys.executable, "scripts/import_metascribe_event.py", "--event", event],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900
        )
        print(f"--- {event} (exit {proc.returncode}) ---", flush=True)
        print(proc.stdout[-12000:], flush=True)
        count = 0
        if path.exists():
            with path.open(encoding="utf-8", newline="") as fp:
                count = sum(1 for _ in csv.DictReader(fp))
        results[event] = {
            "import_succeeded": proc.returncode == 0,
            "collection_status": "ready" if proc.returncode == 0 else ("awaiting_2026_source" if event in pending and count == 0 else "failed"),
            "published_records": count,
            "csv_path": filename if count else None,
            "diagnostic": (proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "No output")[:300]
        }
    status = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": "An import failure preserves any existing dataset. Reported counts describe published CSV rows, not event completeness.",
        "events": results
    }
    dest = Path("public/data/import-status.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if all(item["import_succeeded"] or event in pending and item["collection_status"] == "awaiting_2026_source" for event, item in results.items()) else 1

if __name__ == "__main__":
    sys.exit(main())
