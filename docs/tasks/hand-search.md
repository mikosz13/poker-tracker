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

## Results (17.10.2026)
- Same hands on both databases: `tests/test_postgres.py::test_hand_search_finds_the_same_hands_as_sqlite` imports the
  same demo tournaments into SQLite and PostgreSQL and compares 25 filters (each preflop action alone, the others
  alone and combined, a period, paging): counts, totals, ids and order are identical. It runs in CI's PostgreSQL job.
- Benchmark on 500,000 synthetic hands (`python tools/bench_hand_search.py --explain [--db postgresql://…]`), each
  query measured after one warm-up run, as in the app:
  - SQLite: slowest 129 ms. Filters on time, position or hand class use their indexes; filters on the action, the
    result or the stack scan the table and still stay under 0.13 s.
  - PostgreSQL 16 (local, default settings): slowest 91 ms. The planner reads the time, position and class indexes
    backwards for the newest-first order, and runs a parallel scan for the rarest combination (buy-in + format +
    fold to 3-bet).
  - No new index needed: every combination is far under the 1 s limit on both.
