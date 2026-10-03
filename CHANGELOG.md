# Changelog

## Unreleased
- Fix: a database still on schema 1 (0.3.0) failed to upgrade, because step 2 used a column that only step 3 added.
  All columns are now added before the upgrade steps run. The whole upgrade from 0.2.0 is tested on SQLite and PostgreSQL.
- docs/INSTALL.md: first start on current macOS ("Open Anyway" in Privacy & Security).
- CI and release workflows use the current action versions (Node.js 24).
- Dashboard period: 24 h, 3 days, 1, 2 or 4 weeks, 3 or 6 months, or max. Every number, chart and table on the dashboard
  uses it ("Last session" does not); the choice is remembered.
- Cash profit and result/luck charts on a date axis, with labelled values and a tooltip per tournament.
- ITM as a percentage on the dashboard and in the buy-in, late-reg and category tables.
- Luck badge (Very lucky … Worst run, or No all-ins): total all-in luck compared with how much it could swing by chance
  (z-score); "How luck works" explains it.
- Best and worst starting hand (e.g. ATo, Q9o) and strongest and weakest position on a small table diagram, ranked
  only with at least 30 hands and always shown with the number of hands; heads-up (BTN/SB) is shown on its own.
- Tournament page: the stack in BB is a time chart with annotations where each entry starts (late reg or re-entry, level,
  stack in BB; the full starting stack in the tooltip) and a mark where the stack hit zero. Clicking it replays the hand.
- Position diagram on the dashboard goes clockwise from the big blind, the way the action moves (as in the replayer).
- Fix: a page that finished loading after you had already moved on (e.g. the dashboard) no longer replaces the page
  you opened.
- Late registration vs start leaves out tournaments whose summary reports more entries than the hands show, with a
  footnote count.
- Fix: a player showing one card after folding no longer replaces the dealt cards (16 of Hero's hands were affected).
  Database upgrade (schema 3) turns such cards into unknown; re-reading the files restores them.

## 0.4.0 (2026-10-03)
- Only No-Limit Hold'em tournaments in dollars are imported. Sit & Go (AoF, FlipNGo ...), PLO/Omaha and other games,
  tournaments in other currencies (e.g. Zodiac in ¥) and cash-game hands are never imported; the import result (CLI and
  app) counts them by reason instead of reporting "unrecognised summary format".
- No more "history incomplete" flag: entries always come from the hands (cost and ROI still from the summary). 0.3.0
  flagged late registrations whenever the starting stack was not 10,000.
- The starting stack is learned from the data: the most common first-hand stack of entries for the same tournament
  name and buy-in, shown in the tournament details and reports, or "unknown".
- Database upgrade (schema 2, automatic, backup first): removes out-of-scope tournaments imported by 0.3.0, recomputes
  entries and starting stacks; the equity cache is kept.

## 0.3.0 (2026-10-03)
- Position names fixed: the first player to act is always UTG (0.2.0 started at UTG+1 on 8-handed tables and at MP
  on 7-handed ones). Per-position statistics, reports and the replayer use the new names.
- Existing databases are upgraded in place on startup (schema version stored in the database). The first upgrade
  stores the button seat and recomputes positions from data already in the database, keeping the equity cache;
  a SQLite database is copied to `<name>.bak-v0` first. Re-importing files also refreshes positions of hands that
  are already stored.
- Replayer v2: oval table with seats rotated so Hero sits at the bottom, cards, bets in front of players, dealer
  button, all-in badges and equity at the all-in moment; autoplay (3 speeds), space = play/pause, Home/End, and an
  action log grouped by street where clicking a line jumps to that step. Light/dark theme, works down to 380 px.
- Replayer starts at the first decision: antes and blinds are already in the pot instead of being steps. Uncalled
  bets are shown being returned, so the pot that is left equals the total pot paid out.
- Replayer names opponents by position (UTG ... BB, heads-up BTN/SB and BB) instead of their hashed IDs, on the
  table and in the log; Hero stays "Hero" with the position as a small label. No database changes.
- Replayer: when the betting closes with a player all-in, the cards shown at showdown are face up from that moment,
  together with the equities, instead of only at the end.
- Replayer: after an all-in the equity of every player is recomputed exactly on the flop, turn and river (main pot),
  like on GGPoker. Luck still uses the equity at the all-in moment; "How luck works" says so.
- Four-colour deck everywhere cards are shown (app and HTML report): spades black, hearts red, diamonds blue,
  clubs green, so flush draws are visible at a glance. A "4-colour deck" switch under the replayer turns the app back to
  classic red/black; the choice is remembered in the database.
- Tests close their in-memory databases (no more ResourceWarnings on macOS Python 3.12).
- README: the "what it is not" list no longer says there is no replayer.
- docs/CHECKPOINT.md: results and feedback from the first run on a real Mac.

## 0.2.0
- Desktop app (`python -m pokertracker app`): dashboard with last session, tournament list with filters,
  tournament details, built-in hand replayer, import screen, "How luck works".
- Background import with progress; already-imported files are skipped; optional folder watching.
- Knockout counts (shared knockouts reported separately).
- Parallel precompute of exact all-in equities across CPU cores.
- Results by buy-in and by position on the dashboard.
- CI on Linux/macOS/Windows plus PostgreSQL 16; release workflow building macOS and Windows apps.

## 0.1.0
- Parsers, importer, portable SQL schema, exact all-in EV, classification, tournament report, HTML dashboard.
