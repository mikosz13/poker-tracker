# pokertracker

Tournament tracker for GGPoker. Imports PokerCraft exports (hand histories and tournament summaries),
stores them in SQL and answers the questions a player actually has: *what is my ROI, where do I win and lose,
how do I play at different stack depths?*

## Why

I play tournaments on GGPoker as a hobby: mostly Bounty Hunters, now and then a satellite. Like most
recreational players I had simple questions and no honest answers. Am I actually winning? Was that deep run
skill or a heater? Do I do worse when I register late?

The serious tools that answer this are paid and built to do everything for everyone. Plenty of people who play
for fun will never pay for a tracker, so they play blind. This project is the opposite trade-off: free, narrow,
and done properly. GGPoker tournaments only, straight from the files PokerCraft already gives you, and nothing
to type in by hand.

What it cares about:

- **Late registration and re-entries are part of the story.** Every entry is detected from your hands with the level
  you joined at, and the tournament's starting stack is worked out from your entries (or shown as unknown).
- **A ticket is not cash.** Satellite seats are reported next to your ROI, never mixed into it.
- **Luck is measured, not felt.** All-in EV is computed exactly over every possible runout, so "I ran bad"
  becomes a number in big blinds.
- **Trust, but verify.** Formulas are in plain code, data is in plain SQL, and the test suite checks the maths
  against brute force and known results.
- **Honest by default.** Small samples and unknown cards are flagged, never guessed.

What it is not: no HUD, no ICM, no solver, no cash games. If you need those, PokerTracker 4 is the
right tool. If you just want to know how your tournaments really go, this is for you.

