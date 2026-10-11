import json
import random
import unittest
from datetime import datetime

from pokertracker import session as S
from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.server import last_session, tournaments_list
from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY


def hand(vpip, pfr, net):
    return {"vpip": vpip, "pfr": pfr, "net_bb": net}


class VsUsualTests(unittest.TestCase):
    def setUp(self):
        random.seed(3)
        self.usual = S.totals([hand(int(random.random() < 0.3), int(random.random() < 0.2), random.gauss(0, 10))
                               for _ in range(3000)])

    def test_playing_many_more_hands_is_flagged(self):
        sess = [hand(int(random.random() < 0.6), int(random.random() < 0.2), random.gauss(0, 10)) for _ in range(200)]
        vpip = next(r for r in S.vs_usual(sess, self.usual) if r["stat"] == "VPIP")
        self.assertEqual(vpip["confidence"], "likely")
        self.assertGreater(vpip["session"], vpip["usual"])

    def test_usual_session_is_not_flagged(self):
        sess = [hand(int(random.random() < 0.3), int(random.random() < 0.2), random.gauss(0, 10)) for _ in range(200)]
        self.assertFalse([r for r in S.vs_usual(sess, self.usual) if r["confidence"] == "likely"])

    def test_too_few_session_hands(self):
        self.assertEqual(S.vs_usual([hand(1, 1, 0.0)] * (S.MIN_HANDS_VS_USUAL - 1), self.usual), [])


class NumbersTests(unittest.TestCase):
    def test_max_at_once(self):
        t = lambda h, m: datetime(2026, 1, 1, h, m)
        self.assertEqual(S.max_at_once([(t(10, 0), t(11, 0)), (t(10, 30), t(12, 0)), (t(11, 30), t(12, 30))]), 2)
        self.assertEqual(S.max_at_once([(t(10, 0), t(11, 0)), (t(11, 0), t(12, 0))]), 1)    # one ends, the next starts
        self.assertEqual(S.max_at_once([]), 0)

    def test_worth_a_look_weighs_equity_by_the_chips(self):
        busts = [{"equity": 0.70, "net_bb": -4.5, "rival_cards": "8d 3d", "hero_cards": "Js 8c", "name": "Small"},
                 {"equity": 0.69, "net_bb": -53.2, "rival_cards": "9d 6d", "hero_cards": "Js Jd", "name": "Big"}]
        text = S.summary_sentence([], {"luck": {"count": 0}, "busts": busts})
        self.assertIn("JJ vs 96s in Big", text)

    def test_short_hand_names(self):
        self.assertEqual([S._short(c) for c in ("Kh Kd", "As Qd", "As Qs", "7s")], ["KK", "AQo", "AQs", "7s"])


class SessionGroupingTests(unittest.TestCase):
    def t(self, tid, start, end):
        return {"tournament_id": tid, "first_hand": f"2026-01-01 {start}:00", "last_hand": f"2026-01-01 {end}:00"}

    def test_a_break_longer_than_the_gap_ends_the_session(self):
        from pokertracker.server import group_session
        ts = [self.t(1, "20:00", "22:00"), self.t(2, "16:00", "18:30"), self.t(3, "10:00", "12:00")]
        self.assertEqual([t["tournament_id"] for t in group_session(ts, gap_hours=3)], [1, 2])   # 1.5 h in, 4 h out

    def test_a_tournament_running_alongside_a_long_one_belongs(self):
        from pokertracker.server import group_session
        # A 10:00-18:00, B 16:00-17:00, C 11:00-12:00: C ran during A, so it is in the session although it ended
        # 4 h before B started
        ts = [self.t("A", "10:00", "18:00"), self.t("B", "16:00", "17:00"), self.t("C", "11:00", "12:00")]
        self.assertEqual([t["tournament_id"] for t in group_session(ts, gap_hours=3)], ["A", "B", "C"])

    def test_parallel_tournaments_are_counted_by_overlap(self):
        ts = [("10:00", "12:00"), ("11:00", "13:00"), ("11:30", "11:45"), ("13:00", "14:00")]
        t = lambda x: datetime(2026, 1, 1, int(x[:2]), int(x[3:]))
        self.assertEqual(S.max_at_once([(t(a), t(b)) for a, b in ts]), 3)               # 11:30-11:45: three at once


class UsualPlayTests(unittest.TestCase):
    def test_usual_play_leaves_the_session_out(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("t", HAND_3WAY)])          # 900001: 3 hands, 900003: 1 hand
        u = S.usual_play(db, {900003})
        self.assertEqual(u["n"], 3)                                     # only the other tournament's hands
        self.assertEqual(S.usual_play(db, {900001, 900003})["n"], 0)


class SessionInsightTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("t", HAND_3WAY)])

    def insights(self, tid):
        return S.session_insights(self.db, [t for t in tournaments_list(self.db) if t["tournament_id"] == tid])

    def test_bust_with_cards_equity_and_rival_by_position(self):
        i = self.insights(900001)                                       # entry 1 busts with KK against AA
        self.assertEqual(len(i["busts"]), 1)
        b = i["busts"][0]
        self.assertEqual((b["hand_id"], b["hero_cards"], b["rival"], b["rival_cards"]),
                         ("TM1000000002", "Kc Kd", "BTN/SB", "As Ad"))
        self.assertAlmostEqual(b["equity"], 0.18, delta=0.01)
        self.assertEqual(i["numbers"]["reentries"], 1)
        self.assertEqual(i["numbers"]["reentry_cost"], 10.0)
        self.assertEqual(i["numbers"]["knockouts"], 0)

    def test_summary_sentence(self):
        i = self.insights(900001)
        self.assertTrue(i["summary"].startswith("1 tournament, 1 in the money, +$0.00."), i["summary"])
        self.assertIn("Busted 1 time.", i["summary"])                   # an 18 % bust is not called a must-see

    def test_biggest_pots_and_no_opponent_ids(self):
        i = self.insights(900003)                                       # Hero wins the 3-way all-in with KK
        self.assertEqual([p["hand_id"] for p in i["pots"]["won"]], ["TM1000000010"])
        self.assertEqual(i["busts"], [])
        blob = json.dumps(i)
        for nick in ("aaaa1111", "bbbb2222", "cccc3333"):
            self.assertNotIn(nick, blob)

    def test_last_session_carries_the_insights(self):
        s = last_session(self.db)
        self.assertIn("insights", s)
        self.assertIn("summary", s["insights"])


if __name__ == "__main__":
    unittest.main()
