#!/usr/bin/env python3
"""Audit cross-source game identity without silently discarding legitimate rematches.
Identical player/score/date in different event IDs is a review candidate, NOT
automatic evidence of duplication. The imported 20-0 score and raw VP remain untouched.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import csv,json,re,sys
DATA=Path("public/data")
OUT=DATA/"cross-source-audit.json"
def norm(value):
 return re.sub(r"[^a-z0-9]","",str(value or "").casefold())
def canonical(row):
 a,b=norm(row["player_a"]),norm(row["player_b"])
 if not a or not b or a==b:return None
 try: sa=int(row["score_a_20"]);sb=int(row["score_b_20"])
 except (TypeError,ValueError):return None
 return (a,b,sa,sb) if a<b else (b,a,sb,sa)
def run():
 all_rows=[];skipped=[];files=[]
 for path in sorted(DATA.glob("*.csv")):
  if path.name.startswith("warehouse-"):continue  # Published shards repeat source games; never treat them as new evidence.
  with path.open(encoding="utf-8-sig",newline="") as f:
   reader=csv.DictReader(f)
   required={"event_name","event_date","player_a","player_b","score_a_20","score_b_20"}
   if not required<=set(reader.fieldnames or []):continue
   count=0
   for line,row in enumerate(reader,2):
    identity=canonical(row)
    if not identity:
     skipped.append({"file":path.name,"line":line,"issue":"incomplete identity"});continue
    date=row.get("event_date","").strip()
    event=norm(row["event_name"])
    source=row.get("source_url","").strip().rstrip("/")
    all_rows.append(dict(file=path.name,line=line,identity=identity,date=date,event=event,source=source,round=row.get("round","").strip(),format=row.get("event_format","team") or "team"))
    count+=1
   files.append({"file":path.name,"rows":count})
 by_event=defaultdict(list);by_date=defaultdict(list)
 for row in all_rows:
  by_event[(row["event"],row["date"],row["identity"],row["round"])].append(row)
  by_date[(row["date"],row["identity"])].append(row)
 duplicates=[]
 for group in by_event.values():
  if len(group)>1 and len({x["file"] for x in group})>1:
   duplicates.append({"kind":"same_named_event_same_game", "records":[{"file":x["file"],"line":x["line"]} for x in group]})
 candidates=[]
 for group in by_date.values():
  if len({x["event"] for x in group})>1:
   candidates.append({"kind":"different_event_labels_same_date_players_score","records":[{"file":x["file"],"line":x["line"],"event":x["event"]} for x in group]})
 report={"updated_at_utc":datetime.now(timezone.utc).isoformat(),
  "published_files_audited":files,"total_rows_checked":len(all_rows),
  "cross_file_same_event_duplicates":duplicates[:100],
  "review_cross_event_candidates":candidates[:100],
  "skipped_identity_rows":skipped[:50],
  "note":"Audits duplicate candidate identity and preserves historical records. A flagged candidate is not automatically deleted; matches must be source-verified."}
 OUT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"game_rows":len(all_rows),"cross_file_duplicates":len(duplicates),"ambiguous_candidates":len(candidates),"skipped":len(skipped)},indent=2))
 return 0
if __name__=="__main__":sys.exit(run())
