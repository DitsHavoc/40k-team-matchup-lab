#!/usr/bin/env python3
"""Import public individual singles match histories without inventing scores or armies.
Sources: Metascribe public singles event standings and public player game histories.
All records retain raw VP and the separately published 20-point WTC equivalent.
Games without both factions, valid published WTC scores, or verifiable event identity
are excluded. No army lists or detachments are inferred.
"""
import argparse,csv,re,sys,time,urllib.robotparser
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
BASE="https://metascribe.gg"
EVENTS={
 "epsom-2026":dict(url=BASE+"/tournaments/warhammer-40000-grand-tournament-epsom-downs/",name="Warhammer 40000 Grand Tournament - Epsom Downs",date="2026-09-05",players=65,rounds=5,min_games=100,output="public/data/singles-epsom-2026.csv"),
 "newport-2026":dict(url=BASE+"/tournaments/warhammer-40000-grand-tournament-warhammer-open-newport/",name="Warhammer 40000 Grand Tournament - Warhammer Open Newport",date="2026-08-14",players=187,rounds=8,min_games=400,output="public/data/singles-newport-2026.csv"),
}
FACTIONS=["Adepta Sororitas","Adeptus Custodes","Adeptus Mechanicus","Aeldari","Astra Militarum","Black Templars","Blood Angels","Chaos Daemons","Chaos Knights","Chaos Space Marines","Dark Angels","Death Guard","Deathwatch","Drukhari","Emperor's Children","Genestealer Cults","Grey Knights","Imperial Agents","Imperial Knights","Leagues of Votann","Necrons","Orks","Space Marines","Space Wolves","T'au Empire","Thousand Sons","Tyranids","World Eaters"]
DISPS={"take":"Take and Hold","purge":"Purge the Foe","priority":"Priority Assets","recon":"Reconnaissance","disruption":"Disruption"}
COLS=["event_name","event_date","source_url","event_size_teams","round","team_a","team_b","player_a","player_b","faction_a","faction_b","detachment_a","detachment_b","disposition_a","disposition_b","score_a_20","score_b_20","raw_vp_a","raw_vp_b","mission_a","mission_b","terrain_layout","terrain_pack","deployment","attacker_defender","edition","rules_version","event_format","score_type","player_a_source_url","player_b_source_url","army_list_a_url","army_list_b_url"]
def clean(n):
 if n is None:return ""
 clone=BeautifulSoup(str(n),"html.parser")
 for t in clone.select("img,svg,script,style"):t.decompose()
 return re.sub(r"\s+"," ",clone.get_text(" ",strip=True)).strip()
def norm(s):return re.sub(r"[^a-z0-9]","",str(s or "").casefold())
def army(n):
 t=norm(clean(n))
 for fac in sorted(FACTIONS,key=len,reverse=True):
  fn=norm(fac)
  if t.startswith(fn):
   rem=t[len(fn):]
   for abbr,name in DISPS.items():
    if rem==abbr or rem.startswith(abbr) and rem[len(abbr):] in ("","disposition"):return fac,name
 # Image text sometimes uses singular Genestealer Cult
 if t.startswith("genestealercult"):
  rem=t[len("genestealercult"):]
  for abbr,name in DISPS.items():
   if rem==abbr:return "Genestealer Cults",name
 return None,None
def table_after(soup,label):
 for h in soup.find_all(re.compile(r"^h[1-6]$")):
  if label.casefold() in clean(h).casefold():return h.find_next("table")
 return None
def score(n):
 m=re.search(r"(\d+)\s*[-–]\s*(\d+)",clean(n))
 return (int(m[1]),int(m[2])) if m else None
def date(n):
 m=re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+2026",clean(n),re.I)
 return datetime.strptime(m.group(0),"%b %d %Y").date() if m else None
