#!/usr/bin/env python3
"""Extract publicly visible event match records from Metascribe.

Reads the named event's team placings, round history and individual game history.
Only keeps games with a uniquely identified round/opponent and matching event dates.
Uses robot exclusion checks and a polite request interval. Prints coverage audit.
"""
import argparse
import csv
import io
import re
import sys
import time
import urllib.robotparser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://metascribe.gg"
EVENTS = {
  "studs-snotlings-2026": {
    "url": BASE + "/tournaments/studs-and-snotlings-2026/",
    "name": "Studs and Snotlings 2026",
    "date": "2026-09-19",
    "teams": 26,
    "rounds": 5,
    "players_per_team": 8,
    "min_games": 400,
    "output": "public/data/studs-and-snotlings-2026.csv"
  },
  "nrw-alpine-2026": {
    "url": BASE + "/tournaments/nrw-40k-teams-2026-alpine-cup/",
    "name": "NRW 40K Teams 2026 – Alpine Cup",
    "date": "2026-09-19",
    "teams": 30,
    "rounds": 5,
    "players_per_team": 5,
    "min_games": 260,
    "output": "public/data/nrw-alpine-cup-2026.csv"
  },
  "wtc-2026": {
    "url": BASE + "/tournaments/wtc-wh40k-2026/",
    "name": "WTC WH40K 2026",
    "max_days": 5,
    "date": "2026-08-13",
    "teams": 46,
    "rounds": 7,
    "players_per_team": 8,
    "min_games": 950,
    "output": "public/data/wtc-wh40k-2026.csv"
  },
  "krakow-2026": {
    "url": BASE + "/tournaments/warhammer-open-krakow-warhammer-40000/",
    "name": "Warhammer Open: Krakow Warhammer 40000",
    "date": "2026-09-11",
    "teams": 57,
    "rounds": 6,
    "players_per_team": 5,
    "min_games": 600,
    "output": "public/data/warhammer-open-krakow-2026.csv"
  },
  "gateway-2026": {
    "url": BASE + "/tournaments/the-2026-gateway-open-40k-teams-tournament/",
    "name": "The 2026 Gateway Open 40K Teams Tournament",
    "date": "2026-08-07",
    "teams": 24,
    "rounds": 5,
    "players_per_team": 8,
    "min_games": 350,
    "output": "public/data/gateway-open-teams-2026.csv"
  },
  "scottish-open-2026": {
    "url": BASE + "/tournaments/scottish-open-team-championship/",
    "name": "Scottish Open Team Championship",
    "date": "2026-10-17",
    "teams": 28,
    "rounds": 5,
    "players_per_team": 5,
    "min_games": 260,
    "output": "public/data/scottish-open-teams-2026.csv"
  },
  "south-pacific-8s-2026": {
    "url": BASE + "/tournaments/south-pacific-8s-october-event/",
    "name": "south pacific 8s October event",
    "date": "2026-10-09",
    "teams": 18,
    "rounds": 5,
    "players_per_team": 8,
    "min_games": 280,
    "output": "public/data/south-pacific-8s-2026.csv"
  },
  "challengers-2026": {
    "url": BASE + "/tournaments/the-challengers-cup-2026/",
    "name": "The Challengers Cup 2026",
    "max_days": 4,
    "date": "2026-09-11",
    "teams": 68,
    "rounds": 6,
    "players_per_team": 8,
    "min_games": 1200,
    "output": "public/data/challengers-cup-2026.csv"
  },
  "october-super-6s-2026": {
    "url": BASE + "/tournaments/october-super-6s/",
    "name": "October Super 6’s.",
    "date": "2026-10-31",
    "teams": 24,
    "rounds": 5,
    "players_per_team": 6,
    "min_games": 240,
    "output": "public/data/october-super-6s-2026.csv"
  },
  "kent-teams-november-2026": {
    "url": BASE + "/tournaments/the-kent-teams-november-2026/",
    "name": "The Kent Teams November 2026",
    "date": "2026-11-07",
    "teams": 30,
    "rounds": 5,
    "players_per_team": 5,
    "min_games": 250,
    "output": "public/data/kent-teams-november-2026.csv"
  },
  "uktc-autumn-itt-2026": {
    "url": BASE + "/tournaments/the-autumn-i-t-t-international-team-tournament-november/",
    "name": "UKTC Autumn ITT 2026",
    "date": "2026-11-14",
    "teams": 60,
    "rounds": 5,
    "players_per_team": 5,
    "min_games": 600,
    "output": "public/data/uktc-autumn-itt-2026.csv",
    "strict_event_date": True
  },
  "uktc-summer-itt-2026": {
    "url": BASE + "/tournaments/the-summer-i-t-t-international-team-tournament-august/",
    "name": "UKTC Summer ITT 2026",
    "expected_games": 892,
    "date": "2026-08-08",
    "teams": 71,
    "rounds": 6,
    "players_per_team": 5,
    "min_games": 600,
    "output": "public/data/uktc-summer-itt-2026.csv"
  }
}
parser=argparse.ArgumentParser(description="Import publicly displayed Metascribe team matches")
parser.add_argument("--event",required=True,choices=list(EVENTS))
args=parser.parse_args()
cfg=EVENTS[args.event]
EVENT_URL=cfg["url"]
EVENT=cfg["name"]
SOURCE_EVENT_NAME=("The Summer I. T. T." if args.event=="uktc-summer-itt-2026" else "The Autumn I. T. T." if args.event=="uktc-autumn-itt-2026" else EVENT)
START=datetime.fromisoformat(cfg["date"]).date()
TEAM_COUNT=cfg["teams"]
ROUNDS=cfg["rounds"]
PLAYERS_PER_TEAM=cfg["players_per_team"]
OUT=Path(cfg["output"])
COLS = ["event_name","event_date","source_url","event_size_teams","round","team_a","team_b",
        "player_a","player_b","faction_a","faction_b","detachment_a","detachment_b",
        "disposition_a","disposition_b","score_a_20","score_b_20","raw_vp_a","raw_vp_b",
        "mission_a","mission_b","terrain_layout","terrain_pack","deployment",
        "attacker_defender","edition","rules_version"]
