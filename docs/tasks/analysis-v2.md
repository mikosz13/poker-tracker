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
Accepted by Mik (2026-10-13); the 3-bet chance was then refined for all-in raises (option 2, below).

| Metric | Opportunity | Counted when |
|---|---|---|
| VPIP | a hand with a preflop decision (no walk, no all-in forced by a blind or ante) | call, bet or raise preflop (SB complete yes, BB check no) |
| PFR | same as VPIP | any raise preflop (limp-raise counts) |
| RFI | Hero's first decision with everyone before folded (no limpers), not in the BB | Hero raises (all-in included) |
| Open shove | an RFI opportunity | Hero's raise is all-in |
| 3-bet | exactly one raise before Hero's first decision (callers allowed: a squeeze counts); not when that raise is all-in and Hero cannot raise over it (Hero's stack − ante ≤ the amount raised to: a call would put Hero all-in) | Hero raises |
| Fold to 3-bet | Hero opened (not all-in) and exactly one re-raise followed | Hero folds |
| bb/100 wg EV | every hand | sum of EV results / hands × 100 |

## Jak liczymy (how we count)
For the in-app "jak liczymy" text and Help; numbers from Mik's data (179 tournaments, 10,203 hands, to 11.10.2026).

- **Hands vs the VPIP/PFR denominator.** 10,203 hands, 10,124 with a preflop decision. The 79 left out are all hands
  where Hero had nothing to decide: 75 walks in the BB (everyone folded to Hero) and 4 hands where the ante and the
  blind took Hero's whole stack (Speed Racer [10 BB] and the like, stacks of 0.08–0.32 BB, in the SB, BTN/SB and
  BTN). No sit-outs among them: GGPoker folds a sitting-out player's hand, so such a hand shows as a fold and stays in
  the denominator (the hand text cannot tell it from a real fold).
  For stage 1: GGPoker writes no "and is all-in" on such a post (the stack simply equals ante + blind), so the
  `all_in` flag of the post is not set; those hands leave the denominator only because Hero has no decision. A test
  on this exact format goes with stage 1.
- **Stack depth** is Hero's stack at the start of the hand (the seat line, before ante and blind) in big blinds of
  that hand. Bands: < 10, 10–15, 15–25, 25–40, 40+ BB.
- **Open shove** counts per band from the RFI opportunities in that band, so each band has its own base:

  | Band | Base: RFI opportunities | Of hands in the band | Open shoves | Open shove |
  |---|---|---|---|---|
  | < 10 BB | 286 | 662 | 63 | 22.0 % |
  | 10–15 BB | 426 | 915 | 41 | 9.6 % |

  The tooltip says "z okazji RFI przy stacku X–Y BB" and the cell shows n, so 22.0 % (n = 286) and 9.6 % (n = 426)
  are not read as shares of all hands in the band, and the two bands are not compared as if they had one base.
- **3-bet facing an all-in raise** (decision 2026-10-13, option 2). A raise all-in is a 3-bet chance only when Hero
  can raise over it:
  - *Not a chance*: UTG shoves 9,975 (raise to 9,975); Hero in the BB has 10,000 and posted a 25 ante, so a call
    leaves Hero 0 chips. Hero can only call or fold.
  - *A chance (isolation)*: UTG is all-in for 4,200; Hero has 10,000, so Hero can re-raise to play the short stack
    alone. A re-raise counts as a 3-bet, a call or fold as a missed one.

  On Mik's data (11,446 hands, to 13.10.2026): 622 of the 4,878 chances faced an all-in raise; 472 of them Hero
  could raise over (48 3-bets among them: isolations, 39 all-in and 9 smaller raises), 150 not (0 raises, as it must
  be). The 150 leave the denominator:

  | | Chances (n) | 3-bets | 3-bet |
  |---|---|---|---|
  | before (any single raise) | 4,878 | 690 | 14.1 % |
  | after (option 2) | 4,728 | 690 | 14.6 % |

  Tests: `tests/test_preflop.py` (AllInRaiseTests).
- **In one sentence:** the mockup's 4,343 is the same definition on fewer hands (to 11.10, 10,203 hands), 4,878 is
  it on all 11,446 hands to 13.10 (the 1,243 newer hands add 535 chances), and 4,728 is 4,878 minus the 150 all-ins
  Hero could not raise over; none of the three numbers is wrong.
