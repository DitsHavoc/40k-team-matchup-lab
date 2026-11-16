#!/usr/bin/env python3
"""Short preflight of major singles event HTML and player history parsing.

This is diagnostic only: it never invents or publishes individual games.
"""
import argparse,json,re,sys,time,urllib.robotparser
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from import_metascribe_singles import EVENTS,table_after,clean,norm,army,score,date
from wtc_scoring import wtc_battle_points
BASE="https://metascribe.gg"
def main(event_keys,samples):
 sess=requests.Session();sess.headers["User-Agent"]="40k-team-matchup-lab/0.6 (major event import diagnostic)"
 robots=urllib.robotparser.RobotFileParser()
 response=sess.get(BASE+"/robots.txt",timeout=20);response.raise_for_status()
 robots.parse(response.text.splitlines())
 def fetch(url):
  if not robots.can_fetch("*",url):raise RuntimeError("robots.txt disallows "+url)
  time.sleep(1.25)
  result=sess.get(url,timeout=35);result.raise_for_status()
  return BeautifulSoup(result.text,"html.parser")
 results={}
 for event_key in event_keys:
  cfg=EVENTS[event_key].copy();info={"event":event_key,"source_url":cfg["url"]}
  try:
   page=fetch(cfg["url"])
   h=page.find("h1")
   info["heading_ok"]=bool(h and norm(clean(h))==norm(cfg["name"]))
   info["singles_identified"]="Singles event" in clean(page)[:600]
   v=re.search(r"\bMeta\s*:\s*(\d+(?:\.\d+){1,3})\b",clean(page),re.I)
   info["meta_version"]=v.group(1) if v else None
   table=table_after(page,"Player Placings")
   urls=[]
   if table:
    for tr in table.find_all("tr"):
     td=tr.find_all("td",recursive=False)
     if len(td)>1:
      link=td[1].find("a",href=re.compile("/players/"))
      if link:urls.append(urljoin(BASE,link["href"]))
   info["players_found"]=len(set(urls));info["players_expected"]=cfg["players"]
   if not info["heading_ok"] or not info["singles_identified"] or info["meta_version"]!=cfg["rules_version"] or len(set(urls))<cfg["players"]*.9:
    raise RuntimeError("Event identity/edition/roster validation failed")
   checked=0;games=0;issues=[]
   for url in urls[:samples]:
    try:
     p=fetch(url);history=table_after(p,"Game History - All Events")
     if not history:issues.append("missing_history");continue
     checked+=1
     for tr in history.find_all("tr"):
      cs=tr.find_all("td",recursive=False)
      if len(cs)<8:continue
      link=cs[7].find("a",href=re.compile("/tournaments/"))
      if not link or urljoin(BASE,link.get("href",""))!=cfg["url"]:continue
      factions=[army(cs[2])[0],army(cs[5])[0]]
      equiv=score(cs[4]);vp=score(cs[3])
      if all(factions) and equiv and sum(equiv)==20 and (not vp or wtc_battle_points(*vp)==equiv):games+=1
      else:issues.append("invalid_sampled_game")
    except Exception as e:issues.append(str(e)[:160])
   info.update(profiles_checked=checked,valid_matching_game_rows=games,sample_issues=issues[:15])
   info["status"]="passed" if checked>=min(3,samples) and games>=3 else "failed_sample"
  except Exception as e:info["status"]="failed";info["error"]=str(e)[:250]
  results[event_key]=info
 out=Path("public/data/major-import-preflight.json")
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),"events":results,"note":"Preflight checks are diagnostics only; do not increase game count."},indent=2)+"\n",encoding="utf-8")
 print(json.dumps(results,indent=2),flush=True)
 if not all(v["status"]=="passed" for v in results.values()):sys.exit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--samples",type=int,default=5);args=p.parse_args()
 if not 2<=args.samples<=15:sys.exit("Use 2-15 samples")
 main(["lgt-2026","lvo-2026"],args.samples)
