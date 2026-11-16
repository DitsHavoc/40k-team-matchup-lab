#!/usr/bin/env python3
"""No score changes, no guesses, no cross-event mixing."""
from backfill_singles_dispositions import enrich
def game(event,a,b,da,db):
 return dict(source_url=event,event_name="Event",event_format="singles",
  player_a=a,player_b=b,faction_a="Necrons",faction_b="Space Marines",
  disposition_a=da,disposition_b=db,score_a_20="12",score_b_20="8")
a="https://metascribe.gg/tournaments/a/"
b="https://metascribe.gg/tournaments/b/"
rows=[game(a,"P1","P2","Take and Hold",""),game(a,"P1","P3","",""),
      game(b,"P1","P2","",""),game(a,"P4","P5","Reconnaissance","")]
before=[(r["score_a_20"],r["score_b_20"]) for r in rows]
stats=enrich(rows)
assert rows[1]["disposition_a"]=="Take and Hold"
assert rows[2]["disposition_a"]==""
assert rows[0]["disposition_b"]==""
assert stats["filled"]==1
assert before==[(r["score_a_20"],r["score_b_20"]) for r in rows]
# Conflict between player histories is never filled.
c=[game(a,"P1","P2","Take and Hold",""),game(a,"P1","P3","Disruption",""),
   game(a,"P1","P4","","")]
stats=enrich(c)
assert c[2]["disposition_a"]==""
assert stats["disposition_conflict"]==1
# Roster may independently fill blanks if an exact identity and faction match.
d=[game(a,"P1","P2","","")]
key=(a,"p1","necrons")
stats=enrich(d,{key:{"Priority Assets"}})
assert d[0]["disposition_a"]=="Priority Assets" and stats["filled"]==1
print("PASS: verified fill, source/faction isolation, conflicting evidence rejection, unchanged scores")
