# Task: Dashboard v2

Context: read pokertracker/dashboard.py, the dashboard part of pokertracker/web/index.html, pokertracker/sql/views.sql
and pokertracker/server.py first. Keep the stack: vanilla HTML/JS/CSS, no frameworks, no CDN, no new Python
dependencies. Do docs/tasks/import-fixes.md first, so the dashboard shows correct numbers.

## 1. Period
- Selector: 24 h, 3 days, 1 week, 2 weeks, 4 weeks, 3 months, 6 months, Max. Counted back from now; tournaments
  by start time, hands by their time.
- Every number, chart and table on the dashboard uses the selected period. "Last session" stays as it is.
- The choice is remembered (settings table).

## 2. Charts with dates
- Cumulative cash profit in $ over time.
- Result in BB and luck-adjusted result in BB over time (the gap between them is luck).
- Date axis, labelled value axis, tooltip on hover/tap: date, tournament, values. Light and dark theme, phone width.

## 3. ITM in percent
- "In the money 44/131 · 33.6%" on the tile, an ITM % column in the buy-in, late-reg and category tables.

## 3a. Late registration vs start: leave out tournaments with an incomplete entry history
- Record in the data when a tournament's summary reports more entries (1 + re-entries) than were detected in the hand
  histories. No warning anywhere in the UI; entries still come from the hands and money from the summary.
- The "Late registration vs start" comparison leaves such tournaments out and says how many in a footnote, e.g.
  "N tournaments with an incomplete entry history left out".
- Test: a tournament whose summary reports more entries than the hands is recorded as such and is not counted in the
  late-reg vs start comparison; the footnote count matches.

## 4. Luck badge (inspired by PokerCraft, own design)
- Levels: Very lucky, Lucky, Average, Bad run, Worst run, and "No all-ins" when the period has none.
- Measured, not felt: z = total all-in luck / sqrt(sum of the variance of each all-in), variance of one all-in
  ≈ equity × (1 − equity) × pot². Thresholds e.g. ±0.5 and ±1.5. Show the number of all-ins and luck in BB next
  to it; with very few all-ins say the sample is small.
- "How luck works" explains the badge.

## 5. Best and worst starting hand
- Starting hand classes (e.g. J4s, QTo, 99) by result in BB over the period.
- Ranked only among hand classes with at least 30 hands. Every result shows its number of hands, the same way as the
  positions do.
- When no hand class reaches 30 hands in the period, say so plainly instead of showing a ranking.

## 6. Strongest and weakest position
- Small table diagram with the positions; the best (bb/100) highlighted green, the worst red, with the numbers.
- Only positions with enough hands (same minimum as the tournament report).

## 7. Done when
- Tests for the period filter, ITM %, luck z-score and levels, best/worst hand (30-hand minimum, the "not enough hands"
  case) and position selection, and for leaving incomplete-entry tournaments out of late reg vs start.
- Checked visually in the running app (light/dark, 1100x820 and 380 px).
- CHANGELOG.md (Unreleased) updated; small commits; summary at the end.