## Quick start (SQLite, no database server needed)

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.10+
pip install -e .
python -m unittest discover -s tests -t .              # all tests should pass
python -m pokertracker import exports/                 # .txt, .pdf (text layer), .zip, or whole folders
python -m pokertracker report
python -m pokertracker tournament --html report.html   # latest tournament
python -m pokertracker dashboard --html dashboard.html
```

Re-importing the same files is safe: hands are deduplicated by hand id, summaries are upserted.
Files can arrive in any order (summary before hands, one file per entry, ...).

## Desktop app

```bash
pip install -e ".[app]"          # adds pywebview for a native window
python -m pokertracker app       # or: pokertracker-app
python -m pokertracker app --browser   # same app in your default browser
```

Screens: dashboard (last session, ROI, luck, late reg vs start, buy-in, positions), tournament list with
filters, tournament details, a **hand replayer** on a table view (arrow keys, space for autoplay, clickable action log), import, and a page that explains
how luck is calculated. The app runs a small server on `127.0.0.1` only; imports require a per-launch token.
Data lives in the per-user folder (`~/Library/Application Support/PokerTracker` on macOS,
`%APPDATA%\PokerTracker` on Windows); `--db` or `DATABASE_URL` override it.

## PostgreSQL

```bash
docker compose up -d
pip install -e ".[postgres]"
export DATABASE_URL=postgresql://poker:poker@localhost:5432/poker
python -m pokertracker import ~/poker/exports
```

## How it works

| Layer | File | Notes |
|---|---|---|
| Parsing | `pokertracker/hands.py`, `summary.py` | regex parsers, chip-conservation checked per hand |
| Storage | `pokertracker/sql/schema.sql` | portable DDL, natural keys, idempotent loads |
| Analytics | `pokertracker/sql/views.sql` | ROI (cash vs tickets), VPIP/PFR by position and stack depth |
| Glue | `importer.py`, `db.py`, `cli.py`, `report.py` | one interface for SQLite and PostgreSQL |

### All-in EV (exact, no Monte Carlo)

`pokertracker/equity.py` computes what PokerTracker calls *All-in Adjusted EV*. When the betting closes with
cards still to come and the cards of every live player are known (Hero's own, plus opponents' cards shown at
showdown), **every possible runout is enumerated** (1,712,304 boards for a heads-up preflop all-in) and scored
with a vectorised 7-card evaluator. Ties split the pot, side pots are layered by contribution, and the result is
stored per player: equity, expected chips, actual chips and *luck* (actual minus expected, in chips and BB).
Bad beats (>= 80% equity, lost) and suckouts (<= 20%, won) are flagged.

How it is validated (see `tests/test_equity.py`): the evaluator reproduces the exact category counts of all
2,598,960 five-card hands, agrees with an independent slow reference evaluator on random 7-card hands,
equities match closed-form outs counts and brute force with the reference evaluator (heads-up and a three-way
side pot), equities sum to 1 and luck is zero-sum within every hand.
Equity depends on suit configuration (AA vs KK is 81.3% with disjoint suits, 82.6% with shared suits), which is
why it is computed exactly instead of looked up in a table. Unknown opponent cards are never guessed: such
hands are skipped, as in PokerTracker. Solver / GTO analysis is out of scope.

Speed: about 1 s per heads-up preflop all-in (cold). Results are cached by matchup (suit-canonical key) in the
`equity_cache` table, so each matchup is computed once.

### Post-tournament report

```bash
python -m pokertracker tournament            # latest tournament (or give an id)
python -m pokertracker tournament 313988468 --html report.html   # self-contained, phone friendly
```

Result and ROI, entries, stack path (chart), best and worst position (only positions with at least 8 hands are
ranked), biggest wins and losses, strongest showdown hand, and all-in luck with bad beats and suckouts. Text and
HTML are rendered from the same data, so the numbers are identical.

### Dashboard

`python -m pokertracker dashboard --html dashboard.html` writes a phone-friendly overview of all tournaments:
cumulative cash profit, actual vs all-in-adjusted result in BB, results per tag and the latest tournaments.
It warns when the sample is small (fewer than 30 tournaments), because ROI is mostly variance until then.

### Automatic classification (no manual input)

`pokertracker/classify.py` tags every tournament from the imported data only: `format:` (bounty / satellite /
regular), `mystery-bounty`, `target:` (what a satellite feeds), `stake:` and `field:` tiers, `speed:` (median
minutes between blind levels measured from the hand timestamps, robust against breaks, only when at least 3
consecutive levels were observed), `entry:start` / `entry:late` (level Hero entered at) and `re-entered`.
`report` shows cash ROI and ITM per tag. Thresholds are constants at the top of the module.
No payout structures are needed anywhere: ROI uses the buy-in and the prize from the summary, and the all-in EV
is in chips.

Domain details handled:
- **Late registration and re-entries**: entries are derived from Hero's hands (a new entry starts after the stack hits zero).
  The hands are the source of truth for entries; cost and ROI come from the summary, re-entries included. The starting
  stack is the most common first-hand stack of entries in tournaments with the same name and buy-in, or unknown.
- **Only No-Limit Hold'em tournaments in dollars**: Sit & Go (AoF, FlipNGo ...), PLO/Omaha and other games, tournaments
  in other currencies and cash-game hands are never imported; the import result says how many were left out and why.
- **Satellites**: prizes that are tickets are stored with their face value and excluded from cash ROI.
- **Bounty formats**: buy-in split (prize + fee + bounty) kept; ROI uses the full cost including re-entries.

## Status

- Tested: parsers, importer, views, equity engine, classification, reports, replay, knockouts, background import and
  the HTTP API (unit tests + runs on real exports), on SQLite. PostgreSQL tests are included and run in CI.
- Not run yet: the native window (pywebview) and the packaged .app/.exe; the same UI was tested in a headless
  browser. The release workflow builds both on GitHub.
- Out of scope by decision: ICM / payout structures, cash games, solver analysis, HUD.

## Docs

- [Installing (for players)](docs/INSTALL.md)
- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Checkpoint checklist](docs/CHECKPOINT.md)
- [Changelog](CHANGELOG.md)
