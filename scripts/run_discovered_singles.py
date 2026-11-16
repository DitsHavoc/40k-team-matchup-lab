#!/usr/bin/env python3
"""Import a bounded batch of discovered 11th edition singles events.

Candidates never count as recorded games until complete source, scoring, faction,
deduplication and coverage checks pass. Each event is independently published or
kept out of the manifest, and failed attempts retain previous validated CSVs.
"""
import argparse,csv,json,math,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
from wtc_scoring import wtc_battle_points

ROOT=Path("public/data")
QUEUE=ROOT/"singles-discovery.json"
STATUS=ROOT/"auto-import-status.json"
def validate(path,event):
 if not path.exists():return 0,"no csv created"
 with path.open(encoding="utf-8",newline="") as f:
  rd=csv.DictReader(f);rows=list(rd)
  cols=set(rd.fieldnames or [])
  required={"event_name","event_date","source_url","player_a","player_b","faction_a","faction_b",
            "disposition_a","disposition_b","raw_vp_a","raw_vp_b",
            "score_a_20","score_b_20","event_format","score_type","rules_version"}
  if not required<=cols:return len(rows),"missing required columns"
  seen=set()
  for i,row in enumerate(rows,2):
   if row["event_name"]!=event["name"] or row["source_url"]!=event["source_url"]:
    return len(rows),f"row {i}: source event mismatch"
   if row["event_format"]!="singles" or row["rules_version"]!=event["rules_version"]:
    return len(rows),f"row {i}: event format or rules mismatch"
   if row.get("score_type") not in ("published_wtc_equivalent","calculated_wtc_from_raw_vp"):
    return len(rows),f"row {i}: score provenance missing"
   if not all(row.get(k) for k in ("player_a","player_b","faction_a","faction_b")):
    return len(rows),f"row {i}: missing players or factions"
   try:
    a,b=int(row["score_a_20"]),int(row["score_b_20"])
    if not 0<=a<=20 or not 0<=b<=20 or a+b!=20:raise ValueError()
    if row["raw_vp_a"]!="" or row["raw_vp_b"]!="":
     if wtc_battle_points(row["raw_vp_a"],row["raw_vp_b"])!=(a,b):
      return len(rows),f"row {i}: WTC and VP conflict"
    elif row["score_type"]=="calculated_wtc_from_raw_vp":
     return len(rows),f"row {i}: calculated score without raw VP"
   except (ValueError,TypeError):
    return len(rows),f"row {i}: invalid VP or battle score"
   key=(row["event_date"],tuple(sorted((row["player_a"].casefold(),row["player_b"].casefold()))),
        tuple(sorted((a,b))))
   if key in seen:return len(rows),f"row {i}: duplicate game identity"
   seen.add(key)
 minimum=max(12,math.ceil(int(event["players_reported"])*.9))
 if len(rows)<minimum:return len(rows),f"incomplete sample ({len(rows)} below {minimum})"
 return len(rows),"passed_structural_audit"

def main(limit,max_players):
 if not QUEUE.exists():raise RuntimeError("Discovery queue missing")
 candidates=json.loads(QUEUE.read_text(encoding="utf-8")).get("candidates",[])
 if len(candidates)<10:raise RuntimeError("Too few discovered events to proceed")
 previous={}
 if STATUS.exists():
  try:previous=json.loads(STATUS.read_text(encoding="utf-8")).get("events",{})
  except (ValueError,OSError):previous={}
 # Never let a broken high-priority event monopolise every scheduled run.
 # Failed events are retried after a capped cooldown. New events go first.
 now=datetime.now(timezone.utc)
 to_import=[]
 for e in candidates:
  eid=e.get("id")
  if not eid or not 16<=int(e.get("players_reported",0))<=max_players:continue
  prior=previous.get(eid,{})
  dest=ROOT/("singles-auto-"+eid+".csv")
  if prior.get("import_succeeded") and dest.exists():continue
  retry_after=prior.get("retry_after_utc","")
  if retry_after:
   try:
    if datetime.fromisoformat(retry_after)>now:continue
   except ValueError:pass
  to_import.append(e)
 to_import.sort(key=lambda e:(not bool(previous.get(e["id"])),int(e["players_reported"]),e["event_date"]),reverse=True)
 reports=dict(previous)
 for event in to_import[:limit]:
  eid=event["id"];dest=ROOT/("singles-auto-"+eid+".csv")
  old=dest.read_bytes() if dest.exists() else None
  try:
   proc=subprocess.run([sys.executable,"scripts/import_metascribe_singles.py","--candidate-id",eid],
                       capture_output=True,text=True,timeout=1500)
   count,status=validate(dest,event)
   success=proc.returncode==0 and status=="passed_structural_audit"
   if not success:
    if old is None:dest.unlink(missing_ok=True)
    else:dest.write_bytes(old)
   reports[eid]={"name":event["name"],"event_date":event["event_date"],"source_url":event["source_url"],
       "import_succeeded":success,"collection_status":status if success else "failed_not_published",
       "published_records":count if success else 0,"csv_path":("public/data/"+dest.name) if success else None,
       "diagnostic":(proc.stdout+"\n"+proc.stderr).strip().splitlines()[-1][:250] if (proc.stdout or proc.stderr) else ""}
  except Exception as exc:
   if old is None:dest.unlink(missing_ok=True)
   else:dest.write_bytes(old)
   reports[eid]={"name":event["name"],"import_succeeded":False,"collection_status":"exception_not_published",
        "published_records":0,"diagnostic":str(exc)[:250],"csv_path":None}
  prior_attempts=int(previous.get(eid,{}).get("attempts",0))
  reports[eid]["attempts"]=prior_attempts+1
  reports[eid]["last_attempt_utc"]=datetime.now(timezone.utc).isoformat()
  if not reports[eid].get("import_succeeded"):
   hours=min(6*2**min(prior_attempts,4),72)
   reports[eid]["retry_after_utc"]=(datetime.now(timezone.utc)+timedelta(hours=hours)).isoformat()
  else:
   reports[eid]["retry_after_utc"]=None
  print(eid,reports[eid]["collection_status"],flush=True)
 STATUS.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
 "events":reports,"note":"Only structurally audited game-level records enter the live site; candidate standings never count as games."},indent=2)+"\n",encoding="utf-8")
 print("Validated auto-imports:",sum(v.get("published_records",0) for v in reports.values()))

if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--limit",type=int,default=2)
 parser.add_argument("--max-players",type=int,default=300);args=parser.parse_args()
 if not 1<=args.limit<=16 or not 16<=args.max_players<=2000:raise SystemExit("Unsafe collection bounds")
 try:main(args.limit,args.max_players)
 except Exception as exc:print("Auto collection failed:",exc,file=sys.stderr);sys.exit(1)
