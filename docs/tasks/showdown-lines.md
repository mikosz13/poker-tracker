# Task (sketch): Showdown lines

Queue: a small PR after Analysis v2 stage 1, before the all-in markers. Section **Przegląd** of Analiza (the mockup
already holds a preview on Mik's data).

## What
- One chart, cumulative result in BB over hands (x = hand number, dates in the tooltip):
  - **Łącznie**: every hand;
  - **Z showdownem**: hands where Hero reached showdown;
  - **Bez showdownu**: every other hand (steals, pots given up, blinds and antes lost by folding);
  - **Łącznie wg all-in EV** (dashed): the total with the all-in EV in place of the result in all-in hands.
- Legend with the final value of each line; a tooltip per line with its plain-words definition.

## Definitions
- Hero at showdown: a showdown happened and Hero did not fold. A called preflop all-in always counts as a showdown.
  An uncalled shove (everyone folded) is a steal: **bez showdownu** (to confirm with Mik).
- Sums in BB of each hand (net won / big blind), so different levels and tournaments add up.
- Totals: Łącznie = Z showdownem + Bez showdownu, exactly; tested.

## Checks
- Tests on GGPoker hand texts: showdown won, showdown lost, fold on the river after a showdown between others,
  preflop all-in called, all-in uncalled.
- Same period filter as the rest of Analiza; under 30 hands: no chart, a note instead.
- 800 px and 1100×820, light and dark, PL and EN; screenshots before merge.
