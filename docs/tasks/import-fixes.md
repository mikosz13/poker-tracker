# Task: Import fixes after the first full import

Context: first import of all tournaments from 1 Sep to 3 Oct 2026 (137 tournaments, 6,165 hands, 513 Hero all-ins).
Read pokertracker/hands.py (entries_from_rows), pokertracker/summary.py, pokertracker/importer.py and
pokertracker/migrations.py first.

## 1. False "history incomplete" on late registration
- 33 of 190 entries are flagged `starts_fresh = FALSE` although nothing is missing. Almost all are late
  registrations into tournaments whose starting stack is not 10,000: Bounty Hunters Deepstack Turbo and Mini Heater
  (20,000), Daily Hyper (6,000), MEGA satellites (5,000), WSOP $54 Sunday (25,000).
- Cause: without a level-1 hand of Hero in that tournament the starting stack defaults to 10,000.
- Fix: recognise the starting stack without assuming 10,000 (e.g. learn it per tournament name from entries that
  did start at level 1 or from re-entries, and treat Hero's first hand of an entry as fresh when it looks like a
  full starting stack). Keep flagging real gaps: an entry whose first hand is clearly mid-tournament, and the
  existing check "summary says more entries than the hands contain".
- Existing databases are repaired by a migration (recompute entries), not by deleting anything.
- Tests with late-reg entries at 6,000 / 20,000 / 25,000 and a real gap.

## 2. Ignore formats that are never analysed
- Sit & Go (including AoF and FlipNGo), PLO / any Omaha, and tournaments not in dollars (e.g. Zodiac in ¥) are
  ignored completely: no summaries, no hands, no statistics.
- Rules, not a list of names: game is not "Hold'em No Limit", the name says "Sit & Go", or the currency is not $.
- The import result lists them as "ignored (Sit & Go / PLO / not in $)" instead of "unrecognised summary format".
- Rows that are already in the database for such tournaments (Zodiac: 7 hands, FlipNGo: 1 hand) are removed by
  a migration.
- Tests for each rule.

## 3. Not code
- 4 tournaments from 2 Oct have hands but no summary (3x Bounty Hunters Hyper Special, Mini Heater): Mik exports
  the summaries for 2 Oct again.

## 4. Done when
- Tests pass; after the migration the real database has no false "history incomplete" flags and no ignored formats.
- CHANGELOG.md (Unreleased) updated; summary at the end.
