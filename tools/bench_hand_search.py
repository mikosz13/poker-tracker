"""Benchmark of the hand search on synthetic hands (docs/tasks/hand-search.md): every filter combination of the list
below must answer in under 1 s on SQLite.

    python tools/bench_hand_search.py [hands]        (default 500,000; writes a temporary database)
"""
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pokertracker.db import Database                       # noqa: E402
from pokertracker.hand_search import COLUMNS, search       # noqa: E402

RANKS = "AKQJT98765432"
POSITIONS = ("UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB")
SPOTS = ("fold_unopened", "open", "limp", "call_vs_open", "fold_vs_open", "3bet", "bb_check", "open_shove")
COMBOS = [
    {}, {"position": "BTN"}, {"cards": "AA,KK,QQ"}, {"action": "threebet"}, {"action": "rfi", "position": "CO"},
    {"stack_min": "10", "stack_max": "15", "action": "open_shove"}, {"all_in": "1", "result": "lost", "ev": "1"},
    {"showdown": "1", "min_bb": "20"}, {"since": "2026-09-01 00:00:00", "position": "SB", "cards": "A5s"},
    {"buyin": "21.6", "format": "bounty", "action": "fold_to_3bet"},
    {"cards": "72o", "position": "BB", "stack_min": "40", "result": "won"},
]


def fill(db, n, seed=20261014):
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1)
    rows = []
    for i in range(n):
        a, b = rnd.randrange(13), rnd.randrange(13)
        cls = RANKS[a] * 2 if a == b else RANKS[min(a, b)] + RANKS[max(a, b)] + ("s" if rnd.random() < .25 else "o")
        spot = rnd.choice(SPOTS)
        net = round(rnd.gauss(-0.1, 6), 2)
        rows.append(("GGPoker", f"S{i:07d}", i // 120, start + timedelta(seconds=40 * i), "Bounty Hunters",
                     rnd.choice((5.4, 10.8, 21.6, 54.0)), rnd.choice(("bounty", "regular", "satellite")),
                     rnd.choice(POSITIONS), None, cls, round(rnd.uniform(3, 150), 2), spot,
                     int(spot in ("open", "open_shove")), int(spot == "open_shove"), int(spot == "3bet"),
                     int(spot == "open" and rnd.random() < .1), int(rnd.random() < .08), int(rnd.random() < .12),
                     net, round(net * 0.9, 2)))
        if len(rows) == 50_000:
            db.executemany(f"INSERT INTO hand_facts ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
            rows = []
    if rows:
        db.executemany(f"INSERT INTO hand_facts ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
    db.commit()


def main(n):
    with tempfile.TemporaryDirectory() as tmp, Database(f"sqlite:///{Path(tmp) / 'bench.db'}") as db:
        db.init_schema()
        t = time.time()
        fill(db, n)
        db.execute("ANALYZE")
        print(f"{n:,} synthetic hands written in {time.time() - t:.1f} s")
        worst = 0.0
        for f in COMBOS:
            t = time.time()
            r = search(db, f, limit=100)
            took = time.time() - t
            worst = max(worst, took)
            print(f"  {took * 1000:7.0f} ms  {r['count']:>8,}  {f}")
        print(f"slowest {worst * 1000:.0f} ms: {'OK' if worst < 1 else 'TOO SLOW'} (limit 1 s)")
        return 0 if worst < 1 else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 500_000))
