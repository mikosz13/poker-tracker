# Checkpoint on your Mac (step by step)

## 1. Get the code running
```bash
cd ~/Projects/poker-tracker          # wherever you unzipped it
python3 --version                    # needs 3.10+ (else: brew install python@3.12 and use python3.12)
python3 -m venv .venv
source .venv/bin/activate            # repeat in every new Terminal window
pip install -e ".[app]"
python -m unittest discover -s tests -t .    # expect: OK (skipped=2), the 2 are PostgreSQL-only
```

## 2. Use the app
```bash
python -m pokertracker app
```
Import → paste your PokerCraft export folder → Import. Then click around: Dashboard, Tournaments (filters),
a tournament, the replayer (arrow keys), "How luck works". Try "Watch this folder", export a new tournament, wait ~20 s.

## 3. Check against your memory
- Places, prizes and buy-ins match what GG shows?
- Late reg detected correctly (entry level)? Re-entries?
- Knockouts plausible? Biggest wins/losses are hands you remember?
- Anything confusing in the UI?

## 4. Put it on GitHub (turns on automatic tests and builds)
```bash
git init && git add . && git status   # make sure no exports or .db files are listed
git commit -m "Poker Tracker 0.2.0"
```
Create an empty repository on github.com and follow its "push an existing repository" commands.
Then in the Actions tab: "CI" runs by itself; "Build desktop app" → Run workflow → download the macOS and
Windows zips from the finished run.

## 5. Send back
Test output, any error message in full, import time for N tournaments, screenshots, and what looked wrong.

---

# Checkpoint 1 result (2026-10-02, MacBook Air, Apple Silicon)

## What was verified on the real machine
- Install from zip with Homebrew Python 3.12 and a venv: works.
- Test suite: `Ran 71 tests ... OK (skipped=2)` (the 2 skips are PostgreSQL-only). The ResourceWarnings printed
  during that run came from tests not closing in-memory databases; fixed in the next version, no effect on results.
- Desktop app (`python -m pokertracker app`) opens in the native window; the skeleton works, polish needed.

## Feedback from the first run
1. **Replayer must start at the first real decision (UTG).** Antes and blinds are always posted, so they are
   not steps: show them already in the pot when the replay starts.
2. **Replayer needs a table graphic**: an oval table with seats, stacks, cards, bets and the dealer button,
   and it should simply look good.
3. **Data download**: PokerCraft gave only the latest 10 tournaments when 221 were selected. GG states that
   hand histories from the last 90 days can be downloaded, so older history is lost if it is not exported in time.

## Open issues / unknowns
- PostgreSQL path only covered by the CI tests (not yet pushed to GitHub, so not run yet).
- Packaged .app / .exe not built yet (needs the GitHub push).
- Bounty money vs placement prize is not split, by decision; knockout counts are tracked.

## Next steps (in order)
1. Replayer v2: start at UTG with antes and blinds already in the pot; oval table with seats, stacks in BB,
   hole cards, bets in front of players, pot in the middle, dealer button; step controls and arrow keys.
2. Import in batches of 10 as a workaround for PokerCraft; keep exporting regularly because of the 90-day window.
3. UI polish pass over all screens.
4. Push to GitHub: CI (incl. PostgreSQL) and the macOS / Windows builds.