DISPS = {"take":"Take and Hold","purge":"Purge the Foe","priority":"Priority Assets",
         "recon":"Reconnaissance","disruption":"Disruption"}
FACTIONS = ["Adepta Sororitas","Adeptus Custodes","Adeptus Mechanicus","Aeldari",
"Astra Militarum","Black Templars","Blood Angels","Chaos Daemons","Chaos Knights",
"Chaos Space Marines","Dark Angels","Death Guard","Deathwatch","Drukhari",
"Emperor's Children","Genestealer Cults","Grey Knights","Imperial Agents","Imperial Knights",
"Leagues of Votann","Necrons","Orks","Space Marines","Space Wolves","T'au Empire",
"Thousand Sons","Tyranids","World Eaters"]
def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()
def norm(s):
    return re.sub(r"[^a-z0-9]+", "", clean(s).casefold())
def get_text(node):
    clone=BeautifulSoup(str(node),"html.parser")
    for x in clone.select("img,svg,script,style"): x.decompose()
    return clean(clone.get_text(" ", strip=True))
def parse_date(s):
    m=re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+2026",s,re.I)
    if not m: return None
    return datetime.strptime(m.group(0),"%b %d %Y").date()
def parse_army(cell):
    """Metascribe renders army name and short disposition as adjacent text:
    e.g. NecronsPurge or AeldariRecon, often with an icon and hyperlink.
    Match a complete known faction prefix and disposition suffix.
    """
    t=get_text(cell)
    alts=[clean(im.get("alt","")) for im in cell.select("img") if im.get("alt")]
    labels=[t]+alts
    for label in labels:
        n=norm(label)
        for fac in sorted(FACTIONS,key=len,reverse=True):
            fn=norm(fac)
            if not n.startswith(fn):
                continue
            rem=n[len(fn):]
            for key,val in DISPS.items():
                if rem==key or rem.startswith(key) and rem[len(key):] in ("","disposition"):
                    return fac,val
    # Account for singular 'Genestealer Cult' on Metascribe.
    if norm(t).startswith("genestealercult"):
        tail=norm(t)[len("genestealercult"):]
        for key,val in DISPS.items():
            if tail==key:
                return "Genestealer Cults",val
    return None,None
