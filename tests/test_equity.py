import itertools
import random
import unittest

import numpy as np

from pokertracker import equity as E
from pokertracker.db import Database
from pokertracker.hands import parse_hand
from pokertracker.importer import DbEquityCache, import_texts
from tests.fixtures import HAND_1, HAND_2, HAND_3, HAND_3WAY, HISTORY
from tests.refeval import ref7

c = E.parse_cards


def sgn(a, b):
    return (a > b) - (a < b)


class EvaluatorTests(unittest.TestCase):
    def test_all_five_card_hands_match_known_category_counts(self):
        idx = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(52), 5)),
                          dtype=np.int8, count=2598960 * 5).reshape(-1, 5)
        counts = np.zeros(9, dtype=np.int64)
        for s in range(0, len(idx), 500_000):
            counts += np.bincount(E.evaluate(idx[s:s + 500_000]) >> 20, minlength=9)
        self.assertEqual(counts.tolist(), [1302540, 1098240, 123552, 54912, 10200, 5108, 3744, 624, 40])

    def test_seven_card_hands_agree_with_independent_reference(self):
        rnd = random.Random(3)
        hands = [rnd.sample(range(52), 7) for _ in range(4000)]
        mine = [int(x) for x in E.evaluate(np.array(hands))]
        ref = [ref7(h) for h in hands]
        self.assertTrue(all((m >> 20) == r[0] for m, r in zip(mine, ref)))
        for _ in range(20000):
            i, j = rnd.randrange(len(hands)), rnd.randrange(len(hands))
            self.assertEqual(sgn(mine[i], mine[j]), sgn(ref[i], ref[j]))

    def test_edge_cases(self):
        cases = ["Ah 2d 3c 4s 5h 9d Kc", "Ah 2h 3h 4h 5h 9d Kc", "Ah Ad Ac Kh Kd Kc 2s", "Ah Ad Kh Kd Qh Qd 2s",
                 "Ah Ad Ac As Kh Kd Kc", "2h 3h 4h 5h 9h 6d 7c", "5h 6h 7h 8h 9h Ah 2h"]
        for s in cases:
            cs = c(s)
            self.assertEqual(int(E.evaluate(np.array([cs]))[0]) >> 20, ref7(cs)[0], s)

    def test_wheel_is_the_lowest_straight(self):
        wheel = int(E.evaluate(np.array([c("Ah 2d 3c 4s 5h 9d Kc")]))[0])
        six_high = int(E.evaluate(np.array([c("2h 3d 4c 5s 6h 9d Kc")]))[0])
        self.assertLess(wheel, six_high)


class EquityTests(unittest.TestCase):
    def test_exact_outs_count(self):
        # QhJh vs AsAd on 2h 7h Kc 3d: nine hearts win on the river, 44 unseen cards
        e = E.equity([c("Qh Jh"), c("As Ad")], c("2h 7h Kc 3d"))
        self.assertAlmostEqual(e[0], 9 / 44, places=12)

    def test_flop_all_in_matches_brute_force_with_reference_evaluator(self):
        holes, board = [c("Qh Jh"), c("As Ad")], c("2h 7h Kc")
        rest = [x for x in range(52) if x not in set(holes[0] + holes[1] + board)]
        tot = [0.0, 0.0]
        for run in itertools.combinations(rest, 2):
            a, b = ref7(holes[0] + board + list(run)), ref7(holes[1] + board + list(run))
            tot[0] += 1 if a > b else .5 if a == b else 0
            tot[1] += 1 if b > a else .5 if a == b else 0
        self.assertTrue(np.allclose([t / 990 for t in tot], E.equity(holes, board)))

    def test_preflop_known_matchups(self):
        aa_kk = E.equity([c("As Ah"), c("Kd Kc")])[0]
        self.assertTrue(0.805 < aa_kk < 0.82)                       # suit-specific; independent Monte Carlo: 81.3%
        self.assertGreater(E.equity([c("As Ah"), c("Ks Kh")])[0], aa_kk)   # AA blocks KK's flush outs
        aks_qq = E.equity([c("Ah Kh"), c("Qs Qd")])[0]
        self.assertTrue(0.45 < aks_qq < 0.47)

    def test_sums_to_one_and_symmetry(self):
        e3 = E.equity([c("As Ks"), c("Qh Qd"), c("Jc Jd")], c("2c 5d 9s"))
        self.assertAlmostEqual(sum(e3), 1.0, places=12)
        a = E.equity([c("As Ks"), c("Ah Kh")])
        self.assertAlmostEqual(a[0], a[1], places=12)

    def test_suit_relabelling_does_not_change_equity(self):
        e1 = E.equity([c("As Kd"), c("Qh Qs")], c("2c 7d 9h"))
        e2 = E.equity([c("Ah Ks"), c("Qc Qh")], c("2d 7s 9c"))     # same matchup, suits permuted
        self.assertTrue(np.allclose(e1, e2))
        self.assertEqual(E._canon([c("As Kd"), c("Qh Qs")], c("2c 7d 9h")),
                         E._canon([c("Ah Ks"), c("Qc Qh")], c("2d 7s 9c")))

    def test_side_pot_layers(self):
        pots = E.side_pots({"a": 100, "b": 300, "c": 300, "d": 50}, ["a", "b", "c"])
        self.assertEqual(pots, [(350, ("a", "b", "c")), (400, ("b", "c"))])


