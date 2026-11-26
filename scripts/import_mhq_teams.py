#!/usr/bin/env python3
"""Collect public MHQ team pairing pages; stage CSVs for review before publishing."""
import argparse,csv,re,time,unicodedata,urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from build_warehouse import FIELDS,valid
BASE="https://miniheadquarters.com"
DISPS={"Take and Hold":"Take and Hold","Prendre et Tenir":"Take and Hold","Purge the Foe":"Purge the Foe","Priority Assets":"Priority Assets","Reconnaissance":"Reconnaissance","Disruption":"Disruption","Perturbation":"Disruption"}
FACTIONS="Adepta Sororitas|Adeptus Custodes|Adeptus Mechanicus|Aeldari|Astra Militarum|Black Templars|Blood Angels|Chaos Daemons|Chaos Knights|Chaos Space Marines|Dark Angels|Death Guard|Deathwatch|Drukhari|Emperor's Children|Genestealer Cults|Grey Knights|Imperial Agents|Imperial Knights|Leagues of Votann|Necrons|Orks|Space Marines|Space Wolves|T'au Empire|Thousand Sons|Tyranids|World Eaters".split("|")
def plain(s):return " ".join(s.split())
def faction(s):
 if re.search(r"\bChaos\s*[-–]\s*Daemons\b|\bLegiones Daemonica\b",s,re.I):return "Chaos Daemons"
 for f in sorted(FACTIONS,key=len,reverse=True):
  if re.search(r"(?<!\w)"+re.escape(f)+r"(?!\w)",s,re.I):return f
 if "Adeptus Astartes" in s or "Ultramarines" in s:return "Space Marines"
 return ""
def list_info(s):
 header=re.split(r"Attached Units?|Unités Attachées|BATTLELINE|CHARACTERS|PERSONNAGES|OTHER DATASHEETS",s,flags=re.I)[0][:1000]
 header=header.replace("’","'")
 f=faction(header)
 aliases={**DISPS,"Atouts Prioritaires":"Priority Assets"}
 labels="|".join(re.escape(k) for k in sorted(aliases,key=len,reverse=True))
 m=re.search(r"(?:Force\s+Disposition|Disposition)\s*:\s*("+labels+r")\b",header,re.I)
 if not m:
  m=re.search(r"\(\s*\d+\s+(?:Detachment Points|Points de Détachement)\s*\)\s*("+labels+r")\b",header,re.I)
 d=next((v for k,v in aliases.items() if m and m.group(1).casefold()==k.casefold()),"")
 det=""
 dm=re.search(r"\b(?:DETACHMENT|Détachement)\s*:\s*(.+?)(?=\s*\+\s*|\s+Force Disposition\s*:|\s+\(\d+/\d+\)|$)",header,re.I)
 if dm:det=plain(dm.group(1))
 elif m and f:
  pre=header[:m.start()]
  matches=list(re.finditer(re.escape(f),pre,re.I))
  if matches:det=plain(re.sub(r"\(\s*\d+\s+(?:Detachment Points|Points de Détachement)\s*\)\s*$","",pre[matches[-1].end():]))
 if not f or not d:print("UNPARSED LIST HEADER",repr(header))
 return f,d,det
def main():
 p=argparse.ArgumentParser();p.add_argument("url");p.add_argument("--date",required=True);p.add_argument("--teams",type=int,required=True);p.add_argument("--output",required=True);a=p.parse_args()
 sess=requests.Session();sess.headers["User-Agent"]="40k-team-matchup-lab/1.0 (public tournament statistics)"
 robots=urllib.robotparser.RobotFileParser();r=sess.get(BASE+"/robots.txt",timeout=30);r.raise_for_status();robots.parse(r.text.splitlines())
 def fetch(u):
  if urlparse(u).netloc!=urlparse(BASE).netloc or not robots.can_fetch("*",u):raise ValueError("URL not permitted: "+u)
  time.sleep(1.5);r=sess.get(u,timeout=45);r.raise_for_status();return BeautifulSoup(r.text,"html.parser")
 def links(s,u,pattern):return sorted({urljoin(u,x["href"]) for x in s.select("a[href]") if re.search(pattern,urlparse(urljoin(u,x["href"])).path)})
 root=fetch(a.url);h=root.find("h1");name=plain(h.get_text(" ",strip=True))
 rounds=links(root,a.url,r"/round/\d+/?$")
 if not rounds:raise ValueError("No rounds found")
 games={};rejected=0
 for ru in rounds:
  rnd=int(re.search(r"/round/(\d+)",ru).group(1))
  for u in links(fetch(ru),ru,r"/round/\d+/individual/\d+/?$"):
   s=fetch(u);h=plain(s.find("h1").get_text(" ",strip=True));teams=re.sub(r"^Individual pairings between\s+","",h).split(" and ",1)
   if len(teams)!=2:continue
   for h2 in s.find_all("h2"):
    names=plain(h2.get_text(" ",strip=True)).split(" vs ",1)
    if len(names)!=2:continue
    chunks=[]
    for tag in h2.next_elements:
     if getattr(tag,"name",None)=="h2":break
     if getattr(tag,"name",None) in ("table","h3"):chunks.append(tag)
    table=next((x for x in chunks if x.name=="table"),None)
    lists=[x for x in chunks if x.name=="h3" and "Army list" in x.get_text()]
    if table is None or len(lists)!=2:
     print('REJECT structure',u,names,'table',table is not None,'army headings',len(lists));rejected+=1;continue
    scores={}
    for tr in table.select("tr"):
     cells=[plain(c.get_text(" ",strip=True)) for c in tr.select("th,td")]
     if len(cells)==3 and all(x.isdigit() for x in cells[1:]):scores[cells[0]]=list(map(int,cells[1:]))
    info=[]
    for heading in lists:
     parts=[]
     for el in heading.next_elements:
      if getattr(el,"name",None) in ("h2","h3"):break
      if isinstance(el,str):parts.append(str(el))
     info.append(list_info(plain(" ".join(parts))))
    if "Score" not in scores:
     print("REJECT score",u,names,scores);rejected+=1;continue
    row=dict.fromkeys(FIELDS,"")
    row.update(event_name=name,event_date=a.date,source_url=u,event_size_teams=str(a.teams),round=str(rnd),team_a=teams[0],team_b=teams[1],player_a=names[0],player_b=names[1],faction_a=info[0][0],faction_b=info[1][0],disposition_a=info[0][1],disposition_b=info[1][1],detachment_a=info[0][2],detachment_b=info[1][2],score_a_20=str(scores["Score"][0]),score_b_20=str(scores["Score"][1]),edition="11",event_format="team",score_type="team_wtc_score")
    if "Goal average" in scores:row.update(raw_vp_a=str(scores["Goal average"][0]),raw_vp_b=str(scores["Goal average"][1]))
    if not valid(row):
     print("REJECT validation",u,names,{k:row[k] for k in ("faction_a","faction_b","disposition_a","disposition_b","score_a_20","score_b_20","round")});rejected+=1;continue
    key=(rnd,tuple(sorted(n.casefold() for n in names)))
    if key in games and games[key]!=row:raise ValueError("Conflicting pairing "+str(key))
    games[key]=row
 if not games:raise ValueError("No validated games; no output written")
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(games.values())
 print(f"Staged {len(games)} games; rejected {rejected}; source MiniHeadQuarters. Review coverage and overlap before publication.")
if __name__=="__main__":main()
