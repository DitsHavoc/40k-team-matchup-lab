#!/usr/bin/env python3
"""Validate and publish separately sourced singles results."""
import argparse,csv,json,subprocess,sys
from wtc_scoring import wtc_battle_points
from pathlib import Path
from datetime import datetime,timezone
EVENTS={
 # Fast useful coverage first; slow majors must not block small verified events.
 "october-rtt-2026":("public/data/singles-october-rtt-2026.csv",18),
 "kent-major-2026":("public/data/singles-kent-major-2026.csv",110),
 "ratcon-2026":("public/data/singles-ratcon-2026.csv",130),
 "epsom-2026":("public/data/singles-epsom-2026.csv",100),
 "newport-2026":("public/data/singles-newport-2026.csv",400),
 "lgt-2026":("public/data/singles-lgt-2026.csv",1700),
 "lvo-2026":("public/data/singles-lvo-2026.csv",1000),
}

def validate(path,min_games):
 if not path.exists():return 0,"missing"
 with path.open(encoding="utf-8",newline="") as f:
  reader=csv.DictReader(f);fields=set(reader.fieldnames or []);rows=list(reader)
 required={"event_name","event_date","player_a","player_b","faction_a","faction_b","score_a_20","score_b_20","event_format","source_url"}
 if not required<=fields or not {"disposition_a","disposition_b"}<=fields:return len(rows),"missing required columns"
 seen=set()
 for n,r in enumerate(rows,2):
  if any(not r[k] for k in required):return len(rows),f"line {n} missing required field"
  if r["event_format"]!="singles" or r.get("score_type") not in ("published_wtc_equivalent","calculated_wtc_from_raw_vp"):return len(rows),f"line {n} wrong score provenance"
  try:a=int(r["score_a_20"]);b=int(r["score_b_20"])
  except ValueError:return len(rows),f"line {n} invalid score"
  if not 0<=a<=20 or not 0<=b<=20 or a+b!=20:return len(rows),f"line {n} non-20 score"
  raw_a,raw_b=r.get("raw_vp_a",""),r.get("raw_vp_b","")
  if raw_a!="" or raw_b!="":
   if raw_a=="" or raw_b=="":return len(rows),f"line {n} incomplete raw VP pair"
   try:converted=wtc_battle_points(raw_a,raw_b)
   except (TypeError,ValueError):return len(rows),f"line {n} invalid raw VP"
   if (a,b)!=converted:return len(rows),f"line {n} published/calculated WTC mismatch"
  elif r.get("score_type")=="calculated_wtc_from_raw_vp":return len(rows),f"line {n} calculated score missing raw VP"
  k=(r["event_date"],tuple(sorted([r["player_a"].casefold(),r["player_b"].casefold()])),tuple(sorted([a,b])))
  if k in seen:return len(rows),f"line {n} duplicate pair and score"
  seen.add(k)
 if len(rows)<min_games:return len(rows),"below minimum game count"
 return len(rows),"passed_structural_audit"
def save_status(results):
 dest=Path("public/data/singles-import-status.json")
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
 "events":results,"note":"Published files only: previous verified data retained after collection failure. Raw VP and WTC equivalents are separately recorded."},indent=2)+"\n",encoding="utf-8")

parser=argparse.ArgumentParser()
parser.add_argument("--event",choices=list(EVENTS),help="Import only one event to avoid blocking on very large tournaments")
parser.add_argument("--fast",action="store_true",help="Only smaller events; run majors separately")
args=parser.parse_args()
results={}
try:
 current=Path("public/data/singles-import-status.json")
 if current.exists():
  results=json.loads(current.read_text(encoding="utf-8")).get("events",{})
except (ValueError,OSError):results={}
targets={args.event:EVENTS[args.event]} if args.event else ({k:v for k,v in EVENTS.items() if k not in ("lgt-2026","lvo-2026")} if args.fast else EVENTS)
for event,(filename,minimum) in targets.items():
 path=Path(filename)
 previous_bytes=path.read_bytes() if path.exists() else None
 try:
  proc=subprocess.run([sys.executable,"scripts/import_metascribe_singles.py","--event",event],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=3000)
  output=proc.stdout.strip()
  count,status=validate(path,minimum)
  succeeded=proc.returncode==0 and status=="passed_structural_audit"
  if not succeeded:
   if previous_bytes is None:
    path.unlink(missing_ok=True)
   else:
    path.write_bytes(previous_bytes)
   count=validate(path,minimum)[0] if path.exists() else 0
  results[event]={"collection_status":status if succeeded else "failed_or_previous_file_preserved","import_succeeded":succeeded,"published_records":count,"csv_path":filename if count else None,"diagnostic":output.splitlines()[-1][:300] if output else ""}
 except Exception as e:results[event]={"collection_status":"failed","import_succeeded":False,"published_records":0,"diagnostic":str(e)}
save_status(results)
print(json.dumps(results,indent=2),flush=True)
sys.exit(0 if all(results[e]["import_succeeded"] for e in targets) else 1)
