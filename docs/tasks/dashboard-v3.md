# Task: Dashboard v3

Accepted by Mik on the mockup (14.10.2026). Goal: 1.5–2 screens and fewer than 300 words; the details live in the
session screen, Analysis and Money.

## Layout, top to bottom
1. **Last session**, short: its first sentence, tournaments, profit and luck in BB, and a link to the session screen
   (`#/session`) with the hands to review. The full session (luck, against your usual play, hands to review, its
   tournaments) moved there, with the review list open.
2. **Period**: buttons and dates as in #36.
3. **Four tiles**: profit (cash part under it when tickets count), ROI (cost under it), tournaments (hands), luck (level
   and BB; z in the tooltip; "?" links to "How luck works").
4. **One line of smaller numbers**: ITM (where the files say it), top 15 % of the field, knockouts; the provisional note.
5. **One chart** with a switch: profit in $ or the result in BB (actual and without all-in luck, dashed); the choice
   is remembered per viewer.
6. **Worth knowing**, three facts at most: the best tournament of the period, tickets won (link to Money), and whether
   your play changed beyond noise (VPIP, PFR, 3-bet: the last 30 days against the rest, the Analysis trend).
7. **Recent tournaments**: five, with their names, linking to the tournament.

## Moved off the dashboard
- Best and worst starting hand, positions: Analysis (Preflop, starting-hand grid).
- The luck badge's long explanation: the tile's tooltip and "How luck works".
- Late registration against the start: Money (whole history, with the ITM columns and the incomplete-history note).
- The tickets table: Money (the dashboard keeps one line in Worth knowing).

## Checks
On Mik's data, 30 days: 1.35 screens and 111 words at 1100×820 (the old dashboard: 3 screens, 362 words), 1.72
screens at 800 px with nothing wider than the window. Light and dark, PL and EN.
