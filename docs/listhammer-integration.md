# Listhammer source integration and event deduplication

## What is connected

- `scripts/import_listhammer_export.py` accepts a **permissioned, individual-game CSV** for a verified Listhammer event URL.
- `scripts/build_warehouse.py` includes successful Listhammer exports from `public/data/listhammer-import-status.json`.
- `scripts/event_identity.py` reconciles tournament **names, verified aliases, event formats, and dates** (within four days).
- `public/data/event-aliases.json` is the audited list of cross-platform naming differences.
- The **more complete** valid source is retained for any matching tournament; the other source's entire event is suppressed. All individual matches are also deduplicated within the selected source.
- The warehouse manifest reports `duplicate_tournaments_suppressed`, `duplicate_tournament_rows_suppressed`, and the chosen source for each suppressed event.
- If names are genuinely different and no verified alias exists, add a reviewed alias rather than guessing. Do not merge different tournament formats or same-name events weeks apart.

## Licencing and data integrity

Listhammer's public event standings and faction statistics are **not individual game records** and must never be converted into invented matches. The Listhammer-derived part of `N041M/grimstat-corpus` is explicitly **not CC BY licensed** by the corpus maintainer. Obtain permission / an authorised game-level export before bulk redistribution. The importer requires a permission reference, and no Listhammer games enter predictions until valid per-game data is supplied.

## Import an authorised game-level export

Example:

```bash
python scripts/import_listhammer_export.py \
  --file /path/to/licensed-event-games.csv \
  --event-url https://listhammer.info/events/25351ae31762d64bde \
  --permission-reference 'Licence / written consent reference'
python scripts/build_warehouse.py
python scripts/test_event_identity.py
```

Required CSV columns: `event_name`, `event_date`, `player_a`, `player_b`, `faction_a`, `faction_b`, `score_a_20`, `score_b_20`. Games must be 11th edition and score 20 total. Blank / unverified scores and standings-only exports are refused.

The Listhammer importer stages validated records; it does **not** claim they are additional unique games until the warehouse has rebuilt and deduplicated the corresponding tournament.

## Current status

The connector is ready for authorised game-level data. Until the first authorised export is supplied, it has **added zero Listhammer games**. Continue using the existing verified Metascribe results and their independent provenance.
