#!/usr/bin/env python3
"""Audit published event CSVs without guessing missing tournament results."""
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CONFIG = {
 "studs-snotlings-2026": ("public/data/studs-and-snotlings-2026.csv", 26, 8, 5),
 "nrw-alpine-2026": ("public/data/nrw-alpine-cup-2026.csv", 30, 5, 5),
 "uktc-summer-itt-2026": ("public/data/uktc-summer-itt-2026.csv", 71, 5, 5),
 "uktc-autumn-itt-2026": ("public/data/uktc-autumn-itt-2026.csv", 69, 5, 5),
 "challengers-2026": ("public/data/challengers-cup-2026.csv", 68, 8, 6),
 "kent-teams-november-2026": ("public/data/kent-teams-november-2026.csv", 30, 5, 5),
 "wtc-2026": ("public/data/wtc-wh40k-2026.csv", 46, 8, 7),
 "krakow-2026": ("public/data/warhammer-open-krakow-2026.csv", 57, 5, 6),
 "gateway-2026": ("public/data/gateway-open-teams-2026.csv", 24, 8, 5),
 "scottish-open-2026": ("public/data/scottish-open-teams-2026.csv", 28, 5, 5),
 "south-pacific-8s-2026": ("public/data/south-pacific-8s-2026.csv", 18, 8, 5)
}
REQUIRED = ["event_name","event_date","source_url","round","team_a","team_b","player_a","player_b","faction_a","faction_b","disposition_a","disposition_b","score_a_20","score_b_20"]
def audit():
    report = {}
    for event,(filename,teams,players,rounds) in CONFIG.items():
        path=Path(filename)
        if not path.exists():
            report[event] = {"status":"awaiting_data","games":0,"expected_max":teams*players*rounds//2}
            continue
        with path.open(newline="",encoding="utf-8") as f:
            reader=csv.DictReader(f)
            cols=set(reader.fieldnames or [])
            missing=[x for x in REQUIRED if x not in cols]
            rows=list(reader)
        errors=[]
        if missing: errors.append("Missing columns: "+", ".join(missing))
        duplicates=set()
        rounds_count=Counter()
        dates=Counter()
        for line,r in enumerate(rows,2):
            if not all(r.get(k,"").strip() for k in REQUIRED):
                errors.append(f"Row {line}: missing required field")
                continue
            try:
                rnd=int(r["round"])
                a=int(r["score_a_20"]);b=int(r["score_b_20"])
            except ValueError:
                errors.append(f"Row {line}: invalid round/score");continue
            if not (1<=rnd<=rounds):errors.append(f"Row {line}: out-of-range round {rnd}")
            if not (0<=a<=20 and 0<=b<=20 and a+b==20):errors.append(f"Row {line}: impossible scores")
            k=(rnd,tuple(sorted([r["player_a"].casefold(),r["player_b"].casefold()])))
            if k in duplicates:errors.append(f"Row {line}: duplicate pairing")
            duplicates.add(k);rounds_count[rnd]+=1;dates[r["event_date"]]+=1
        theoretical=teams*players*rounds//2
        ratio=round(len(rows)/theoretical*100,1) if theoretical else 0
        report[event]={"status":"needs_review" if errors else "passed_structural_audit",
                       "games":len(rows),"expected_max":theoretical,"coverage_pct_of_theoretical":ratio,
                       "round_counts":dict(sorted(rounds_count.items())),
                       "date_counts":dict(sorted(dates.items())),"issues_total":len(errors),
                       "issues":errors[:12],
                       "note":"Expected maximum assumes all teams have full rosters, every round is played and no byes. Passing is a structural check, not proof of complete results."}
    return {"updated_at_utc":datetime.now(timezone.utc).isoformat(),
            "events":report}
if __name__=="__main__":
    dest=Path("public/data/coverage-audit.json")
    dest.parent.mkdir(parents=True,exist_ok=True)
    result=audit()
    dest.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k: {"games":v["games"],"status":v["status"],"issues":v.get("issues_total",0)} for k,v in result["events"].items()},indent=2))
    sys.exit(0)