- **Why n changed from 4,343 (mockup) to 4,878.** The mockup used Mik's database up to 11.10.2026 00:07 (10,203
  hands); the app now has 11,446 hands to 13.10.2026. The 1,243 hands played since add 535 chances (4,343 + 535 =
  4,878, same definition); no hand counted before changed. With option 2 the mockup's data gives 4,195 (14.6 %).
- **Showdown lines**: see docs/tasks/showdown-lines.md (a called preflop all-in is a showdown; an uncalled shove is
  not).

## Significance (leaks, strengths, trends)
Checked before stage 1 (2026-10-13) on Mik's data.

**What the code does today** (pokertracker/analysis.py, `spot_tests` and `classify`): every spot is one test in one
family, and the whole family is corrected with Benjamini–Hochberg (q-values). On Mik's data the family has 156 tests:
134 cells of the 13×13 grid (the 35 cells with fewer than 30 hands are not tested), 5 stack bands, 6 positions,
5 lines (open, 3-bet, cold 4-bet, open shove, 3-bet shove), 3 blind decisions against folding and 3 fold-to-3-bet
bands. A card is "prawdopodobne" at q ≤ 0.05 and "możliwe" at q ≤ 0.20.

So the multiple comparisons are already accounted for, and it matters: without the correction 55 (p = 0.011), Q2s
(p = 0.015), 86o (p = 0.021) and 25–40 BB (p = 0.024) would each pass p < 0.05; with it their q is 0.59–0.63 and no
leak is shown. The strengths that pass are open shove (q < 0.001) and 3-bet shove (q = 0.039).

**Decided by Mik (2026-10-13): points 1–3 accepted; point 4 needs no change.**
1. Leak and strength cards only at q ≤ 0.05 (accepted). The "możliwe" level (q ≤ 0.20) accepts that up to one in five such
   cards is noise: too loose for a card that tells the player to change something. Spots with 0.05 < q ≤ 0.20 go to
   the collapsed "najbliżej progu" list with the rest.
2. (accepted) The heatmap colour is a description (the average per hand), not a finding; its tooltip says so ("kolor to
   średnia; o leaku decyduje test z korektą na wszystkie porównania").
3. The fold-to-3-bet leak today measures against a rough guide (folding more than 70 %). After decision 5 (no solver
   patterns) the guide goes (accepted): fold to 3-bet is compared with Hero's own history, like the trend, and a
   leak only when Hero folds more than before beyond noise.
4. Trends are a separate small family (the tiles with a trend: VPIP, PFR, 3-bet). |z| ≥ 2.5 is Bonferroni at 5 %
   two-sided for up to four statistics (z = 2.50), so Mik's threshold already covers it; no further correction.

## Stage 1
- **Przegląd**: tiles ROI (95 % bar with the zero line), ITM / cashed (place or bounty), VPIP, PFR, 3-bet,
  all-in EV, luck. "Where you finish" stays. Below the tiles, room for the showdown-lines chart
  (docs/tasks/showdown-lines.md, its own PR).
- **Trend** (decision 2026-10-13): the last 30 days against the rest of the history (not the whole history, so recent
  hands do not count on both sides). Only when both sides (the 30 days and the rest) have at least 500 hands, and for
  a rate at least 100 opportunities on each side (3-bet, fold to 3-bet have far fewer opportunities than hands; 100 is
  a proposal to confirm); otherwise no trend for that rate.
  An arrow only at |z| ≥ 2.5 (two-proportion test on the opportunities), and at most one at a time: the largest |z|.
  On Mik's data today: 8,463 hands in the window, 1,740 before it; no change beyond noise (largest: 3-bet
  13.9 % vs 15.4 %, z = −1.05).
- **Preflop**: per position VPIP, PFR, RFI, 3-bet, fold to 3-bet, bb/100 wg EV, hands; a total row. BB has no RFI and
  no fold to 3-bet; UTG no 3-bet chance before it; BTN/SB is heads-up. Numbers only, no reference ranges.
- **Głębokość stacku**: the same per stack band (<10, 10–15, 15–25, 25–40, 40+ BB) plus open shove %, short stacks
  highlighted; the open-shove base per band as in "Jak liczymy".
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
