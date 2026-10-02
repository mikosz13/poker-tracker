# Task: Import fixes after the first full import

Context: first import of all tournaments from 1 Sep to 3 Oct 2026 (137 tournaments, 6,165 hands, 513 Hero all-ins).
Read pokertracker/hands.py (entries_from_rows), pokertracker/summary.py, pokertracker/importer.py and
pokertracker/migrations.py first.

## 1. False "history incomplete" on late registration
- 33 of 190 entries are flagged `starts_fresh = FALSE` although nothing is missing. Almost all are late
  registrations into tournaments whose starting stack is not 10,000: Bounty Hunters Deepstack Turbo and Mini Heater
  (20,000), Daily Hyper (6,000), MEGA satellites (5,000), WSOP $54 Sunday (25,000).
- Cause: without a level-1 hand of Hero in that tournament the starting stack defaults to 10,000.
- No "history incomplete" flag at all: entries always come from the hand histories, also when the summary reports a
  different number. Cost and ROI still come from the summary (re-entries included), as decided for ROI.
- The starting stack is determined from the data instead of the 10,000 constant: the most common stack at the first
  hand of an entry among tournaments with the same name and buy-in. When it cannot be determined, it is "unknown",
  without any flag.
- Existing databases are repaired by a migration (recompute entries), not by deleting anything.
- Tests: a late registration into a tournament whose starting stack is not 10,000 (e.g. 20,000) is not flagged and
  gets the right starting stack; a summary with more entries than the hands contain gives no flag and the entries
  from the hands; a starting stack that cannot be determined is "unknown".

## 2. Ignore formats that are never analysed
- Anything outside No-Limit Hold'em tournaments in dollars is never imported: Sit & Go (including AoF and FlipNGo),
  PLO / any Omaha or other games, tournaments not in dollars (e.g. Zodiac in ¥) and cash-game hands. No summaries,
  no hands, no statistics.
- Rules, not a list of names: no "Tournament #" (cash game), the name says "Sit & Go", the game is not
  "Hold'em No Limit", or the currency is not $.
- Skipped files and tournaments are counted with their reason (Sit & Go, PLO, currency other than $) in the import
  summary (CLI and stored import result) and shown in the app, instead of "unrecognised summary format".
- Rows that are already in the database for such tournaments (Zodiac: 7 hands, FlipNGo: 1 hand) are removed by
  a migration.
- Tests for each rule.

## 3. Not code
- 4 tournaments from 2 Oct have hands but no summary (3x Bounty Hunters Hyper Special, Mini Heater): Mik exports
  the summaries for 2 Oct again.

## 4. Done when
- Tests pass; after the migration the real database has no false "history incomplete" flags and no ignored formats.
- CHANGELOG.md (Unreleased) updated; summary at the end.
