# Changelog

## Unreleased
- Replayer v2: oval table with seats rotated so Hero sits at the bottom, cards, bets in front of players, dealer
  button, all-in badges and equity at the all-in moment; autoplay (3 speeds), space = play/pause, Home/End, and an
  action log grouped by street where clicking a line jumps to that step. Light/dark theme, works down to 380 px.
- Replayer starts at the first decision: antes and blinds are already in the pot instead of being steps. Uncalled
  bets are shown being returned, so the pot that is left equals the total pot paid out.
- Replayer names opponents by position (UTG ... BB, heads-up BTN/SB and BB) instead of their hashed IDs, on the
  table and in the log; Hero stays "Hero" with the position as a small label. No database changes.
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
