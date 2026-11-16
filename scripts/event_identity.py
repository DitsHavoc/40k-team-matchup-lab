#!/usr/bin/env python3
"""Tournament-level identity reconciliation across independent sources.

Prefer the more complete verified dataset for one tournament; never concatenate
two sites' copies of the same event. Score and player dedupe remains an
additional safeguard within the selected event.
"""
from collections import defaultdict
from datetime import date
import re,unicodedata

def normal_name(text):
    t=unicodedata.normalize("NFKD",str(text or "")).casefold()
    t="".join(ch for ch in t if not unicodedata.combining(ch))
    t=t.replace("&","and")
    return re.sub(r"[^a-z0-9]","",t)

def event_group_key(name, event_format):
    fmt="singles" if event_format=="singles" else "team"
    return (normal_name(name),fmt)

def first_date(rows):
    dates=[]
    for r in rows:
        try:dates.append(date.fromisoformat(str(r.get("event_date",""))[:10]))
        except ValueError:pass
    return min(dates) if dates else None

def overlaps(a,b,days=4):
    x,y=first_date(a),first_date(b)
    return x is not None and y is not None and abs((x-y).days)<=days

def source_priority(path):
    path=str(path).lower()
    if "listhammer" in path:return 1
    return 2

def choose_events(source_groups):
    """Source groups are {path,name,format,rows}; return (groups, suppressed).
    Casefolded tournament name and start-date proximity are required; distinct
    event formats never silently merge. Ambiguities prefer *exclusion* rather
    than double-counting.
    """
    accepted=[]
    suppressed=[]
    for event in sorted(source_groups,key=lambda e:(-len(e["rows"]),-source_priority(e["path"]),str(e["path"]))):
        same=[prior for prior in accepted if
              event_group_key(prior["name"],prior["format"])==event_group_key(event["name"],event["format"]) and
              overlaps(prior["rows"],event["rows"])]
        if same:
            suppressed.append({"event":event["name"],"dropped_source":str(event["path"]),
                "chosen_source":str(same[0]["path"]),"suppressed_rows":len(event["rows"]),
                "reason":"duplicate_tournament_source"})
        else:accepted.append(event)
    return accepted,suppressed
