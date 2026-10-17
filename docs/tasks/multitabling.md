# Task: Multitabling and sessions (1.x)

Status: done 17.10.2026 (Analysis → Sessions, pokertracker/play_context.py). Decisions with Mik: hand times are local
time (the file names are UTC, two hours earlier in summer); a session ends after a 3 h break, as on the dashboard.
Added on the way: groups are compared at the same stack depth and counted by session (plain comparisons blamed the
clock for short stacks and one long evening).
Tilt (17.10.2026, decisions with Mik): three kinds of moment (an all-in lost with 60 %+ equity, a pot lost by 20+ BB,
a bust), a 15-minute window on every table, against the calm hands. Comparisons hold the stack band and the blind
level band (1-5, 6-10, 11-15, 16+) fixed: at the same stack only, "after a big loss" and "after a bust" showed a looser
VPIP, which disappeared at the same stage (the next hands after a bust are early levels of a new entry).

## What
- Results (bb/100 wg EV, ROI) and VPIP / PFR by:
  - the number of tournaments played at the same time (from overlapping hand times of different tournaments);
  - time of day;
  - session length (a session = hands with gaps under X minutes; X to fix with Mik).
- Conclusions only beyond noise (the same tests and BH correction as the leaks); otherwise "w granicach przypadku".
- Later together with a tilt detector (play after a big loss or a bust).

## Checked
- The time zone: hands and summaries share one clock (a tournament from the start has its first hand within seconds
  of "Tournament started"); GG's file names are exactly two hours earlier in all 11 files (UTC), and Mik confirmed
  15:30 on his clock for the hand at 15:30.
