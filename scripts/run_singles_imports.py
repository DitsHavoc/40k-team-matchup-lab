#!/usr/bin/env python3
"""Validate and publish separately sourced singles results."""
import csv,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
EVENTS={
 "epsom-2026":("public/data/singles-epsom-2026.csv",100),
 "newport-2026":("public/data/singles-newport-2026.csv",400),
}
def validate(path,min_games):
 if not path.exists():return 0,"missing"
 with path.open(encoding="utf-8",newline="") as f:
  reader=csv.DictReader(f);fields=set(reader.fieldnames or []);rows=list(reader)
 required={"event_name","event_date","player_a","player_b","faction_a","faction_b","disposition_a","disposition_b","score_a_20","score_b_20","event_format","source_url"}
 if not required<=fields:return len(rows),"missing required columns"
 seen=set()
 for n,r in enumerate(rows,2):
  if any(not r[k] for k in required):return len(rows),f"line {n} missing required field"
  if r["event_format"]!="singles" or r.get("score_type")!="published_wtc_equivalent":return len(rows),f"line {n} wrong score provenance"
  try:a=int(r["score_a_20"]);b=int(r["score_b_20"])
  except ValueError:return len(rows),f"line {n} invalid score"
  if not 0<=a<=20 or not 0<=b<=20 or a+b!=20:return len(rows),f"line {n} non-20 score"
  k=(r["event_date"],tuple(sorted([r["player_a"].casefold(),r["player_b"].casefold()])),tuple(sorted([a,b])))
  if k in seen:return len(rows),f"line {n} duplicate pair and score"
  seen.add(k)
 if len(rows)<min_games:return len(rows),"below minimum game count"
 return len(rows),"passed_structural_audit"
results={}
for event,(filename,minimum) in EVENTS.items():
 path=Path(filename)
 try:
  proc=subprocess.run([sys.executable,"scripts/import_metascribe_singles.py","--event",event],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=3000)
  output=proc.stdout.strip()
  count,status=validate(path,minimum)
  results[event]={"collection_status":status if proc.returncode==0 else "failed_or_previous_file_preserved","import_succeeded":proc.returncode==0 and status=="passed_structural_audit","published_records":count,"csv_path":filename if count else None,"diagnostic":output.splitlines()[-1][:300] if output else ""}
 except Exception as e:results[event]={"collection_status":"failed","import_succeeded":False,"published_records":0,"diagnostic":str(e)}
dest=Path("public/data/singles-import-status.json");dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),"events":results,"note":"Singles results are explicitly labelled, retain native raw VP, and have separately published 20-point equivalents. Failed imports preserve previously published datasets."},indent=2)+"\n",encoding="utf-8")
print(json.dumps(results,indent=2),flush=True)
sys.exit(0 if all(v["import_succeeded"] for v in results.values()) else 1)
