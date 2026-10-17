# Task: Variance (1.x)

Status: done 17.10.2026 (Analysis → Variance, pokertracker/variance.py). Decisions: horizons 100 / 500 / 1,000;
slider −20 … +50 % scaling prizes (losers stay at their cost); $ at the average buy-in of the last 30 tournaments;
at a losing ROI no bankroll number.

## What
- A simulation from Mik's own results: bootstrap over tournaments (profit in buy-ins, so different buy-ins compare),
  e.g. 10,000 runs of the next N tournaments.
- Shown:
  - the distribution of the result after N tournaments (median, 5–95 %);
  - the distribution of the largest drawdown (in buy-ins);
  - **how many buy-ins keep the risk of a drawdown of X under 5 %**;
  - a slider **co jeśli ROI**: the same distribution shifted to a chosen ROI;
  - ABI (average buy-in) over time.
- No bankroll entry; everything from the imported files.

## Rules
- Flag small samples: under 100 tournaments, a clear note that the simulation repeats the few results there are.
- Fixed seed, so the numbers do not change between visits; tests on a known small sample.
- Plain-words explanation in the app: what bootstrap means and what it cannot see (changes in skill, field,
  structure).
