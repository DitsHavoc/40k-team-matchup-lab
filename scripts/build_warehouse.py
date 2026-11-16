#!/usr/bin/env python3
"""Build static, deduplicated game shards from published verified tournament CSVs.

The warehouse is a delivery format, not extra matches. Bad rows are excluded,
unavailable/failed auto-imports are not silently counted. Retains source URLs.
"""
import csv,json,re,hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone

ROOT=Path("public/data")
HTML=Path("public/index.html")
SHARD_SIZE=10000
REQUIRED=("event_name","event_date","player_a","player_b","faction_a","faction_b","score_a_20","score_b_20")
FIELDS=["event_name","event_date","source_url","event_size_teams","round","team_a","team_b","player_a","player_b","faction_a","faction_b","detachment_a","detachment_b","disposition_a","disposition_b","score_a_20","score_b_20","raw_vp_a","raw_vp_b","mission_a","mission_b","terrain_layout","terrain_pack","deployment","attacker_defender","edition","rules_version","event_format","score_type","player_a_source_url","player_b_source_url","army_list_a_url","army_list_b_url"]
def source_paths():
 html=HTML.read_text(encoding="utf-8")
 m=re.search(r"let sources=\[([^\]]+)\]",html)
 if not m:raise RuntimeError("Baseline source list missing from website")
 paths=[ROOT/x for x in re.findall(r"'data/([^']+\.csv)'",m.group(1))]
 status=ROOT/"auto-import-status.json"
 if status.exists():
  for v in json.loads(status.read_text(encoding="utf-8")).get("events",{}).values():
   path=v.get("csv_path","")
   if v.get("import_succeeded") and re.fullmatch(r"public/data/singles-auto-[a-f0-9]{12}\.csv",path):
    paths.append(Path(path))
 return list(dict.fromkeys(paths))
def identity(r):
 names=tuple(sorted((r["player_a"].strip().casefold(),r["player_b"].strip().casefold())))
 fmt=r.get("event_format") or "team"
 scores=tuple(sorted((int(r["score_a_20"]),int(r["score_b_20"])))) if fmt=="singles" else ()
 return (r["event_name"].strip().casefold(),r["event_date"],str(r.get("round","")).strip().casefold(),names,scores)
def valid(r):
 if not all(r.get(k,"").strip() for k in REQUIRED):return False
 if r.get("edition","11") not in ("11","11th"):return False
 try:
  a,b=int(r["score_a_20"]),int(r["score_b_20"])
  if not(0<=a<=20 and 0<=b<=20 and a+b==20):return False
 except (TypeError,ValueError):return False
 if (r.get("event_format") or "team")=="team":
  if not r.get("disposition_a") or not r.get("disposition_b"):return False
  try:
   if not 1<=int(r.get("round",""))<=20:return False
  except (ValueError,TypeError):return False
 return True
def main():
 rows=[];seen=set();audit=Counter();files=[]
 for path in source_paths():
  if not path.exists():audit["source_missing"]+=1;continue
  n=0
  with path.open(encoding="utf-8-sig",newline="") as f:
   reader=csv.DictReader(f)
   for r in reader:
    audit["source_rows"]+=1
    if not valid(r):audit["invalid_rows"]+=1;continue
    k=identity(r)
    if k in seen:audit["duplicate_rows"]+=1;continue
    seen.add(k);rows.append({field:r.get(field,"") or "" for field in FIELDS});n+=1
  files.append({"path":str(path),"accepted_unique":n})
 rows.sort(key=lambda r:(r["event_date"],r["event_name"],r["player_a"],r["player_b"]))
 if len(rows)<1000:raise RuntimeError("Unreasonably small warehouse; preserving existing published version")
 shards=[]
 for i,start in enumerate(range(0,len(rows),SHARD_SIZE),1):
  path=ROOT/f"warehouse-{i:04d}.csv"
  with path.open("w",encoding="utf-8",newline="") as f:
   wr=csv.DictWriter(f,fieldnames=FIELDS);wr.writeheader();wr.writerows(rows[start:start+SHARD_SIZE])
  shards.append({"path":f"data/{path.name}","records":len(rows[start:start+SHARD_SIZE]),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
 for old in ROOT.glob("warehouse-*.csv"):
  if old.name not in {Path(x["path"]).name for x in shards}:old.unlink()
 manifest={"schema_version":1,"updated_at_utc":datetime.now(timezone.utc).isoformat(),"total_unique_games":len(rows),"total_source_rows":audit["source_rows"],"deduplicated":audit["duplicate_rows"],"invalid_rows":audit["invalid_rows"],"missing_source_files":audit["source_missing"],"shard_size":SHARD_SIZE,"shards":shards,"sources":files,"note":"Verified game-level CSVs merged for efficient delivery; shards are not additional games. Data includes team and singles matches."}
 (ROOT/"warehouse-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:manifest[k] for k in ("total_unique_games","total_source_rows","deduplicated","invalid_rows","missing_source_files","shard_size")},indent=2))
if __name__=="__main__":main()
