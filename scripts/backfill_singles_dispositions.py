#!/usr/bin/env python3
"""Backfill verified Force Dispositions across all published singles CSVs.

Existing game outcomes are never changed. A missing disposition is filled only
where same-event, same-player, same-faction records agree; optionally supplement
from the original tournament's public Player Placings table.
"""
import argparse,csv,json,os,re,tempfile,time,urllib.robotparser
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,urljoin
import requests
from bs4 import BeautifulSoup
from build_warehouse import source_paths
from import_metascribe_singles import army,clean,table_after

ROOT=Path("public/data")
KNOWN={"Take and Hold","Purge the Foe","Priority Assets","Reconnaissance","Disruption"}
def norm(v):return re.sub(r"[^a-z0-9]","",str(v or "").casefold())
def who(row,side):
 event=(row.get("source_url") or "").strip() or norm(row.get("event_name"))
 profile=(row.get("player_"+side+"_source_url") or "").strip().rstrip("/").casefold()
 player=profile or norm(row.get("player_"+side))
 faction=norm(row.get("faction_"+side))
 return (event,player,faction) if all((event,player,faction)) else None
def rosters(rows,session,robots):
 evidence=defaultdict(set);status=Counter()
 for url in sorted({(r.get("source_url") or "").strip() for r in rows}):
  u=urlparse(url)
  if u.scheme!="https" or u.netloc!="metascribe.gg" or not re.fullmatch(r"/tournaments/[a-z0-9-]+/",u.path):
   status["bad_url"]+=1;continue
  if not robots.can_fetch("*",url):status["robots_blocked"]+=1;continue
  try:
   time.sleep(1.25)
   response=session.get(url,timeout=35);response.raise_for_status()
   page=BeautifulSoup(response.text,"html.parser")
   heading=page.find("h1")
   names={norm(r.get("event_name")) for r in rows if (r.get("source_url") or "").strip()==url}
   if not heading or norm(clean(heading)) not in names:
    status["event_title_mismatch"]+=1;continue
   table=table_after(page,"Player Placings")
   if not table:status["no_placings_table"]+=1;continue
   for tr in table.find_all("tr"):
    cells=tr.find_all("td",recursive=False)
    if len(cells)<3:continue
    anchor=cells[1].find("a",href=re.compile(r"/players/"))
    if not anchor:continue
    profile=urljoin(url,anchor.get("href","")).rstrip("/").casefold()
    if urlparse(profile).netloc!="metascribe.gg":continue
    for cell in cells[2:]:
     faction,disp=army(cell)
     if faction:
      if disp in KNOWN:evidence[(url,profile,norm(faction))].add(disp)
      break
   status["rosters_scanned"]+=1
  except (requests.RequestException,ValueError):
   status["roster_fetch_failed"]+=1
 return evidence,status
def enrich(rows,external=None):
 evidence=defaultdict(set);stats=Counter()
 for row in rows:
  for side in ("a","b"):
   value=(row.get("disposition_"+side) or "").strip()
   if value in KNOWN:
    key=who(row,side)
    if key:evidence[key].add(value)
 for row in rows:
  for side in ("a","b"):
   field="disposition_"+side
   if row.get(field):
    stats["already_recorded"]+=1;continue
   stats["missing_before"]+=1
   key=who(row,side)
   if not key:stats["identity_missing"]+=1;continue
   own=evidence.get(key,set())
   other=(external or {}).get(key,set())
   if own and other and own!=other:
    stats["source_conflict"]+=1;continue
   choices=own|other
   if len(choices)==1:
    row[field]=next(iter(choices));stats["filled"]+=1
   elif len(choices)>1:stats["disposition_conflict"]+=1
   else:stats["unverified"]+=1
 stats["missing_after"]=stats["missing_before"]-stats["filled"]
 return stats
def write_csv(path,fields,rows):
 fd,temp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
 try:
  with os.fdopen(fd,"w",newline="",encoding="utf-8") as handle:
   writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.unlink(temp)
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--rosters",action="store_true")
 parser.add_argument("--dry-run",action="store_true")
 a=parser.parse_args()
 paths=[p for p in source_paths() if p.is_file() and p.name.startswith("singles-")]
 if not paths:raise RuntimeError("No source singles CSV files found")
 session=None;robots=None
 if a.rosters:
  session=requests.Session()
  session.headers["User-Agent"]="40k-team-matchup-lab/0.7 (verified disposition correction)"
  r=session.get("https://metascribe.gg/robots.txt",timeout=30);r.raise_for_status()
  robots=urllib.robotparser.RobotFileParser();robots.parse(r.text.splitlines())
 totals=Counter();files=[]
 for path in sorted(paths):
  with path.open(newline="",encoding="utf-8-sig") as handle:
   reader=csv.DictReader(handle);fields=reader.fieldnames;rows=list(reader)
  if not fields or not {"disposition_a","disposition_b","event_format"}<=set(fields):
   files.append({"file":str(path),"status":"unsupported_columns"});continue
  if any(row.get("event_format")!="singles" for row in rows):
   raise RuntimeError("Mixed singles/team CSV: "+str(path))
  before=[{k:v for k,v in row.items() if not k.startswith("disposition_")} for row in rows]
  roster_data,diagnostics=rosters(rows,session,robots) if session else ({},Counter())
  stats=enrich(rows,roster_data)
  for row,original in zip(rows,before):
   if {k:v for k,v in row.items() if not k.startswith("disposition_")}!=original:
    raise RuntimeError("Non-disposition columns unexpectedly changed: "+str(path))
  totals.update(stats);totals.update(diagnostics)
  files.append({"file":str(path),"games":len(rows),**dict(stats),**dict(diagnostics)})
  if stats["filled"] and not a.dry_run:write_csv(path,fields,rows)
 report={"updated_at_utc":datetime.now(timezone.utc).isoformat(),
         "dry_run":a.dry_run,"roster_lookup":a.rosters,"files_processed":len(paths),
         "summary":dict(totals),"files":files,
         "note":"Only verified missing singles dispositions filled. Event/player/faction constrained. Matches, scores and teams not changed."}
 if not a.dry_run:
  (ROOT/"singles-disposition-backfill.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(report["summary"],indent=2))
if __name__=="__main__":main()