def table_after(soup,heading):
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        if heading.casefold() in get_text(h).casefold():
            t=h.find_next("table")
            if t:return t
    return None
def data_rows(table):
    if not table:return []
    return [[get_text(c) for c in tr.find_all("td",recursive=False)] for tr in table.find_all("tr") if tr.find_all("td",recursive=False)]
session=requests.Session()
session.headers.update({"User-Agent":"40k-team-matchup-lab/0.2 (research; uses public pages; contact repository issues)"})
robots=urllib.robotparser.RobotFileParser()
try:
    rr=session.get(BASE+"/robots.txt",timeout=20)
    if rr.ok:
        robots.parse(rr.text.splitlines())
        if not robots.can_fetch("*",EVENT_URL):
            sys.exit("Robots policy disallows event URL; stopping")
    else:
        sys.exit("Cannot verify site robots policy; stopping")
except requests.RequestException as exc:
    sys.exit("Cannot verify site robots policy: "+str(exc))
def fetch(url):
    if not robots.can_fetch("*",url):raise RuntimeError("Robots policy disallows "+url)
    time.sleep(1.25)
    r=session.get(url,timeout=35)
    r.raise_for_status()
    return BeautifulSoup(r.text,"html.parser")
event_soup=fetch(EVENT_URL)
source_meta_match=re.search(r"\bMeta\s*:\s*(11(?:\.\d+){2,3})\b",get_text(event_soup),re.I)
EVENT_RULES_VERSION=source_meta_match.group(1) if source_meta_match else ""
if cfg.get("strict_event_date"):
    heading=event_soup.find("h1")
    if not heading or "autumn" not in norm(get_text(heading)):
        sys.exit("Autumn event page is not yet a verified 2026 event; refusing to import")
    # The 2025 event is currently indexed at this address. Never import it.
    block=get_text(event_soup)[:1200]
    year_mentions=re.findall(r"\b(?:Nov(?:ember)?\s+1[45],?\s+20\d{2}|20\d{2}[-/]11[-/]1[45])\b",block,re.I)
    if not any("2026" in match for match in year_mentions):
        sys.exit("No 14-15 November 2026 event date confirmed on page. Avoiding 2025 cross-edition contamination")
placings=table_after(event_soup,"Team Placings")
if not placings: sys.exit("No team placings table: site layout may have changed")
teams=[]
for row in placings.select("tr"):
    cells=row.find_all("td",recursive=False)
    if len(cells)<2:continue
    a=cells[1].find("a",href=re.compile(r"/teams/"))
    if a:
        teams.append((get_text(a),urljoin(BASE,a.get("href"))))
