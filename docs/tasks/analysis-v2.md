# Task: Analysis v2

Decisions by Mik (2026-10-11/12/13). Stage 0 (this document and a mockup on Mik's data) is approved before any code; then
stage 1 and stage 2, each its own PR, each with screenshots for approval before merge.

## Tabs
Przegląd | Preflop | Głębokość stacku | Leaki i mocne strony | Finanse (Finanse as today).

## Rules for every number
- Rates (VPIP, PFR, RFI, 3-bet, fold to 3-bet, open shove, ITM, cashed …): one decimal and n (the number of
  opportunities); ROI without decimals, with its 95 % interval where there is room.
- Fewer than 30 opportunities (or 10 tournaments): greyed, tooltip "za mało danych".
- Every metric has a plain-words definition in a tooltip and in Help, and a test on a GGPoker hand text.
- Results "wg EV": in a hand with an all-in, the all-in EV replaces the result (no luck).
- No reference ranges in the tables: typical ranges are solver patterns, and solver/GTO is out of scope. Context comes
  from Hero's own history (the trend, below).

## Definitions (PokerTracker 4 style; the denominator is the opportunities)
Accepted by Mik without changes (2026-10-13).

| Metric | Opportunity | Counted when |
|---|---|---|
| VPIP | a hand with a preflop decision (no walk, no all-in forced by a blind or ante) | call, bet or raise preflop (SB complete yes, BB check no) |
| PFR | same as VPIP | any raise preflop (limp-raise counts) |
| RFI | Hero's first decision with everyone before folded (no limpers), not in the BB | Hero raises (all-in included) |
| Open shove | an RFI opportunity | Hero's raise is all-in |
| 3-bet | exactly one raise before Hero's first decision (callers allowed: a squeeze counts) | Hero raises |
| Fold to 3-bet | Hero opened (not all-in) and exactly one re-raise followed | Hero folds |
| bb/100 wg EV | every hand | sum of EV results / hands × 100 |

## Stage 1
- **Przegląd**: tiles ROI (95 % bar with the zero line), ITM / cashed (place or bounty), VPIP, PFR, 3-bet,
  all-in EV, luck. "Where you finish" stays. Below the tiles, room for the showdown-lines chart
  (docs/tasks/showdown-lines.md, its own PR).
- **Trend** (decision 2026-10-13): the last 30 days against the rest of the history (not the whole history, so recent
  hands do not count on both sides). Only when the 30-day window has at least 500 hands; otherwise no trend at all.
  An arrow only at |z| ≥ 2.5 (two-proportion test on the opportunities), and at most one at a time: the largest |z|.
  On Mik's data today: 8,463 hands in the window, 1,740 before it; no change beyond noise (largest: 3-bet
  13.9 % vs 15.4 %, z = −1.05).
- **Preflop**: per position VPIP, PFR, RFI, 3-bet, fold to 3-bet, bb/100 wg EV, hands; a total row. BB has no RFI and
  no fold to 3-bet; UTG no 3-bet chance before it; BTN/SB is heads-up. Numbers only, no reference ranges.
- **Głębokość stacku**: the same per stack band (<10, 10–15, 15–25, 25–40, 40+ BB) plus open shove %, short stacks
  highlighted.
- Definitions in code with tests; computed in under 1 s for 10,000 hands.

## Stage 2
- **Leaki i mocne strony** as cards: title, plain explanation, value against the baseline, confidence (Benjamini-
  Hochberg over every spot), n, a mini-trend (cumulative EV over time), a tip, "Pokaż ręce" (the hands, with links to
  the replayer).
- **No significant leak** (decision 2026-10-13): the message "brak istotnych leaków" and a collapsed section
  "najbliżej progu" (a short list: spot, n, value, q), no cards.
- **Ręce startowe**: a 13×13 heatmap of the result wg EV per hand **against folding the same hand** (adding back the
  blind and ante posted, so hands usually folded are not red just for the blinds). The tooltip shows n; cells with
  fewer than 30 hands are greyed (the same 30 below which a cell is not tested). A click lists the hands.

## Order
Stage 0 → stage 1 → showdown lines (docs/tasks/showdown-lines.md) → all-in markers on the tournament stack chart
(colour by result, tooltip with cards, equity and luck in BB, click opens the replayer) → stage 2. Each a separate PR.

## Checks
800 px and 1100×820, light and dark, PL and EN; screenshots for approval before each merge; a summary of the results
on Mik's data at the end of each stage.
