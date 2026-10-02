"""Small synthetic fixtures in GGPoker's format (no real player data)."""

HAND_1 = """Poker Hand #TM1000000001: Tournament #900001, Bounty Hunters $10 Hold'em No Limit - Level1(25/50(5)) - 2026/01/01 10:00:00
Table '1' 9-max Seat #1 is the button
Seat 1: aaaa1111 (5,000 in chips)
Seat 2: bbbb2222 (5,000 in chips)
Seat 3: Hero (5,000 in chips)
aaaa1111: posts the ante 5
bbbb2222: posts the ante 5
Hero: posts the ante 5
bbbb2222: posts small blind 25
Hero: posts big blind 50
*** HOLE CARDS ***
Dealt to aaaa1111 
Dealt to bbbb2222 
Dealt to Hero [Ah Kh]
aaaa1111: raises 100 to 150
bbbb2222: folds
Hero: calls 100
*** FLOP *** [2c 7d Th]
Hero: checks
aaaa1111: bets 200
Hero: folds
Uncalled bet (200) returned to aaaa1111
aaaa1111 collected 340 from pot
*** SUMMARY ***
Total pot 340 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2c 7d Th]
Seat 1: aaaa1111 (button) collected (340)
Seat 2: bbbb2222 (small blind) folded before Flop
Seat 3: Hero (big blind) folded on the Flop
"""

HAND_2 = """Poker Hand #TM1000000002: Tournament #900001, Bounty Hunters $10 Hold'em No Limit - Level1(25/50(5)) - 2026/01/01 10:05:00
Table '1' 9-max Seat #1 is the button
Seat 1: aaaa1111 (5,185 in chips)
Seat 3: Hero (4,845 in chips)
aaaa1111: posts the ante 5
Hero: posts the ante 5
aaaa1111: posts small blind 25
Hero: posts big blind 50
*** HOLE CARDS ***
Dealt to aaaa1111 
Dealt to Hero [Kc Kd]
aaaa1111: raises 5,155 to 5,180 and is all-in
Hero: calls 4,790 and is all-in
Uncalled bet (340) returned to aaaa1111
aaaa1111: shows [As Ad]
Hero: shows [Kc Kd]
*** FLOP *** [2h 7d 9c]
*** TURN *** [2h 7d 9c] [3s]
*** RIVER *** [2h 7d 9c 3s] [Jd]
*** SHOWDOWN ***
aaaa1111 collected 9,690 from pot
*** SUMMARY ***
Total pot 9,690 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2h 7d 9c 3s Jd]
Seat 1: aaaa1111 (button) (small blind) showed [As Ad] and won (9,690)
Seat 3: Hero (big blind) showed [Kc Kd] and lost
"""

# Hero busted in hand 2 and is back with a fresh stack: a re-entry
HAND_3 = """Poker Hand #TM1000000003: Tournament #900001, Bounty Hunters $10 Hold'em No Limit - Level1(25/50(5)) - 2026/01/01 10:20:00
Table '2' 9-max Seat #1 is the button
Seat 1: cccc3333 (7,000 in chips)
Seat 3: Hero (5,000 in chips)
cccc3333: posts the ante 5
Hero: posts the ante 5
cccc3333: posts small blind 25
Hero: posts big blind 50
*** HOLE CARDS ***
Dealt to cccc3333 
Dealt to Hero [7c 2d]
cccc3333: folds
Uncalled bet (25) returned to Hero
Hero collected 60 from pot
*** SUMMARY ***
Total pot 60 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 1: cccc3333 (button) (small blind) folded before Flop
Seat 3: Hero (big blind) collected (60)
"""

# GG exports newest first, with blank lines between hands
HISTORY = "\n\n".join([HAND_3, HAND_2, HAND_1])

SUMMARY_BOUNTY = """Tournament #900001, Bounty Hunters $10, Hold'em No Limit
Buy-in: $4.50+$0.50+$5
50 Players
Total Prize Pool: $225
Tournament started 2026/01/01 09:00:00 
3rd : Hero, $20
You finished the tournament in 3rd place.
You made 1 re-entries and received a total of $20.
"""

