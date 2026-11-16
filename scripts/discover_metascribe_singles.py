#!/usr/bin/env python3
"""Discover 11th-edition singles GTs/RTTs without treating standings as game data.
Checks Metascribe robots, index metadata, dates, event format and event identity.
Outputs a *candidate queue*, never published match records.
"""
import argparse,hashlib,json,re,sys,time,urllib.robotparser
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright,TimeoutError as PlaywrightTimeout
BASE="https://metascribe.gg"
def text(n):return n.get_text(" ",strip=True) if n else ""
def main(pages,limit):
 sess=requests.Session();sess.headers["User-Agent"]="40k-team-matchup-lab/0.6 (public event discovery, polite rate limits)"
 robots=urllib.robotparser.RobotFileParser()
 r=sess.get(BASE+"/robots.txt",timeout=30);r.raise_for_status()
 robots.parse(r.text.splitlines())
 def get(url):
  u=urlparse(url)
  if u.scheme!="https" or u.netloc!="metascribe.gg" or not robots.can_fetch("*",url):
   raise RuntimeError("Unapproved or disallowed discovery URL")
  time.sleep(1.3)
  response=sess.get(url,timeout=30);response.raise_for_status()
  return BeautifulSoup(response.text,"html.parser")
 discovered={}
 issues=[]
 browser_driver=None
 browser=None
 for page in range(1,pages+1):
  size=("super","major")[(page-1)%2]
  page_number=(page-1)//2+1
  url=BASE+"/tournaments/"+("page/"+str(page_number)+"/" if page_number>1 else "")+"?format=individual&size="+size
  try:
   soup=get(url)
   if not soup.find("a",href=re.compile(r"/tournaments/[a-z0-9-]+/?$")):
    if browser_driver is None:
     browser_driver=sync_playwright().start()
     browser=browser_driver.chromium.launch(headless=True,args=["--no-sandbox"])
    tab=browser.new_page()
    try:
     tab.goto(url,wait_until="domcontentloaded",timeout=35000)
     tab.wait_for_selector('a[href*="/tournaments/"]',timeout=25000)
     tab.wait_for_timeout(2000)  # Event cards are populated after the navigation shell.
     soup=BeautifulSoup(tab.content(),"html.parser")
    finally:
     tab.close()
  except (requests.RequestException,RuntimeError,PlaywrightTimeout) as e:
   issues.append("Page "+url+": "+str(e)[:180]);continue
  if not any("Explore Tournaments" in text(h) for h in soup.select("h1,h2")):issues.append("Unexpected index page "+url);break
  links=0
  reasons={"anchors":0,"context":0,"players":0,"date":0,"version_or_year":0,"small":0,"teams":0,"duplicate":0}
  anchor_samples=[]
  for anchor in soup.find_all("a",href=re.compile(r"/tournaments/[a-z0-9-]+/?$")):
   reasons["anchors"]+=1
   label=text(anchor)
   event_url=urljoin(BASE,anchor["href"])
   if urlparse(event_url).netloc!="metascribe.gg":continue
   # Metascribe renders each tournament as one clickable card:
   # "Nov 8 2026 Tournament Name 44 — City, Country 11.1.07"
   # Parse singles only: the em dash is the *team-count* placeholder.
   # Do not misread a number inside a tournament name as a team count.
   found=re.match(
    r"^(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+20\d{2})\s+(?P<name>.+)\s+(?P<players>\d[\d,]*)\s+(?P<teams>—|-)\s+.+?\s+(?P<version>11\.\d+\.\d+)(?:\s+.*)?$",
    label,re.I)
   if not found:
    reasons["context"]+=1
    if len(anchor_samples)<3:anchor_samples.append({"label":label[:300]})
    continue
   date=datetime.strptime(found.group("date"),"%b %d %Y").date()
   name=found.group("name").strip()
   players=int(found.group("players").replace(",",""))
   if date.year!=2026:reasons["version_or_year"]+=1;continue
   if players<16:reasons["small"]+=1;continue
   if found.group("teams") not in ("—","-"):reasons["teams"]+=1;continue
   version=found.group("version")
   if event_url in discovered:reasons["duplicate"]+=1;continue
   discovered[event_url]={"id":hashlib.sha256(event_url.encode("utf-8")).hexdigest()[:12],"name":name,"event_date":date.isoformat(),"players_reported":players,"rules_version":version,"source_url":event_url,"event_format":"singles","status":"candidate_not_imported"}
   links+=1
  if links==0:issues.append("No eligible events on "+url+"; diagnostics="+repr(reasons)+"; samples="+repr(anchor_samples))
  print("Page",page,"accepted",links,"diagnostics",reasons,flush=True)
 if browser is not None:browser.close()
 if browser_driver is not None:browser_driver.stop()
 # Do not report discovery success just because a previous fallback queue exists.
 freshly_discovered=len(discovered)
 if freshly_discovered<10:
  raise RuntimeError("Only "+str(freshly_discovered)+" eligible events discovered from live listings; previous fallback queue remains untouched. "+repr(issues[:5]))
 # Preserve previously validated queue items when paginating or when new results roll in.
 # Discovery is a queue; it must not silently forget unprocessed event IDs.
 prior_path=Path("public/data/singles-discovery.json")
 if prior_path.exists():
  try:
   previous=json.loads(prior_path.read_text(encoding="utf-8")).get("candidates",[])
   for event in previous:
    if event.get("source_url") and event["source_url"] not in discovered and event.get("event_format")=="singles":
     event["id"]=hashlib.sha256(event["source_url"].encode("utf-8")).hexdigest()[:12]
     discovered[event["source_url"]]=event
  except (OSError,ValueError) as exc:
   issues.append("Unable to merge previous discovery queue: "+str(exc)[:100])
 if len(discovered)<10:raise RuntimeError("Discovery produced too few candidates; "+repr(issues))
 out=sorted(discovered.values(),key=lambda e:(e["event_date"],e["players_reported"]),reverse=True)[:limit]
 dest=Path("public/data/singles-discovery.json");dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),"source":BASE+"/tournaments/?format=individual&size=major","pages_checked":pages,"candidates":out,"issues":issues[:30],"note":"Event candidates only. No score, player matchup or army list assumed until validated game-level import."},indent=2)+"\n",encoding="utf-8")
 status=Path("public/data/singles-discovery-status.json")
 status.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
 "status":"success","candidate_events":len(out),"issues":issues[:20]},indent=2)+"\n",encoding="utf-8")
 print("Discovered",len(out),"eligible event candidates")
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--pages",type=int,default=6);p.add_argument("--limit",type=int,default=120);a=p.parse_args()
 if not 1<=a.pages<=60 or not 1<=a.limit<=5000:raise SystemExit("Invalid discovery bounds")
 try:main(a.pages,a.limit)
 except Exception as e:
  error=str(e)
  print("Discovery failed:",error,file=sys.stderr)
  status=Path("public/data/singles-discovery-status.json")
  status.parent.mkdir(parents=True,exist_ok=True)
  status.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
   "status":"failed","reason":error[:1000],
   "note":"Previous verified event-game CSVs are unaffected; failed discovery must not be counted."},indent=2)+"\n",encoding="utf-8")
  sys.exit(1)
