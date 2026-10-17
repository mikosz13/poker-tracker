"""When and how you play (pokertracker/play_context.py): tournaments at once, sessions, and tests that compare at the
same stack depth and count sessions, not hands."""
import unittest

from pokertracker import server
from pokertracker.db import Database
from pokertracker.demo import build_demo
from pokertracker.play_context import (MIN_TEST_SESSIONS, SESSION_GAP_HOURS, context_data, expected_test,
                                       session_hours, tables_at_once, _bands)


def hand(at, tid=1, stack=30.0, vpip=0, pfr=0, adj=0.0):
    return {"hand_id": f"{tid}-{at}", "tournament_id": tid, "at": at, "stack_bb": stack, "decided": 1, "vpip": vpip,
            "pfr": pfr, "adj_bb": adj}


class TimingTests(unittest.TestCase):
    def test_tournaments_running_at_each_hand(self):
        hands = [hand("2026-10-01 10:00", 1), hand("2026-10-01 10:10", 2), hand("2026-10-01 10:20", 1),
                 hand("2026-10-01 10:30", 2), hand("2026-10-01 10:40", 3)]
        # tournament 1: 10:00-10:20, 2: 10:10-10:30, 3: 10:40 only
        self.assertEqual(tables_at_once(hands), [1, 2, 2, 1, 1])   # at 10:30 the first one is over

    def test_a_break_longer_than_three_hours_starts_a_session(self):
        hands = [hand("2026-10-01 10:00"), hand("2026-10-01 12:30"), hand("2026-10-01 15:30"),   # 3 h: the same session
                 hand("2026-10-01 18:31")]                                                     # 3 h 1 min: a new one
        self.assertEqual(session_hours(hands), [(0, 0.0), (0, 2.5), (0, 5.5), (1, 0.0)])

    def test_the_same_session_rule_as_the_dashboard(self):
        self.assertEqual(SESSION_GAP_HOURS, server.SESSION_GAP_HOURS)


class ExpectedTests(unittest.TestCase):
    def rest(self):
        # the rest: deep stacks play 40 % of hands, short stacks 10 %
        out = []
        for i in range(1000):
            out.append(hand(f"r{i}", stack=50, vpip=int(i % 10 < 4)))
            out.append(hand(f"s{i}", stack=8, vpip=int(i % 10 < 1)))
        return out

    def test_a_short_stacked_group_is_compared_with_short_stacks(self):
        # a group of short stacks playing 10 %: far below the rest overall (25 %), exactly as expected for its stacks
        group = [hand(f"g{i}", stack=8, vpip=int(i % 10 < 1)) for i in range(500)]
        sessions = [i % 20 for i in range(500)]
        z, value, expected, n_sessions = expected_test("vpip", group, sessions, _bands(self.rest()))
        self.assertEqual((value, expected, n_sessions), (10.0, 10.0, 20))
        self.assertAlmostEqual(z, 0.0)

    def test_sessions_not_hands_carry_the_uncertainty(self):
        bands = _bands(self.rest())
        group = [hand(f"g{i}", stack=50, vpip=int(i % 10 < 5)) for i in range(600)]   # 50 % against 40 % expected
        few = expected_test("vpip", group, [i % (MIN_TEST_SESSIONS - 1) for i in range(600)], bands)
        self.assertIsNone(few)                                    # four evenings are not a habit
        # the same hands from 30 sessions, but each session either all in (+) or all out (-): strongly clustered
        clustered = [hand(f"c{i}", stack=50, vpip=int((i // 20) % 2 == 0)) for i in range(600)]
        z_clustered = expected_test("vpip", clustered, [i // 20 for i in range(600)], bands)[0]
        z_spread = expected_test("vpip", group, [i // 20 for i in range(600)], bands)[0]     # half in every session
        self.assertGreater(z_spread, 3)                            # a steady difference across sessions stands out
        self.assertLess(abs(z_clustered), 2.5)                     # a few all-or-nothing sessions do not

    def test_ev_against_the_band_means(self):
        rest = [hand(f"r{i}", stack=50, adj=(1.0 if i % 2 else -1.0)) for i in range(400)] + \
               [hand(f"s{i}", stack=8, adj=(3.0 if i % 2 else -5.0)) for i in range(400)]
        group = [hand(f"g{i}", stack=8, adj=(3.0 if i % 2 else -5.0)) for i in range(400)]
        z, value, expected, _ = expected_test("ev100", group, [i % 10 for i in range(400)], _bands(rest))
        self.assertEqual((value, expected), (-100.0, -100.0))     # short stacks lose 1 BB a hand here, as expected
        self.assertAlmostEqual(z, 0.0)


class ContextDataTests(unittest.TestCase):
    def test_on_the_demo_tournaments(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        build_demo(db, n=20, equity=False)
        c = context_data(db)
        self.assertEqual([d["key"] for d in c["dims"]], ["tables", "daypart", "session"])
        hands = db.scalar("SELECT COUNT(*) FROM hero_hands")
        for d in c["dims"]:
            self.assertEqual(sum(r["hands"] for r in d["rows"]), hands)
            self.assertEqual(sum(r["tournaments"] for r in d["rows"]), 20)     # every tournament in one group
        for f in c["findings"]:
            self.assertLessEqual(f["q"], 0.05)
        self.assertEqual(context_data(db, hands=[])["dims"], [])


if __name__ == "__main__":
    unittest.main()
