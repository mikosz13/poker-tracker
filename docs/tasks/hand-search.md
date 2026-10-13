# Task (sketch): Hand search

Queue: after Analysis v2 stage 2 and Pulpit v3.

## What
- A new tab **Ręce** with filters:
  - period; buy-in / format (bounty, satellite, plain);
  - Hero's position;
  - hands from the 13×13 grid (click to select, drag for a range);
  - stack in BB (from–to);
  - preflop action (RFI, limp, call of a raise, 3-bet, fold to 3-bet, open shove, …, the Analysis v2 definitions);
  - all-in yes/no; showdown yes/no;
  - result (won / lost, at least X BB, by actual or wg EV).
- Results: a list (date, tournament, position, cards, stack, action, result in BB) sorted by date; a click opens the
  replayer with **następna / poprzednia** across the result list.
- **Pokaż te ręce** on the leak and strength cards (Analysis v2 stage 2) opens this tab with the matching filters.

## How
- Parameterised SQL only (no string-built filters), portable between SQLite and PostgreSQL.
- Preflop spots stored per hand at import (or a cached table refreshed after import), so filters do not re-parse
  actions.
- Indexes for the filtered columns; checked with EXPLAIN on both databases.
- Benchmark on ~500k synthetic hands: every filter combination under 1 s on SQLite; a script in tools/ to generate the
  data.

## Checks
- Tests: each filter alone and in combination, empty result, paging; the same hands as Analysis v2 counts for the
  same spot.
- 800 px, light and dark, PL and EN; screenshots before merge.