class AllInDetectionTests(unittest.TestCase):
    def test_no_all_in_means_no_lock(self):
        self.assertIsNone(E.find_lock(parse_hand(HAND_1)))
        self.assertIsNone(E.find_lock(parse_hand(HAND_3)))

    def test_preflop_call_of_a_shove_locks_preflop(self):
        street, live = E.find_lock(parse_hand(HAND_2))
        self.assertEqual((street, sorted(live)), ("preflop", ["Hero", "aaaa1111"]))

    def test_heads_up_preflop_all_in_ev(self):
        res = E.compute_allin(parse_hand(HAND_2), hero="Hero")
        hero = next(p for p in res["players"] if p["nick"] == "Hero")
        self.assertTrue(0.17 < hero["equity"] < 0.20)               # KcKd vs AsAd
        self.assertEqual((hero["net"], hero["result"]), (-4845, "lose"))
        pot = 9690
        self.assertAlmostEqual(hero["luck"], -pot * hero["equity"], places=6)   # lost the pot he owned `equity` of
        self.assertAlmostEqual(sum(p["luck"] for p in res["players"]), 0, places=6)

    def test_hero_filter(self):
        self.assertIsNone(E.compute_allin(parse_hand(HAND_2), hero="nobody"))

    def test_three_way_side_pot_matches_brute_force(self):
        hand = parse_hand(HAND_3WAY)
        res = E.compute_allin(hand, hero="Hero")
        self.assertEqual((res["street"], res["board_at_lock"]), ("flop", "2c 8d 9h"))
        holes = {"aaaa1111": c("7s 7d"), "bbbb2222": c("Ac Qd"), "Hero": c("Ks Kh")}
        board = c("2c 8d 9h")
        rest = [x for x in range(52) if x not in set(sum(holes.values(), []) + board)]
        expected = {n: 0.0 for n in holes}
        runs = list(itertools.combinations(rest, 2))
        for run in runs:
            sc = {n: ref7(h + board + list(run)) for n, h in holes.items()}
            for amount, eligible in ((3000, list(holes)), (4000, ["bbbb2222", "Hero"])):   # main pot, side pot
                best = max(sc[n] for n in eligible)
                winners = [n for n in eligible if sc[n] == best]
                for n in winners:
                    expected[n] += amount / len(winners) / len(runs)
        for p in res["players"]:
            self.assertAlmostEqual(p["ev_net"] + p["invested"], expected[p["nick"]], places=6, msg=p["nick"])
        self.assertAlmostEqual(sum(p["luck"] for p in res["players"]), 0, places=6)
        self.assertEqual({p["nick"]: p["result"] for p in res["players"]},
                         {"aaaa1111": "lose", "bbbb2222": "lose", "Hero": "win"})


class CacheAndImportTests(unittest.TestCase):
    def test_cache_is_used_and_returns_identical_values(self):
        class Spy(dict):
            sets = 0
            def get(self, k, d=None): return dict.get(self, k, d)
            def set(self, k, v):
                Spy.sets += 1
                self[k] = v
        spy = Spy()
        h = parse_hand(HAND_3WAY)
        first = E.compute_allin(h, cache=spy, hero="Hero")
        second = E.compute_allin(h, cache=spy, hero="Hero")
        self.assertEqual((Spy.sets, first), (1, second))

    def test_db_cache_roundtrip(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        cache = DbEquityCache(db)
        self.assertIsNone(cache.get("k"))
        cache.set("k", ((0.25, 0.75),))
        fresh = DbEquityCache(db)                                   # a new object must read it back from the table
        self.assertEqual(fresh.get("k"), ((0.25, 0.75),))

    def test_import_stores_all_in_ev_and_luck_views(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        s = import_texts(db, [("history", HISTORY), ("threeway", HAND_3WAY)])
        self.assertEqual(s.allins, 2)
        rows = db.query("SELECT * FROM hero_allins ORDER BY played_at")
        self.assertEqual([r["lock_street"] for r in rows], ["preflop", "flop"])
        pre = rows[0]
        self.assertAlmostEqual(float(pre["luck_bb"]), float(pre["luck"]) / 50, places=6)
        self.assertEqual(int(pre["bad_beat"]), 0)                    # KK was only ~18% there
        flop = rows[1]
        self.assertEqual(flop["result"], "win")
        self.assertGreater(float(flop["luck"]), 0)                   # won the pot while owning < 100% of it
        self.assertLess(float(flop["equity"]), 1.0)
        # re-importing must not duplicate anything
        import_texts(db, [("history", HISTORY), ("threeway", HAND_3WAY)])
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM allin_ev"), 5)   # 2 + 3 contestants
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM tournament_luck"), 2)


if __name__ == "__main__":
    unittest.main()


class ParallelTests(unittest.TestCase):
    def test_parallel_precompute_matches_serial(self):
        hands = [parse_hand(HAND_2), parse_hand(HAND_3WAY)]
        preps = [E.prepare_allin(h, hero="Hero") for h in hands]

        class Box(dict):
            def get(self, k, d=None): return dict.get(self, k, d)
            def set(self, k, v): self[k] = v

        parallel, serial = Box(), Box()
        self.assertEqual(E.precompute(preps, parallel, workers=2), 2)
        E.precompute(preps, serial, workers=1)
        self.assertEqual(set(parallel), set(serial))
        for k in parallel:
            self.assertTrue(np.allclose(np.array(parallel[k], dtype=object).tolist()[0], serial[k][0]))
        self.assertEqual(E.precompute(preps, parallel, workers=2), 0)          # everything cached now
        for h, prep in zip(hands, preps):                                       # compute_allin then hits the cache
            self.assertEqual(E.compute_allin(h, cache=parallel, prepared=prep), E.compute_allin(h, hero="Hero"))
