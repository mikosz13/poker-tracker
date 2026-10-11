# Task: Analysis view

Context: read pokertracker/dashboard.py, pokertracker/sql/views.sql, pokertracker/replay.py and the dashboard part of
pokertracker/web/index.html first. Keep the stack: vanilla HTML/JS/CSS, no frameworks, no CDN, no new Python
dependencies. Decisions by Mik (2026-10-11):

- **Option A: built-in tips.** The app computes the numbers and writes the tips itself from clear rules, offline and
  tested. No AI calls, no export for AI.
- **Always the whole history.** The view ignores the dashboard period.
- **Leaks are measured against a baseline, never as raw sums.** A raw sum like "BB calls -784 BB" includes the blind
  that is lost anyway, and every fold is negative by definition. Compare with the alternative (call vs fold in the
  same spot) or use a frequency (fold to 3-bet 87 %), and say which.
- **Praise as well as leaks.** What works, with numbers.
- **"Flag, don't guess".** Every number shows its sample (hands, tournaments). A small sample is marked or the tip is
  not shown. Rough reference ranges are labelled as rough; nothing from solvers / GTO.

## 1. Overview
- Hands, tournaments, VPIP, PFR, bb/100, all-in EV vs actual and luck, ROI and ITM.

## 2. Leaks (sorted by cost)
- Big blind defence: result per call vs open compared with folding in the same spot.
- Fold to 3-bet: frequency after opening, by stack depth.
- Small blind completes / flats: per hand compared with folding.
- Stack depths and positions outside the blinds with a negative bb/100 and enough hands.
- Losing starting-hand classes (30+ hands).
- Each leak: the number, the baseline, the sample, a plain-words tip and "show the 5 worst hands" (replayer).

## 3. Strengths
- Profitable lines (open raise, 3-bet, 4-bet), positive all-in EV, profitable positions and depths, late reg vs start.

## 4. Money and variance
- Spend and result by buy-in tier, cost of re-entries, share of spend in the highest stakes.
- How much the ROI says at this sample: an error margin from the spread of tournament results.

## 5. Postflop (second PR)
- Flop c-bet, fold to c-bet, went to showdown (WTSD), won money at showdown (W$SD), postflop aggression.

## 6. Habits from the game (second PR)
- **Tilt detector.** Triggers: a lost pot of 20+ BB, a bad beat (lost all-in with 80 %+ equity), busting before a
  re-entry. Compare the next 20 hands with the usual play at a similar stack: VPIP, PFR, all-in frequency, bb/100.
  Flag only with enough triggers and hands; no difference is praise.
- Passive vs aggressive: calls vs raises before the flop and what each earns.
- Adapting to the stack: e.g. more shove-or-fold at 10-15 BB.
- Showdown habits: going to showdown often and winning rarely = paying too much after the flop.
- Trend per leak: last 4 weeks vs before (an extra column; the view still uses the whole history).

## 7. Done when
- Tests for every metric and every tip rule (baseline comparison, frequency, sample flags, tilt detector).
- Checked visually in the running app (light/dark, 1100x820 and 380 px).
- CHANGELOG.md (Unreleased) updated; small commits; summary at the end.
