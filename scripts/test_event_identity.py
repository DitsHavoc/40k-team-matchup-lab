#!/usr/bin/env python3
"""No duplicate tournament counted across sources."""
from event_identity import choose_events
def row(day,player):
 return {"event_date":day,"player_a":player}
meta={"path":"public/data/singles-lgt-2026.csv","name":"The London Grand Tournament - 40k Main Event (LGT 40k GT)",
 "format":"singles","rows":[row("2026-09-25",str(i)) for i in range(40)]}
lis={"path":"public/data/listhammer-games-aabbccddeeff.csv","name":"THE LONDON GRAND TOURNAMENT - 40K MAIN EVENT (LGT 40K GT)",
 "format":"singles","rows":[row("2026-09-26",str(i)) for i in range(50)]}
separate={"path":"public/data/independent.csv","name":"Another Tournament","format":"singles",
 "rows":[row("2026-09-25",str(i)) for i in range(20)]}
accepted,suppressed=choose_events([meta,lis,separate])
assert len(accepted)==2,(accepted,suppressed)
assert len(suppressed)==1,suppressed
assert sum(len(e["rows"]) for e in accepted)==70
assert suppressed[0]["reason"]=="duplicate_tournament_source"
different_format={"path":"public/data/team.csv","name":meta["name"],"format":"team","rows":[row("2026-09-25","A")]}
kept,skip=choose_events([meta,different_format])
assert len(kept)==2 and not skip
different_month={"path":"public/data/december.csv","name":meta["name"],"format":"singles","rows":[row("2026-12-20","B")]}
kept,skip=choose_events([meta,different_month])
assert len(kept)==2 and not skip
# Verified source names that differ must also collapse to one tournament.
summer_a={"path":"a.csv","name":"UKTC Summer ITT 2026","format":"team","rows":[row("2026-08-08","A")]}
summer_b={"path":"b.csv","name":"The Summer I. T. T.","format":"team","rows":[row("2026-08-09","B"),row("2026-08-09","C")]}
kept,excluded=choose_events([summer_a,summer_b])
assert len(kept)==1 and len(excluded)==1,(kept,excluded)
print("PASS: cross-source events and verified name aliases are deduplicated; separate tournaments preserved")