teams=list({url:(name,url) for name,url in teams}.values())
print("Teams on event page:",len(teams))
if len(teams)<TEAM_COUNT:sys.exit("Incomplete event team listing; refusing to publish partial data as whole event")
games={}
audit={"no_round":0,"no_faction":0,"bad_score":0,"stale":0,"rows":0}
for ti,(team,url) in enumerate(teams,1):
    try:
        soup=fetch(url)
        rounds_table=table_after(soup,"Round History")
        games_table=table_after(soup,"Game History - Team Events")
        roundlookup={}
        for row in data_rows(rounds_table):
            # Date, tournament, round, result, team, score, opponent ...
            if len(row)<7:continue
            if norm(SOURCE_EVENT_NAME) not in norm(row[1]):continue
            try: rnd=int(row[2])
            except ValueError:continue
            key=norm(row[6])
            roundlookup.setdefault(key,set()).add(rnd)
        if not games_table:
            print("No games table for:",team)
            continue
        for tr in games_table.find_all("tr"):
            cells=tr.find_all("td",recursive=False)
            if len(cells)<8:continue
            audit["rows"]+=1
            d=parse_date(get_text(cells[0]))
            if not d or not START<=d<=START+8*timedelta(days=1):
                audit["stale"]+=1;continue
            opponent_team=get_text(cells[7])
            rn=roundlookup.get(norm(opponent_team),set())
            if len(rn)!=1:
                audit["no_round"]+=1;continue
            rnd=next(iter(rn))
            # The round comes from this event's team Round History, not an inferred schedule.
            # ROUNDS is the advertised regular-round count, NOT a hard upper limit.
            # Shadow rounds, playoffs and finals can extend a valid event.
            if rnd < 1 or rnd > 20:
                audit.setdefault('invalid_round',0)
                audit['invalid_round']+=1
                continue
            if rnd > ROUNDS:
                audit.setdefault('extra_recorded_round',0)
                audit['extra_recorded_round']+=1
            fac_a,disp_a=parse_army(cells[3])
            fac_b,disp_b=parse_army(cells[5])
            if not all([fac_a,disp_a,fac_b,disp_b]):
                audit["no_faction"]+=1;continue
            m=re.search(r"(\d+)\s*[-–]\s*(\d+)",get_text(cells[4]))
            if not m or int(m.group(1))+int(m.group(2))!=20:
                audit["bad_score"]+=1;continue
            pa,pb=get_text(cells[2]),get_text(cells[6])
            if not pa or not pb:continue
            # An unordered player pair is unique within event+round.
            key=(rnd,tuple(sorted([norm(pa),norm(pb)])))
            score_a,score_b=map(int,m.groups())
            if key not in games:
                record={k:"" for k in COLS}
                record.update(event_name=EVENT,event_date=d.isoformat(),source_url=url,event_size_teams=TEAM_COUNT,
                              round=rnd,team_a=team,team_b=opponent_team,player_a=pa,player_b=pb,
                              faction_a=fac_a,faction_b=fac_b,disposition_a=disp_a,disposition_b=disp_b,
                              score_a_20=score_a,score_b_20=score_b,edition="11",rules_version=EVENT_RULES_VERSION)
                games[key]=record
            else:
                prior=games[key]
                if score_a not in (int(prior["score_a_20"]),int(prior["score_b_20"])):
                    print("CONFLICT! Game:",key)
                    sys.exit("Conflicting mirrored score: aborting import")
        print(f"Processed {ti}/{len(teams)}: {team}, unique games={len(games)}")
    except Exception as exc:
        print("Failed team",team,exc)
expected=cfg.get("expected_games",TEAM_COUNT*PLAYERS_PER_TEAM*ROUNDS//2)
print(f"Verified games: {len(games)}/{expected} theoretical maximum ({100*len(games)/expected:.1f}%). Byes, dropouts and extra rounds can change this denominator.")
print("Audit:",audit)
print("Observed round numbers:",sorted({int(r["round"]) for r in games.values()}))
# Do not make a nearly-empty partial export replace an apparently complete dataset.
if len(games)<cfg["min_games"]:
    sys.exit("Insufficient verified game coverage; likely HTML mismatch or incomplete data. Nothing written.")
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as fp:
    writer=csv.DictWriter(fp,fieldnames=COLS);writer.writeheader()
    writer.writerows(sorted(games.values(),key=lambda r:(int(r["round"]),r["team_a"],r["player_a"])))
print("Wrote",OUT)
