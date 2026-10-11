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
