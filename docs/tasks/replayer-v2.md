# Task: Replayer v2

Context: read CLAUDE.md, docs/CHECKPOINT.md, pokertracker/replay.py, the replayer part of pokertracker/web/index.html
and tests/test_replay.py first. Keep the stack: vanilla HTML/JS/CSS in index.html, no frameworks, no CDN (the app
works offline), no new Python dependencies.

## 1. Start at the first real decision
- Antes and blinds are always posted, so they are not steps. The first step shows them already in the pot
  (and taken from the stacks), with the first voluntary action (usually UTG) next to act.
- Chip accounting must stay exact: update tests/test_replay.py and add tests for the first step
  (pot = antes + blinds, stacks reduced), heads-up (BTN/SB acts first preflop) and a short stack whose ante or
  blind put them all-in.

## 2. Table graphic
- Oval felt table. Seats placed around it by seat number for the table size (8-max and 9-max both occur),
  rotated so Hero sits at the bottom centre.
- Each seat: nick (Hero highlighted), position label, stack in BB (chips on hover/tooltip), hole cards
  (Hero always; opponents face down until they show), the current street's bet in front of the player,
  folded players dimmed, an "ALL-IN" badge, the dealer button.
- Centre: board cards and the pot in BB (and chips).
- Cards readable at a glance: rank + suit symbol, red hearts/diamonds.

## 3. Controls and flow
- Previous / next, jump to start / end, autoplay with a speed choice, arrow keys (left/right), space = play/pause.
- Street indicator and a compact action log with the current step highlighted; clicking a log line jumps there.
- All-in runouts: deal the remaining board street by street; if the hand has an all-in EV row for Hero, show
  Hero's equity at the all-in moment. Show uncalled bets being returned and the final pot(s) paid out.

## 4. Look and feel
- Must simply look good: consistent with the rest of the app, light and dark theme, smooth but quick transitions.
- Works in the default window (1100x820) and down to 380 px wide.

## 5. Done when
- All tests pass; new tests cover the points in section 1.
- Checked visually in the running app on several hands: a normal hand, heads-up, a preflop all-in, a flop all-in
  with 3 players, a hand where Hero folds preflop. Screenshots or a short description of each.
- CHANGELOG.md (Unreleased) updated; small descriptive commits.
