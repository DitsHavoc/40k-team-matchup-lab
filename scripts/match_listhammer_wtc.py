#!/usr/bin/env python3
"""Verified, narrowly scoped Listhammer WTC roster cross-reference.

Only associates a profile with a *WTC 2026* participant when name and faction
both agree with the published Metascribe WTC game CSV and the Listhammer WTC
country roster. Does NOT claim a profile is the game-specific army list.
Never import match results from Listhammer into match score data.
"""
import csv,json,re,sys,time,unicodedata,urllib.robotparser
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

ROOT="https://listhammer.info"
ROOT_URL=ROOT+"/wtc?list=8IJXMRQEoDBW"
DATA=Path("public/data/wtc-wh40k-2026.csv")
OUTPUT=Path("public/data/verified-player-links.json")
FACTIONS={"adepta sororitas","adeptus custodes","adeptus mechanicus","aeldari","astra militarum","black templars","blood angels","chaos daemons","chaos knights","chaos space marines","dark angels","death guard","deathwatch","drukhari","emperor's children","genestealer cults","grey knights","imperial agents","imperial knights","leagues of votann","necrons","orks","space marines","space wolves","t'au empire","thousand sons","tyranids","world eaters"}
def norm(v):
 s=unicodedata.normalize("NFKD",str(v or ""))
 s="".join(c for c in s if not unicodedata.combining(c))
 return re.sub(r"[^a-z0-9]","",s.casefold())
def text(n):return n.get_text(" ",strip=True) if n else ""
def domain_safe(url,root=ROOT):
 p=urlparse(url)
 return p.scheme=="https" and p.netloc=="listhammer.info" and p.path.startswith("/wtc/") or (p.scheme=="https" and p.netloc=="listhammer.info" and p.path.startswith("/players/"))
def main():
 if not DATA.exists():raise RuntimeError("WTC event CSV missing")
 roster=defaultdict(set)
 with DATA.open(encoding="utf-8",newline="") as f:
  for r in csv.DictReader(f):
   if r.get("event_name")!="WTC WH40K 2026":continue
   for side in "ab":
    name=r.get("player_"+side,"");faction=r.get("faction_"+side,"")
    if name and faction:roster[norm(name)].add(norm(faction))
 session=requests.Session()
 session.headers["User-Agent"]="MatchupLab/0.5 (public verified link cross-references; no bulk list copying)"
 rp=urllib.robotparser.RobotFileParser()
 res=session.get(ROOT+"/robots.txt",timeout=25)
 if not res.ok:raise RuntimeError("Cannot confirm Listhammer robots.txt; preserving previous links")
 rp.parse(res.text.splitlines())
 def fetch(url):
  if not domain_safe(url) and url!=ROOT_URL:raise RuntimeError("Unapproved Listhammer URL")
  if not rp.can_fetch("*",url):raise RuntimeError("Robots disallow: "+url)
  time.sleep(1.5)
  r=session.get(url,timeout=30);r.raise_for_status()
  return BeautifulSoup(r.text,"html.parser")
 index=fetch(ROOT_URL)
 if "WTC WH40K 2026" not in text(index.find("h1")):raise RuntimeError("Unexpected WTC event page")
 countries=set()
 for anchor in index.find_all("a",href=True):
  url=urljoin(ROOT,anchor["href"])
  if urlparse(url).path.startswith("/wtc/") and domain_safe(url):countries.add(url)
 if len(countries)<25:raise RuntimeError("WTC country links incomplete; no output published")
 links=defaultdict(set);checked=0
 for country in sorted(countries):
  try:page=fetch(country)
  except (requests.RequestException,RuntimeError) as e:
   print("Country page unavailable",country,str(e)[:90],file=sys.stderr);continue
  roster_header=next((h for h in page.find_all(re.compile("^h[1-6]$")) if text(h).strip().lower()=="roster"),None)
  if not roster_header:continue
  # Traverse the section after the roster heading, including nested lists.
  # Do not scan the preceding matchups, as those include opposition players.
  for node in roster_header.next_elements:
   if getattr(node,"name",None) in ("h1","h2","h3") and node is not roster_header:break
   if getattr(node,"name",None)!="a":continue
   url=urljoin(ROOT,node.get("href",""))
   if not urlparse(url).path.startswith("/players/") or not domain_safe(url):continue
   name=text(node)
   parent=node.find_parent("li") or node.find_parent("tr")
   if parent is None:continue
   nearby=text(parent)
   factions=[f for f in FACTIONS if norm(f) in norm(nearby)]
   # A bullet should contain only one faction; generic Space Marines
   # must not silently absorb Dark Angels, Blood Angels, etc.
   exact=[f for f in factions if norm(f) in roster.get(norm(name),set())]
   if len(exact)==1 and len(factions)==1:links[(norm(name),norm(exact[0]))].add(url)
  checked+=1
 matches=[]
 ambiguous=[]
 for (name,fac),urls in sorted(links.items()):
  if len(urls)==1:
   matches.append({"event_name":"WTC WH40K 2026","player_key":name,"faction_key":fac,"profile_url":next(iter(urls)),"source":"Listhammer WTC 2026 country roster","link_type":"verified_player_profile_not_army_list"})
  else:ambiguous.append({"player_key":name,"faction_key":fac,"candidates":len(urls)})
 if len(matches)<20:raise RuntimeError("Too few verified matches: "+str(len(matches))+"; no incomplete results published")
 report={"updated_at_utc":datetime.now(timezone.utc).isoformat(),"source_event":ROOT_URL,
 "country_pages_checked":checked,"profiles_verified":len(matches),"ambiguous":ambiguous,"matches":matches,
 "note":"Exact name+faction+WTC 2026 roster matches. These URLs are player profiles, not proven game-specific lists. No results imported or guessed."}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 OUTPUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print("WTC participant profile links:",len(matches),"countries checked:",checked)
if __name__=="__main__":
 try:main()
 except Exception as e:print("Listhammer validation failed:",e,file=sys.stderr);sys.exit(1)
