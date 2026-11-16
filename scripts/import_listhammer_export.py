#!/usr/bin/env python3
"""Safely add authorised Listhammer *game-level* CSV exports.

Never interpret standings, aggregate win rates or X-0 army lists as individual
matches. Requires documented permission for bulk redistribution. Existing
tournaments are reconciled by build_warehouse.py at event level.
"""
import argparse,csv,hashlib,json,re,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from build_warehouse import FIELDS,valid,identity
ROOT=Path("public/data")
STATUS=ROOT/"listhammer-import-status.json"
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--file",required=True,help="Authorised game-level CSV export")
 p.add_argument("--event-url",required=True,help="Listhammer event details URL")
 p.add_argument("--permission-reference",required=True,help="Permission record / licence reference")
 args=p.parse_args()
 url=urlparse(args.event_url)
 if url.scheme!="https" or url.netloc not in ("listhammer.info","www.listhammer.info") or not re.fullmatch(r"/events/[a-f0-9]{18}",url.path):
  p.error("Expected verified https://listhammer.info/events/{18-character-id} URL")
 if not args.permission_reference.strip() or len(args.permission_reference.strip())<8:
  p.error("Specific licence/permission reference required for bulk redistribution")
 source=Path(args.file)
 if not source.is_file():p.error("Game-level CSV file missing")
 with source.open(encoding="utf-8-sig",newline="") as f:
  reader=csv.DictReader(f)
  if not set(("event_name","event_date","player_a","player_b","faction_a","faction_b","score_a_20","score_b_20"))<=set(reader.fieldnames or []):
   p.error("This appears to be standings or an incomplete export, not game-level results")
  rows=list(reader)
 if not rows:p.error("No individual games found")
 events={str(r.get("event_name","")).strip() for r in rows}
 if len(events)!=1:p.error("One export must contain precisely one named tournament")
 unique=set()
 for i,r in enumerate(rows,2):
  r["source_url"]=args.event_url
  r["event_format"]="singles"
  r["edition"]=r.get("edition") or "11"
  if not valid(r):p.error(f"Game row {i} failed identity/edition/score validation")
  key=identity(r)
  if key in unique:p.error(f"Duplicate game inside supplied export at row {i}")
  unique.add(key)
 eid=hashlib.sha256(args.event_url.encode()).hexdigest()[:12]
 dest=ROOT/("listhammer-games-"+eid+".csv")
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open("w",encoding="utf-8",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
  writer.writeheader();writer.writerows(rows)
 status=json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {"events":{}}
 status["updated_at_utc"]=datetime.now(timezone.utc).isoformat()
 status["events"][eid]={"event_name":next(iter(events)),"source_url":args.event_url,"published_records":len(rows),
   "csv_path":"public/data/"+dest.name,"import_succeeded":True,
   "permission_reference":args.permission_reference,
   "note":"Warehouse suppresses duplicate events before estimating totals"}
 STATUS.write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"event_name":next(iter(events)),"validated_game_rows":len(rows),
   "status":"staged_for_warehouse_event_deduplication"},indent=2))
if __name__=="__main__":main()
