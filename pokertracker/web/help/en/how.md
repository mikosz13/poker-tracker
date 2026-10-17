# How we count

## Analysis {#analysis}

Every rate is counted over its own chances, as PokerTracker 4 does, with n (the number of chances) under it; under 30 chances it is greyed.

- **VPIP**: you put chips in voluntarily preflop (call, bet, raise; completing the small blind counts, checking the big blind does not). Out of hands with a preflop decision: no walks, no all-in forced by the blind.
- **PFR**: you raise preflop (a limp-raise counts).
- **RFI**: you raise when everyone before you folded (no limpers); never in the big blind.
- **Open shove**: that raise is all-in; counted out of the RFI chances at the same stack.
- **3-bet**: exactly one raise came before your first decision (a squeeze counts), and you re-raise. An all-in you cannot raise over is not a chance; one for less than you have is (isolation).
- **Fold to 3-bet**: your open (not all-in) was re-raised once and you fold.
- **bb/100 by EV**: the result per 100 hands with the all-in EV in place of the result.

The **trend** compares the last 30 days with the rest of your history (500+ hands and 100+ chances on each side) and shows an arrow only beyond noise (|z| ≥ 2.5), one at a time.

**Leaks and strengths** test every spot by EV against a baseline (a call from the blinds against folding) and correct for all of them together: a card appears only at q ≤ 0.05. The closest spots are listed apart, still within chance. The **starting-hand grid** shows each hand by EV against folding it; grey under 30 hands. The **showdown lines** split your result into hands that reached showdown and the rest.

**Variance**: 10,000 runs of the next 100, 500 or 1,000 tournaments drawn from your own (bootstrap, results in buy-ins). It shows the typical result and the spread, the chance of a loss, the largest drawdown and how many buy-ins keep the risk of a bigger one under 5%; the “what if my ROI were” slider scales the prizes. It cannot see changes in your play, fields or structures; under 100 tournaments it says so clearly.

**Sessions**: VPIP, PFR, bb/100 by EV and ROI by the number of tournaments at once, the time of day and the time since the session started (a session ends after a break of more than 3 hours, as on the dashboard). Each group is compared with your other hands at the same stack depth, with the uncertainty counted by session, not by hand; only differences beyond noise are listed.

## Money {#money}

**ROI** counts tickets at face value on both sides: a satellite returns the seat's value, a tournament entered with a ticket costs its full buy-in, so the total matches the cash that moved; "cash part" leaves tickets out. Next to each ROI, a **95 % interval** (a bootstrap over your tournaments): where your long-run ROI probably lies. A group is called winning or losing only when the whole interval is above or below zero.

**ITM** (reached the paid places) is counted only where the files say it: tournaments without bounties, and satellites (a ticket is ITM). A bounty summary gives one total for place and knockouts, so bounty money counts in profit and ROI but not in ITM. **Top 10 % / 15 % of the field** are plain facts: your place over the number of players. A late registration flatters the place, so the late-reg table compares ROI.

## How luck is calculated {#luck}

{{luck}}