def run(cfg):
 session=requests.Session();session.headers["User-Agent"]="40k-team-matchup-lab/0.3 (public non-commercial event statistics; contact GitHub)"
 robots=urllib.robotparser.RobotFileParser()
 rr=session.get(BASE+"/robots.txt",timeout=30);rr.raise_for_status();robots.parse(rr.text.splitlines())
 def fetch(url):
  if not url.startswith(BASE+"/") or not robots.can_fetch("*",url):raise RuntimeError("Site disallows page "+url)
  time.sleep(1.25);r=session.get(url,timeout=35);r.raise_for_status()
  return BeautifulSoup(r.text,"html.parser")
 page=fetch(cfg["url"]);heading=page.find("h1")
 if not heading or norm(clean(heading))!=norm(cfg["name"]):raise RuntimeError("Wrong singles event page")
 if "Singles event" not in clean(page)[:600]:raise RuntimeError("Event not verified as singles")
 playersTable=table_after(page,"Player Placings")
 if not playersTable:raise RuntimeError("Player placings missing")
 players={}
 for tr in playersTable.find_all("tr"):
  cols=tr.find_all("td",recursive=False)
  if len(cols)<3:continue
  link=cols[1].find("a",href=re.compile(r"/players/"))
  if not link:continue
  url=urljoin(BASE,link["href"]);players[url]=clean(link)
 if len(players)<cfg["players"]*0.9:raise RuntimeError("Insufficient event player roster")
 print("Player profiles",len(players),flush=True)
 start=datetime.fromisoformat(cfg["date"]).date()
 games={}
 rejects={}
 def reject(reason):rejects[reason]=rejects.get(reason,0)+1
 for idx,(url,name) in enumerate(players.items(),1):
  try:
   p=fetch(url);history=table_after(p,"Game History - All Events")
   if not history:reject("no_history");continue
   for tr in history.find_all("tr"):
    cs=tr.find_all("td",recursive=False)
    if len(cs)<8:continue
    evt=cs[7];link=evt.find("a",href=re.compile(r"/tournaments/"))
    if not link or urljoin(BASE,link.get("href",""))!=cfg["url"]:continue
    if "Singles event" not in clean(evt):reject("not_singles");continue
    d=date(cs[0])
    if not d or not start<=d<=start+timedelta(days=5):reject("date_mismatch");continue
    f1,disp1=army(cs[2]);f2,disp2=army(cs[5])
    if not all((f1,disp1,f2,disp2)):reject("army_missing");continue
    equiv=score(cs[4]);vp=score(cs[3])
    if not equiv or equiv[0]+equiv[1]!=20 or any(v<0 or v>20 for v in equiv):reject("bad_20score");continue
    oppLink=cs[6].find("a",href=re.compile(r"/players/"));opp=clean(oppLink or cs[6])
    if not opp or not name or norm(opp)==norm(name):reject("bad_player");continue
    # Multiple games against the same opponent on different days are kept.
    # Same-day duplicate matches with identical scores cannot be distinguished
    # without a round; count one and record this limitation in the status.
    key=(d.isoformat(),tuple(sorted((norm(name),norm(opp)))),tuple(sorted(equiv)))
    if key in games:
     prior=games[key]
     if prior["faction_a"]!=f1 and prior["faction_b"]!=f1:reject("mirrored_faction_conflict")
     continue
    record={k:"" for k in COLS}
    record.update(event_name=cfg["name"],event_date=d.isoformat(),source_url=cfg["url"],player_a=name,player_b=opp,
      faction_a=f1,faction_b=f2,disposition_a=disp1,disposition_b=disp2,score_a_20=equiv[0],score_b_20=equiv[1],
      raw_vp_a=vp[0] if vp else "",raw_vp_b=vp[1] if vp else "",
      edition="11",event_format="singles",score_type="published_wtc_equivalent",
      player_a_source_url=url,player_b_source_url=urljoin(BASE,oppLink.get("href")) if oppLink else "")
    games[key]=record
  except Exception as e:print("Failed player",name,str(e)[:140],flush=True);reject("player_error")
  if idx%40==0:print("Scanned",idx,"/",len(players),"games",len(games),flush=True)
 print("Collected",len(games),"rejections",rejects,flush=True)
 if len(games)<cfg["min_games"]:raise RuntimeError("Below minimum singles game coverage; no CSV written")
 out=Path(cfg["output"]);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("w",newline="",encoding="utf-8") as fd:
  w=csv.DictWriter(fd,fieldnames=COLS);w.writeheader();w.writerows(sorted(games.values(),key=lambda r:(r["event_date"],r["player_a"],r["player_b"])))
 print("Wrote",out,flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--event",choices=list(EVENTS),required=True);args=p.parse_args()
 try:run(EVENTS[args.event])
 except Exception as e:print("Import failed",str(e),file=sys.stderr);sys.exit(1)