SUMMARY_SATELLITE = """Tournament #900002, $5 Satellite to #1: Big Event, 20 Seats, Hold'em No Limit
Buy-in: $4.50+$0.50
100 Players
Total Prize Pool: $450
Tournament started 2026/01/02 09:00:00 
5th : Hero, $50 Entry
You finished the tournament in 5th place.
You received a total of $50 Entry.
"""

# Three-way all-in on the flop with a side pot: aaaa1111 is short (1,000), bbbb2222 and Hero cover each other (3,000)
HAND_3WAY = """Poker Hand #TM1000000010: Tournament #900003, Bounty Hunters $10 Hold'em No Limit - Level1(25/50(5)) - 2026/01/03 10:00:00
Table '1' 9-max Seat #1 is the button
Seat 1: aaaa1111 (1,000 in chips)
Seat 2: bbbb2222 (3,000 in chips)
Seat 3: Hero (3,000 in chips)
aaaa1111: posts the ante 5
bbbb2222: posts the ante 5
Hero: posts the ante 5
bbbb2222: posts small blind 25
Hero: posts big blind 50
*** HOLE CARDS ***
Dealt to aaaa1111 
Dealt to bbbb2222 
Dealt to Hero [Ks Kh]
aaaa1111: calls 50
bbbb2222: calls 25
Hero: checks
*** FLOP *** [2c 8d 9h]
bbbb2222: bets 100
Hero: raises 2,845 to 2,945 and is all-in
aaaa1111: calls 945 and is all-in
bbbb2222: calls 2,845 and is all-in
aaaa1111: shows [7s 7d]
bbbb2222: shows [Ac Qd]
Hero: shows [Ks Kh]
*** TURN *** [2c 8d 9h] [Jc]
*** RIVER *** [2c 8d 9h Jc] [3s]
*** SHOWDOWN ***
Hero collected 3,000 from pot
Hero collected 4,000 from pot
*** SUMMARY ***
Total pot 7,000 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2c 8d 9h Jc 3s]
Seat 1: aaaa1111 (button) showed [7s 7d] and lost
Seat 2: bbbb2222 (small blind) showed [Ac Qd] and lost
Seat 3: Hero (big blind) showed [Ks Kh] and won (7,000)
"""

# 8-max, a 8-chip stack is all-in on the ante; the SB folds, Hero's uncalled 50 comes back and Hero wins at showdown
HAND_SHORT = """Poker Hand #TM1000000020: Tournament #900004, Bounty Hunters $10 Hold'em No Limit - Level3(50/100(10)) - 2026/01/04 10:00:00
Table '1' 8-max Seat #2 is the button
Seat 2: dddd4444 (8 in chips)
Seat 4: eeee5555 (2,000 in chips)
Seat 6: Hero (3,000 in chips)
dddd4444: posts the ante 8 and is all-in
eeee5555: posts the ante 10
Hero: posts the ante 10
eeee5555: posts small blind 50
Hero: posts big blind 100
*** HOLE CARDS ***
Dealt to dddd4444 
Dealt to eeee5555 
Dealt to Hero [Qs Qh]
eeee5555: folds
Uncalled bet (50) returned to Hero
dddd4444: shows [9c 4d]
Hero: shows [Qs Qh]
*** FLOP *** [2c 7d Th]
*** TURN *** [2c 7d Th] [3s]
*** RIVER *** [2c 7d Th 3s] [Kd]
*** SHOWDOWN ***
Hero collected 104 from pot
Hero collected 24 from pot
*** SUMMARY ***
Total pot 128 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2c 7d Th 3s Kd]
Seat 2: dddd4444 (button) showed [9c 4d] and lost
Seat 4: eeee5555 (small blind) folded before Flop
Seat 6: Hero (big blind) showed [Qs Qh] and won (128)
"""
