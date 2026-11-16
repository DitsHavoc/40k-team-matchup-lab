#!/usr/bin/env python3
"""Offline six-figure warehouse stress test; all fake matches stay in a temporary folder."""
import csv,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_warehouse as warehouse
def main():
 with tempfile.TemporaryDirectory(prefix="matchup-scale-test-") as d:
  root=Path(d)/"data";root.mkdir()
  html=Path(d)/"index.html";html.write_text("let sources=['data/fixture.csv'];",encoding="utf-8")
  warehouse.ROOT=root;warehouse.HTML=html
  path=root/"fixture.csv"
  with path.open("w",encoding="utf-8",newline="") as f:
   writer=csv.DictWriter(f,fieldnames=warehouse.FIELDS);writer.writeheader()
   for i in range(100000):
    writer.writerow({"event_name":"Synthetic Test Event","event_date":"2026-10-01","round":"1",
      "player_a":f"Dummy A{i}","player_b":f"Dummy B{i}",
      "faction_a":"Aeldari","faction_b":"Adepta Sororitas",
      "disposition_a":"Take and Hold","disposition_b":"Disruption",
      "score_a_20":"12","score_b_20":"8","edition":"11","event_format":"team",
      "source_url":"https://example.invalid/test-only"})
   writer.writerow({"event_name":"Synthetic Test Event","event_date":"2026-10-01","round":"1",
     "player_a":"Dummy A0","player_b":"Dummy B0","faction_a":"Aeldari","faction_b":"Adepta Sororitas",
     "disposition_a":"Take and Hold","disposition_b":"Disruption",
     "score_a_20":"12","score_b_20":"8","edition":"11","event_format":"team",
     "source_url":"https://example.invalid/test-only"})
  warehouse.main()
  manifest=json.loads((root/"warehouse-manifest.json").read_text(encoding="utf-8"))
  assert manifest["total_unique_games"]==100000,manifest
  assert manifest["deduplicated"]==1,manifest
  assert len(manifest["shards"])==10,manifest
  assert sum(s["records"] for s in manifest["shards"])==100000
  assert all((root/Path(s["path"]).name).exists() for s in manifest["shards"])
  print("PASS: 100,000 unique synthetic games, 10 shards, duplicate removed; no fake data published")
if __name__=="__main__":main()
