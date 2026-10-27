# Poker Tracker

A free, open-source ([MIT](LICENSE)) tournament tracker for GGPoker. It reads the files PokerCraft already gives you (hand histories and tournament
summaries) and answers the questions a recreational player actually has: *am I winning, was it skill or luck, where do
I lose chips, does late registration hurt me?* Everything stays on your computer; nothing is typed in by hand.

![Dashboard on the made-up sample data](docs/img/dashboard.png)

## Get it

**Players:** download the app for macOS or Windows from [Releases](https://github.com/mikosz13/poker-tracker/releases)
and follow [Getting started / Jak zacząć](docs/INSTALL.md) (seven steps, English and Polish). No exports at hand? The
empty dashboard has a **Look around on sample data** button: 40 made-up tournaments in a separate database, so you can
see every screen before your first import. The app speaks English and Polish and has a light and a dark theme.

## What it shows

- **Dashboard**: the last session, profit, ROI, luck and the cumulative result for any period.
- **Tournament**: every entry (late reg, re-entries), the stack in BB or chips with each all-in marked (cards, equity,
  luck; click to replay), positions, knockouts.
- **Analysis**: VPIP, PFR, 3-bet and more by position and stack depth (PokerTracker 4 definitions); leaks and
  strengths only when they stand out from chance; results with and without showdown; where you finish; money by
  buy-in and entry.
- **Variance**: 10,000 runs of your next 100 / 500 / 1,000 tournaments drawn from your own results: the typical
  result and its spread, the largest drawdown, how many buy-ins keep its risk under 5 %, and "what if my ROI were".
- **Sessions**: how you play with several tournaments at once, by time of day and as a session goes on, compared at
  the same stack depth and counted by session, so one long evening does not make a habit.
- **Hands**: filter every hand by period, buy-in, position, starting hand (13×13 grid), stack, preflop action, all-in,
  showdown and result, then open it in the replayer (a table view, step by step or autoplay, next / previous hand).
- Also: "copy the hand" as text for forums, CSV export for Excel, a backup of the whole database in one click, a help
  page with every definition, and [how luck is calculated](#all-in-ev-exact-no-monte-carlo) written out in the app.

<p>
<img src="docs/img/tournament.png" alt="Tournament: the stack with every all-in marked" width="32%">
<img src="docs/img/analysis.png" alt="Analysis: overview, results with and without showdown, luck" width="32%">
<img src="docs/img/hands.png" alt="Hands: filters and results" width="32%">
</p>

<img src="docs/img/replayer.png" alt="Hand replayer: a five-way all-in, step by step" width="66%">

Screenshots are made from the made-up sample data (`python tools/screenshots.py`).

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
- **Tickets count at face value, on both sides.** A satellite won counts as the ticket's value and a tournament
  entered with a ticket costs its full buy-in, so the total matches your cash flow; the cash-only ROI sits under it.
- **Luck is measured, not felt.** All-in EV is computed exactly over every possible runout, so "I ran bad"
  becomes a number in big blinds.
- **Trust, but verify.** Formulas are in plain code, data is in plain SQL, and the test suite checks the maths
  against brute force and known results.
- **Honest by default.** Small samples and unknown cards are flagged, never guessed.

What it is not: no HUD, no ICM, no solver, no cash games. If you need those, PokerTracker 4 is the
right tool. If you just want to know how your tournaments really go, this is for you.

## For developers: quick start (SQLite, no database server needed)

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.10+
pip install -e .
python -m unittest discover -s tests -t .              # all tests should pass
python -m pokertracker import exports/                 # .txt, .pdf (text layer), .zip, or whole folders
python -m pokertracker report
python -m pokertracker tournament --html report.html   # latest tournament
python -m pokertracker dashboard --html dashboard.html
```

No exports yet? `python -m pokertracker demo-files demo/` writes 40 made-up tournaments (names start with "DEMO") in
GG's format; import them into a separate database with `python -m pokertracker --db sqlite:///demo.db import demo/`.
The app offers the same sample data from its empty dashboard, in its own `demo.db`.

Back up and restore the SQLite database from Settings → Backup in the app (a dated copy in Downloads; restoring keeps the current database next to itself first).

Re-importing the same files is safe: hands are deduplicated by hand id, summaries are upserted.
Files can arrive in any order (summary before hands, one file per entry, ...).
If PokerCraft offers the hands of a later day (Day 2) but not its summary, the event still counts, flagged as missing
the day's prize; `python -m pokertracker provisional <tournament id> <amount>` counts the cash won that day until the
summary is imported and replaces it.

## Desktop app

```bash
pip install -e ".[app]"          # adds pywebview for a native window
python -m pokertracker app       # or: pokertracker-app
python -m pokertracker app --browser   # same app in your default browser
```

The app runs a small server on `127.0.0.1` only; imports require a per-launch token.
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

The **Analysis** view looks at the whole history and writes tips from clear rules: leaks measured against a
baseline (e.g. calling from the big blind compared with folding there), strengths, and how much the ROI can still be
noise. Findings that do not stand out from chance are not shown.

In the app the dashboard covers the last session, 24 hours, 7 / 14 / 30 days, 3 / 6 months, the whole history or any
range: profit, ROI, the luck badge (how far all-in luck is from zero in "typical swings"), the cumulative result in $ or
BB, and a few lines worth knowing (best tournament, tickets, whether your play changed beyond noise).

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
- **Satellites**: tickets count at face value on both sides (a satellite won = the ticket's value, a target entered
  with a ticket = its full buy-in), so the total matches the cash flow; the cash-only ROI is shown under it.
- **Bounty formats**: buy-in split (prize + fee + bounty) kept; ROI uses the full cost including re-entries.

## Known limitations

**What it reads**
- GGPoker only, No-Limit Hold'em tournaments in dollars. Cash games, Sit & Go, PLO and other games, other currencies
  and freerolls are left out (the import says how many and why).
- Only what PokerCraft gives: hand histories of the last 90 days, about 10 tournaments per download. PDF exports need
  `pdftotext`.
- One player ("Hero") on one site.

**Installing**
- macOS: Apple Silicon only (no Intel build). Windows 10/11.
- The app is not signed: macOS asks for "Open Anyway", Windows SmartScreen for "Run anyway" (see the
  [install guide](docs/INSTALL.md)).
- Windows has not been checked by hand yet; the release build is smoke-tested on both systems in CI.

**What it can and cannot know**
- All-in EV and luck only for all-ins where every opponent's cards are known; others are left out, never guessed.
- Bounties are not split from the prize for the place (the summary gives one total), so ITM is unknown in bounty
  tournaments; knockouts in a split pot or a side pot count as shared.
- A later day (Day 2) without its summary counts a prize typed in by hand, marked as provisional, with the place
  unknown, until the summary is imported.
- The starting stack of a late registration can be unknown.
- Times are those in the GG files, and PokerCraft writes them in the time zone of the moment you **download** the export,
  not of when you played: an export downloaded after a daylight-saving change shows every hand about 1 hour off from one
  downloaded before it. Hands imported from exports on both sides of a change can then be about an hour apart in the
  time of day, in sessions, in "tournaments at once" and in the 15-minute tilt window. The order of hands within a
  tournament stays right (a tournament comes from one export). Times are not converted for now.
- Sessions: the blind level stands in for the stage of a tournament, roughly (structures differ in speed).

**Databases**
- Backup and restore in the app work with the SQLite database only; PostgreSQL users use `pg_dump`.

**Out of scope by decision**
- ICM / $EV, payout structures, HUD, solver / GTO analysis, cash games.

## Status

- Tested: parsers, importer, views, equity engine, classification, reports, replay, knockouts, background import and
  the HTTP API (unit tests + runs on real exports), on SQLite. PostgreSQL tests are included and run in CI.
- Packaged app: every release build is tested before upload on macOS and Windows (`tools/smoke_packaged.py`: clean
  profile, demo import twice with all-in EV, backup / restore, sample data, upgrade of an old database). The native
  window was checked by hand on macOS; a hand check on Windows is pending.

## Docs

- [Installing (for players)](docs/INSTALL.md)
- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Checkpoint checklist](docs/CHECKPOINT.md)
- [Changelog](CHANGELOG.md)

## License

[MIT](LICENSE) © 2026 Mikołaj Szcześniak. Free to use, change and share, with the copyright notice kept.
