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
 for page in range(1,pages+1):
  url=BASE+"/tournaments/"+("page/"+str(page)+"/" if page>1 else "")
  try:soup=get(url)
  except (requests.RequestException,RuntimeError) as e:issues.append(str(e));continue
  if not any("Explore Tournaments" in text(h) for h in soup.select("h1,h2")):issues.append("Unexpected index page "+url);break
  links=0
  reasons={"rows":0,"columns":0,"link":0,"players":0,"date":0,"version_or_year":0,"small":0,"teams":0,"duplicate":0}
  sample=[]
  for row in soup.select("table tr"):
   reasons["rows"]+=1
   td=row.find_all("td",recursive=False)
   if len(td)<6:reasons["columns"]+=1;continue
   anchor=td[1].find("a",href=re.compile(r"/tournaments/"))
   if not anchor:reasons["link"]+=1;continue
   name=text(anchor);event_url=urljoin(BASE,anchor.get("href",""))
   count=re.search(r"\d+",text(td[2]).replace(",",""))
   if not count:reasons["players"]+=1;continue
   players=int(count.group())
   date_match=re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{1,2}\\s+20\\d{2}",text(td[0]),re.I)
   if not date_match:reasons["date"]+=1;continue
   date=datetime.strptime(date_match.group(0),"%b %d %Y").date()
   version=re.search(r"\\b11\\.\\d+\\.\\d+\\b",text(td[5]))
   if not version or date.year!=2026:reasons["version_or_year"]+=1;continue
   if players<16:reasons["small"]+=1;continue
   # A numeric team count means this is a team event, not singles.
   team_col=text(td[3]).strip()
   if team_col not in ("","—","-"):reasons["teams"]+=1;continue
   if event_url in discovered:reasons["duplicate"]+=1;continue
   discovered[event_url]={"id":hashlib.sha256(event_url.encode("utf-8")).hexdigest()[:12],"name":name,"event_date":date.isoformat(),"players_reported":players,"rules_version":version.group(),"source_url":event_url,"event_format":"singles","status":"candidate_not_imported"}
   links+=1
  if links==0:issues.append("No eligible events on "+url+"; diagnostics="+repr(reasons))
  print("Page",page,"accepted",links,"diagnostics",reasons,flush=True)
 # Do not write empty or unexpected results; preserve previous queue.
 if len(discovered)<10:raise RuntimeError("Discovery produced too few candidates; "+repr(issues))
 out=sorted(discovered.values(),key=lambda e:(e["event_date"],e["players_reported"]),reverse=True)[:limit]
 dest=Path("public/data/singles-discovery.json");dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),"source":BASE+"/tournaments/","pages_checked":pages,"candidates":out,"issues":issues[:30],"note":"Event candidates only. No score, player matchup or army list assumed until validated game-level import."},indent=2)+"\n",encoding="utf-8")
 status=Path("public/data/singles-discovery-status.json")
 status.write_text(json.dumps({"updated_at_utc":datetime.now(timezone.utc).isoformat(),
 "status":"success","candidate_events":len(out),"issues":issues[:20]},indent=2)+"\n",encoding="utf-8")
 print("Discovered",len(out),"eligible event candidates")
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--pages",type=int,default=6);p.add_argument("--limit",type=int,default=120);a=p.parse_args()
 if not 1<=a.pages<=30 or not 1<=a.limit<=500:raise SystemExit("Invalid discovery bounds")
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
