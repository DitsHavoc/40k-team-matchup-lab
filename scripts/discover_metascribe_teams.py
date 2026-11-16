#!/usr/bin/env python3
"""Discover 2026 11th-edition Metascribe team events with over 100 players.
The queue is only candidate metadata; game rows are imported separately from player histories.
"""
import argparse,hashlib,json,re,sys,time,urllib.robotparser
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright,TimeoutError as PlaywrightTimeout
BASE="https://metascribe.gg"
QUEUE=Path("public/data/teams-discovery.json")
STATUS=Path("public/data/teams-discovery-status.json")
PATTERN=re.compile(
 r"^(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+20\d{2})\s+"
 r"(?P<name>.+?)\s+(?P<players>\d[\d,]*)\s+(?P<teams>\d[\d,]*)\s+"
 r".+?\s+(?P<version>11\.\d+\.\d+)(?:\s+.*)?$",re.I)
def main(pages,limit):
 session=requests.Session()
 session.headers["User-Agent"]="40k-team-matchup-lab/0.8 (public team-event discovery; polite rate limits)"
 robots=urllib.robotparser.RobotFileParser()
 response=session.get(BASE+"/robots.txt",timeout=30);response.raise_for_status()
 robots.parse(response.text.splitlines())
 def fetch(url):
  u=urlparse(url)
  if u.scheme!="https" or u.netloc!="metascribe.gg" or not robots.can_fetch("*",url):
   raise RuntimeError("Disallowed discovery URL "+url)
  time.sleep(1.4)
  r=session.get(url,timeout=35);r.raise_for_status()
  return BeautifulSoup(r.text,"html.parser")
 candidates={}
 issues=[]
 playwright=None
 browser=None
 try:
  for page in range(1,pages+1):
   size=("super","major")[(page-1)%2]
   page_number=(page-1)//2+1
   url=BASE+"/tournaments/"+("page/"+str(page_number)+"/" if page_number>1 else "")+"?format=team&size="+size
   try:
    soup=fetch(url)
    if not soup.find("a",href=re.compile(r"/tournaments/[a-z0-9-]+/?$")):
     if playwright is None:
      playwright=sync_playwright().start()
      browser=playwright.chromium.launch(headless=True,args=["--no-sandbox"])
     tab=browser.new_page()
     try:
      tab.goto(url,wait_until="domcontentloaded",timeout=40000)
      tab.wait_for_selector('a[href*="/tournaments/"]',timeout=25000)
      tab.wait_for_timeout(1500)
      soup=BeautifulSoup(tab.content(),"html.parser")
     finally:tab.close()
   except (requests.RequestException,RuntimeError,PlaywrightTimeout) as exc:
    issues.append("Page "+str(page)+": "+str(exc)[:160]);continue
   accepted=0
   for a in soup.find_all("a",href=re.compile(r"/tournaments/[a-z0-9-]+/?$")):
    label=a.get_text(" ",strip=True)
    match=PATTERN.match(label)
    if not match:continue
    date=datetime.strptime(match.group("date"),"%b %d %Y").date()
    if date.year!=2026:continue
    players=int(match.group("players").replace(",",""))
    teams=int(match.group("teams").replace(",",""))
    if players<=100 or teams<5 or not 2<=players/teams<=10:continue
    event_url=urljoin(BASE,a["href"])
    if urlparse(event_url).netloc!="metascribe.gg":continue
    if not event_url.endswith("/"):event_url+="/"
    candidate={"id":hashlib.sha256(event_url.encode()).hexdigest()[:12],
     "name":match.group("name").strip(),"event_date":date.isoformat(),
     "players_reported":players,"teams_reported":teams,
     "rules_version":match.group("version"),"source_url":event_url,
     "event_format":"team","status":"candidate_not_imported"}
    candidates[event_url]=candidate
    accepted+=1
   print("Team listing page",page,"new candidates",accepted,flush=True)
  # Preserve previously reviewed candidates if a listing is temporarily unavailable.
  if QUEUE.exists():
   for entry in json.loads(QUEUE.read_text(encoding="utf-8")).get("candidates",[]):
    url=entry.get("source_url")
    if entry.get("event_format")=="team" and url and url not in candidates and re.fullmatch(r"https://metascribe\.gg/tournaments/[a-z0-9-]+/",url):
     entry["id"]=hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
     candidates[url]=entry
  if not candidates:raise RuntimeError("No 100+ player team events discovered or queued")
  out=sorted(candidates.values(),key=lambda x:(x["event_date"],x["players_reported"]),reverse=True)[:limit]
  QUEUE.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
   "source":BASE+"/tournaments/?format=team&size=major","pages_checked":pages,
   "candidates":out,"issues":issues[:25],
   "note":"Event metadata candidates only; games must be independently verified from player histories."},indent=2)+"\n",encoding="utf-8")
  STATUS.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
   "status":"success" if not issues else "partial","candidate_events":len(out),"issues":issues[:25]},indent=2)+"\n",encoding="utf-8")
  print("Queued",len(out),"team events >100 players",flush=True)
 finally:
  if browser:browser.close()
  if playwright:playwright.stop()
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--pages",type=int,default=5)
 p.add_argument("--limit",type=int,default=500);a=p.parse_args()
 if not 1<=a.pages<=12 or not 1<=a.limit<=1000:raise SystemExit("Unsafe bounds")
 try:main(a.pages,a.limit)
 except Exception as exc:
  STATUS.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
   "status":"failed","reason":str(exc)[:800]},indent=2)+"\n",encoding="utf-8")
  print("Team discovery failed",exc,file=sys.stderr);sys.exit(1)
