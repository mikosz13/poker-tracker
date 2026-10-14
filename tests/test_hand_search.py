"""Hand search (pokertracker/hand_search.py): every filter alone and together, paging, and the same hands as the
Analysis v2 counts."""
import unittest

from pokertracker import preflop
from pokertracker.analysis import load_hands
from pokertracker.db import Database
from pokertracker.hand_search import ACTIONS, search
from pokertracker.importer import exclude_tournament, import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY
from tests.test_analysis import gg_hand
from tests.test_preflop import CASES


class HandSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("sqlite:///:memory:")
        cls.db.init_schema()
        # tournament 910000: the preflop cases (no summary); 900001: HISTORY with its bounty summary ($10)
        import_texts(cls.db, [(name, gg_hand(i, hero, actions)) for i, (name, (hero, actions, _)) in
                              enumerate(CASES.items(), 1)] + [("h", HISTORY), ("b", SUMMARY_BOUNTY)])
        cls.all = search(cls.db, {}, limit=500)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def find(self, **f):
        return search(self.db, {k: str(v) for k, v in f.items()}, limit=500)

    def test_every_hand_once_newest_first(self):
        self.assertEqual(self.all["count"], len(CASES) + 3)
        times = [h["played_at"] for h in self.all["hands"]]
        self.assertEqual(times, sorted(times, reverse=True))
        self.assertEqual(self.all["ids"], [h["hand_id"] for h in self.all["hands"]])

    def test_the_same_hands_as_analysis_counts(self):
        t = preflop.summarise(load_hands(self.db))
        for action, key in (("rfi", "rfi"), ("open_shove", "shove"), ("threebet", "threebet"), ("fold_to_3bet", "fold3")):
            self.assertEqual(self.find(action=action)["count"], t[key]["count"], action)

    def test_each_filter(self):
        self.assertEqual(self.find(position="BB")["count"],
                         sum(1 for h in self.all["hands"] if h["position"] == "BB"))
        self.assertEqual(self.find(cards="AKo")["count"], len(CASES))         # gg_hand deals Ah Kd
        self.assertEqual(self.find(cards="KK,AA")["count"], 1)               # HISTORY's KK all-in
        self.assertEqual(self.find(buyin=10)["count"], self.all["count"])  # both are "$10" (from the name)
        self.assertEqual(self.find(buyin=5)["count"], 0)
        self.assertEqual(self.find(format="bounty")["count"], 3)
        self.assertEqual(self.find(stack_min=40, stack_max=60)["count"], len(CASES))   # 10,000 at 200: 50 BB
        self.assertEqual(self.find(all_in=1)["count"], len([h for h in self.all["hands"] if h["all_in"]]))
        self.assertGreaterEqual(self.find(all_in=1)["count"], 3)              # two open shoves and KK vs AA
        self.assertEqual(self.find(showdown=1)["count"] + self.find(showdown=0)["count"], self.all["count"])
        won, lost = self.find(result="won"), self.find(result="lost")
        self.assertTrue(all(h["net_bb"] > 0 for h in won["hands"]) and all(h["net_bb"] < 0 for h in lost["hands"]))
        self.assertTrue(all(abs(h["adj_bb"]) >= 50 for h in self.find(min_bb=50, ev=1)["hands"]))
        self.assertEqual(self.find(since="2026-02-01 00:00:00")["count"], len(CASES))
        self.assertEqual(self.find(until="2026-01-31 23:59:59")["count"], 3)

    def test_filters_together_and_empty(self):
        both = self.find(position="UTG", action="rfi")
        self.assertTrue(both["count"] > 0 and all(h["position"] == "UTG" for h in both["hands"]))
        self.assertEqual(self.find(position="BB", action="rfi")["count"], 0)            # the BB never raises first in
        self.assertEqual((self.find(cards="32s")["count"], self.find(cards="32s")["hands"]), (0, []))

    def test_paging(self):
        page = search(self.db, {}, offset=2, limit=3)
        self.assertEqual([h["hand_id"] for h in page["hands"]], self.all["ids"][2:5])
        self.assertEqual(page["count"], self.all["count"])

    def test_values_never_become_sql(self):
        self.assertEqual(self.find(cards="AKo') OR 1=1 --")["count"], 0)
        self.assertEqual(self.find(action="1=1; DROP TABLE hands")["count"], self.all["count"])   # unknown: ignored
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM hands"), self.all["count"])
        self.assertTrue(set(ACTIONS) >= {"rfi", "threebet", "fold_to_3bet", "open_shove"})

    def test_an_excluded_tournament_leaves_the_search(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY)], equity=False)
        self.assertEqual(search(db, {})["count"], 3)
        exclude_tournament(db, 900001, "ignored")
        self.assertEqual(search(db, {})["count"], 0)


if __name__ == "__main__":
    unittest.main()
