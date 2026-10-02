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

## 4. Luck badge (inspired by PokerCraft, own design)
- Levels: Very lucky, Lucky, Average, Bad run, Worst run, and "No all-ins" when the period has none.
- Measured, not felt: z = total all-in luck / sqrt(sum of the variance of each all-in), variance of one all-in
  ≈ equity × (1 − equity) × pot². Thresholds e.g. ±0.5 and ±1.5. Show the number of all-ins and luck in BB next
  to it; with very few all-ins say the sample is small.
- "How luck works" explains the badge.

## 5. Best and worst starting hand
- Starting hand classes (e.g. J4s, QTo, 99) by result in BB over the period, with the number of hands.
- Minimum sample so a single hand does not win; "not enough hands yet" otherwise.

## 6. Strongest and weakest position
- Small table diagram with the positions; the best (bb/100) highlighted green, the worst red, with the numbers.
- Only positions with enough hands (same minimum as the tournament report).

## 7. Done when
- Tests for the period filter, ITM %, luck z-score and levels, best/worst hand and position selection.
- Checked visually in the running app (light/dark, 1100x820 and 380 px).
- CHANGELOG.md (Unreleased) updated; small commits; summary at the end.
