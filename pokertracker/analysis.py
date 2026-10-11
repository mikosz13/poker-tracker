"""Analysis view: leaks, strengths and money over the whole history, with built-in tips.

How a finding is made:
- Results are EV-adjusted: in a hand where Hero was all-in with cards to come, the all-in EV replaces the actual
  result, so a single lost or won coinflip does not create a "leak" or a "strength".
- Leaks are measured against a baseline, never as raw sums: a call from the blinds is compared with folding in the
  same hand, which loses exactly the blind and ante Hero posted; folding to 3-bets is a frequency.
- Every spot that is checked is one test. Their p-values are corrected together for multiple comparisons
  (Benjamini-Hochberg): "likely" at q <= 0.05, "possible" at q <= 0.20, otherwise nothing is shown.
- Every number carries its sample; reference ranges are rough guides, nothing comes from solvers.
"""
import math
from collections import defaultdict

import numpy as np

from .dashboard import hand_class
from .tournament_report import SITE

HIDE_BELOW = 30          # fewer hands than this: the spot is not tested
SMALL_BELOW = 100        # fewer hands than this: shown as a small sample
MIN_GROUP = 300          # stack depths and positions need this many hands to be tested
DEPTHS = ((0, 10, "<10 BB"), (10, 15, "10-15 BB"), (15, 25, "15-25 BB"), (25, 40, "25-40 BB"), (40, 10 ** 9, "40+ BB"))
FOLD_TO_3BET_DEPTHS = ((0, 20, "under 20 BB"), (20, 40, "20-40 BB"), (40, 10 ** 9, "40+ BB"))
FOLD_TO_3BET_HIGH = 0.70  # above this, opponents can 3-bet you with anything (rough guide)
FOLD_TO_3BET_GUIDE = 0.55  # roughly where solid players are; used only to size the leak
UNRANKED_POSITIONS = ("SB", "BB", "BTN/SB")
Q_LIKELY, Q_POSSIBLE = 0.05, 0.20
BOOTSTRAP_SAMPLES, BOOTSTRAP_SEED = 10_000, 20261011


def _f(x):
    return 0.0 if x is None else float(x)


def depth_label(stack_bb, depths=DEPTHS):
    return next(label for lo, hi, label in depths if lo <= stack_bb < hi)


def preflop_spots(actions):
    """Hero's preflop decisions in one hand, from its preflop actions in order (dicts nick, action_type, all_in).

    Returns (first, after_3bet): first is Hero's first voluntary spot, after_3bet Hero's answer when Hero's own open
    was re-raised ("fold", "call" or "4bet"), or None.
      raises before Hero  first decision        spot
      0                   raise / all-in        open / open_shove
      0                   call                  limp (complete in the small blind)
      0                   check (big blind)     bb_check
      0                   fold                  fold_unopened
      1                   call / raise / fold   call_vs_open / 3bet (3bet_shove) / fold_vs_open
      2+                  call / raise / fold   call_vs_3bet_cold / 4bet_cold / fold_vs_3bet_cold
    Two raises before Hero's first action are "cold" spots, never "folding to a 3-bet after your own open".
    """
    raises, first, opened = 0, None, False
    after = None
    for a in actions:
        t = a["action_type"]
        if t.startswith("posts"):
            continue
        if a["nick"] == "Hero":
            if first is None:
                all_in = bool(a["all_in"])
                if raises == 0:
                    first = {"raises": "open_shove" if all_in else "open", "calls": "limp", "checks": "bb_check",
                             "folds": "fold_unopened"}.get(t, t)
                    opened = t == "raises" and not all_in
                elif raises == 1:
                    first = {"calls": "call_vs_open", "raises": "3bet_shove" if all_in else "3bet",
                             "folds": "fold_vs_open"}.get(t, t)
                else:
                    first = {"calls": "call_vs_3bet_cold", "raises": "4bet_cold", "folds": "fold_vs_3bet_cold"}.get(t, t)
                raises_at_open = raises
            elif opened and after is None and raises > raises_at_open + 1:
                after = {"folds": "fold", "calls": "call", "raises": "4bet"}.get(t)
        if t in ("raises", "bets"):
            raises += 1
    return first, after


def load_hands(db, site=SITE, tournament_ids=None):
    """One row per hand Hero played: preflop spots, stack depth, the result in BB, the EV-adjusted result and the
    chips Hero posted (blind + ante) in BB. Optionally only some tournaments."""
    where, args = "", ()
    if tournament_ids is not None:
        ids = sorted(tournament_ids) or [-1]
        where, args = f" AND h.tournament_id IN ({', '.join('?' for _ in ids)})", tuple(ids)
    acts = defaultdict(list)
    # actions are filtered through the plain hands table: joining the hero_hands view (VPIP/PFR per row) is slow
    for a in db.query("SELECT a.hand_id, a.nick, a.action_type, a.amount, a.all_in FROM actions a "
                      "JOIN hands h ON h.site = a.site AND h.hand_id = a.hand_id "
                      f"WHERE a.site = ? AND a.street = 'preflop'{where} ORDER BY a.hand_id, a.action_order", (site, *args)):
        acts[a["hand_id"]].append(a)
    hands = []
    for r in db.query("SELECT hh.hand_id, hh.tournament_id, hh.played_at, hh.position, hh.stack_bb, hh.net_bb, "
                      "hh.big_blind, hh.vpip, hh.pfr, hp.hole_cards, ae.ev_net FROM hero_hands hh "
                      "JOIN hands h ON h.site = hh.site AND h.hand_id = hh.hand_id "
                      "JOIN hand_players hp ON hp.site = hh.site AND hp.hand_id = hh.hand_id AND hp.is_hero "
                      "LEFT JOIN allin_ev ae ON ae.site = hh.site AND ae.hand_id = hh.hand_id AND ae.is_hero "
                      f"WHERE hh.site = ?{where} ORDER BY hh.played_at, hh.hand_id", (site, *args)):
        a = acts.get(r["hand_id"], [])
        first, after = preflop_spots(a)
        bb = _f(r["big_blind"]) or 1.0
        posted = sum(_f(x["amount"]) for x in a if x["nick"] == "Hero" and x["action_type"].startswith("posts"))
        net = _f(r["net_bb"])
        hands.append({"hand_id": r["hand_id"], "tournament_id": r["tournament_id"], "at": str(r["played_at"])[:16],
                      "position": r["position"], "stack_bb": _f(r["stack_bb"]), "net_bb": net,
                      "adj_bb": _f(r["ev_net"]) / bb if r["ev_net"] is not None else net,
                      "posted_bb": posted / bb, "vpip": int(r["vpip"]), "pfr": int(r["pfr"]),
                      "cards": r["hole_cards"] or "", "spot": first, "after_3bet": after})
    return hands


# ---- statistics ------------------------------------------------------------------------------------------------

def _mean_se(values):
    n = len(values)
    if n == 0:
        return None, None
    mean = sum(values) / n
    if n < 2:
        return mean, None
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, (var / n) ** 0.5


def _group(hands, key="adj_bb"):
    mean, se = _mean_se([h[key] for h in hands])
    n = len(hands)
    return {"hands": n, "net_bb": round(sum(h[key] for h in hands), 1), "per_hand": round(mean, 2) if n else None,
            "bb_per_100": round(100 * mean, 1) if n else None, "se": se}


def p_value(z, side="two"):
    """p-value of a z score: two-sided, or one-sided when only one direction is a finding ("leak": z below zero is
    bad, "strength": z above zero is good)."""
    if side == "leak":
        return 0.5 * math.erfc(-z / math.sqrt(2))
    if side == "strength":
        return 0.5 * math.erfc(z / math.sqrt(2))
    return math.erfc(abs(z) / math.sqrt(2))


def benjamini_hochberg(pvalues):
    """q-values (adjusted p-values) for a family of tests, in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    q, running = [0.0] * m, 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        q[i] = running
    return q


def confidence_from_q(q):
    return "likely" if q <= Q_LIKELY else "possible" if q <= Q_POSSIBLE else None


def confidence(z):
    """Confidence of a single comparison from its z score (used where only one thing is compared, e.g. the session
    against your usual play): 'likely' beyond 2, 'possible' beyond 1."""
    if z is None:
        return None
    return "likely" if abs(z) >= 2 else "possible" if abs(z) >= 1 else None


def _sample(n):
    return "small" if n < SMALL_BELOW else "ok"


def _worst(hands, k=5):
    return [{"hand_id": h["hand_id"], "at": h["at"], "position": h["position"], "cards": h["cards"],
             "stack_bb": round(h["stack_bb"], 1), "net_bb": round(h["net_bb"], 1), "adj_bb": round(h["adj_bb"], 1)}
            for h in sorted(hands, key=lambda h: h["adj_bb"])[:k]]


# ---- the family of tested spots -------------------------------------------------------------------------------

DEPTH_TIPS = {
    "10-15 BB": "At 10-15 BB most hands should be all-in or fold. Avoid raising and folding, and avoid calling.",
    "25-40 BB": "At 25-40 BB re-shoving all-in over an open is often the best play. Calling and playing after the "
                "flop with this stack loses for you.",
    "40+ BB": "With a deep stack small edges after the flop decide. Review the biggest losses: were they one-pair hands "
              "paid off to the river?",
}
LINES = (("open", "Open raising"), ("3bet", "3-betting"), ("4bet_cold", "4-betting"), ("open_shove", "Open shoving"),
         ("3bet_shove", "Re-shoving all-in"))


def _versus_fold(key, title, played, tip):
    """A decision from a blind compared with folding in the same hand, which would have lost exactly the blind and
    ante Hero posted. The difference per hand is (EV-adjusted result + posted chips)."""
    if len(played) < HIDE_BELOW:
        return None
    mean, se = _mean_se([h["adj_bb"] + h["posted_bb"] for h in played])
    played_mean = sum(h["adj_bb"] for h in played) / len(played)
    fold_mean = -sum(h["posted_bb"] for h in played) / len(played)
    return {"key": key, "title": title, "kind": "vs_fold", "hands": len(played), "value": round(mean, 2),
            "z": mean / se if se else None, "played": round(played_mean, 2), "folded": round(fold_mean, 2),
            "cost_bb": round(-mean * len(played), 0), "gain_bb": round(mean * len(played), 0), "tip": tip,
            "worst": _worst(played)}


def spot_tests(hands):
    """Every spot checked, with its z score (negative = worse than the baseline). One family of tests."""
    tests = []
    by = defaultdict(list)
    for h in hands:
        by[(h["position"], h["spot"])].append(h)
    tests.append(_versus_fold(
        "bb_defence", "Big blind: calling an open", by[("BB", "call_vs_open")],
        "On average your calls from the big blind end worse than folding would have. Call less with offsuit hands "
        "that are easily dominated (e.g. KJo, QTo, A8o) against early positions, 3-bet your strongest hands instead "
        "of calling, and do not pay off to the river with one pair out of position."))
    tests.append(_versus_fold(
        "sb_complete", "Small blind: completing or limping", by[("SB", "limp")],
        "From the small blind you play out of position for the whole hand. Raise or fold instead of completing."))
    tests.append(_versus_fold(
        "sb_flat", "Small blind: calling an open", by[("SB", "call_vs_open")],
        "Calling from the small blind invites the big blind in and leaves you out of position. 3-bet or fold more."))

    # folding after your own open was 3-bet: a frequency against a rough guide, by stack depth
    for lo, hi, label in FOLD_TO_3BET_DEPTHS:
        faced = [h for h in hands if h["spot"] == "open" and h["after_3bet"] and lo <= h["stack_bb"] < hi]
        if len(faced) < HIDE_BELOW:
            continue
        folds = [h for h in faced if h["after_3bet"] == "fold"]
        freq = len(folds) / len(faced)
        se = (FOLD_TO_3BET_HIGH * (1 - FOLD_TO_3BET_HIGH) / len(faced)) ** 0.5
        lost = -sum(h["adj_bb"] for h in folds) / len(folds) if folds else 0.0
        tests.append({"key": f"fold_to_3bet_{label}", "title": f"Folding to 3-bets after your open ({label})",
                      "kind": "frequency", "hands": len(faced), "value": round(100 * freq, 1),
                      "z": -(freq - FOLD_TO_3BET_HIGH) / se,          # folding more than the guide is the bad side
                      "guide": "rough guide: around half; above 70 % opponents can 3-bet you with anything",
                      "cost_bb": round(max(0.0, freq - FOLD_TO_3BET_GUIDE) * len(faced) * lost, 0), "gain_bb": 0,
                      "tip": "You fold most of the time when your open is re-raised. Open a little tighter from early "
                             "positions so you have hands to continue with, and with 20-40 BB answer more 3-bets "
                             "with an all-in or a call.",
                      # one-sided: folding rarely is not praise (it can mean calling too much)
                      "side": "leak", "worst": _worst(folds)})

    def group_test(key, title, g, tip, kind="bb_per_100", vs_fold=False, side="two"):
        """vs_fold: measure against folding in the same hands (result + posted blind and ante), e.g. for hand types,
        which are mostly folded and would otherwise look bad just because the blinds are lost."""
        values = [h["adj_bb"] + (h["posted_bb"] if vs_fold else 0.0) for h in g]
        mean, se = _mean_se(values)
        total = sum(values)
        return {"key": key, "title": title, "kind": "vs_fold_total" if vs_fold else kind, "hands": len(g),
                "value": round(100 * mean, 1) if kind == "bb_per_100" else round(total, 1),
                "z": mean / se if se else None, "cost_bb": round(-total, 0), "gain_bb": round(total, 0),
                "tip": tip, "worst": _worst(g), "side": side}

    for label in [d[2] for d in DEPTHS]:
        g = [h for h in hands if depth_label(h["stack_bb"]) == label]
        if len(g) >= MIN_GROUP:
            tests.append(group_test(f"depth_{label}", f"Stack {label}", g,
                                    DEPTH_TIPS.get(label, "Review the biggest losses at this stack depth.")))
    for pos in sorted({h["position"] for h in hands if h["position"] and h["position"] not in UNRANKED_POSITIONS}):
        g = [h for h in hands if h["position"] == pos]
        if len(g) >= MIN_GROUP:
            tests.append(group_test(f"position_{pos}", f"Position {pos}", g,
                                    "The button should be your best seat. Fewer calls, more raises, and keep betting "
                                    "when checked to." if pos == "BTN" else "Play a little tighter from this seat."))
    classes = defaultdict(list)
    for h in hands:
        if k := hand_class(h["cards"]):
            classes[k].append(h)
    for k, g in sorted(classes.items()):
        if len(g) >= HIDE_BELOW:
            tests.append(group_test(f"hand_{k}", f"Starting hand {k}", g,
                                    "With this many hands a result depends mostly on a few big pots. Look at those "
                                    "pots: was it a dominated hand calling a raise?", kind="net_bb", vs_fold=True,
                                    side="leak"))                   # winning with QQ is no praise
    for spot, title in LINES:
        g = [h for h in hands if h["spot"] == spot]
        if len(g) >= HIDE_BELOW:
            t = group_test(f"line_{spot}", title, g, "", kind="net_bb", side="strength")
            t["praise"] = f"{t['gain_bb']:+,.0f} BB in {len(g)} hands ({t['gain_bb'] / len(g):+.2f} BB per hand)."
            t["line"] = True
            tests.append(t)
    return [t for t in tests if t and t["z"] is not None]


def classify(tests):
    """Correct the whole family for multiple comparisons and split it into leaks and strengths."""
    q = benjamini_hochberg([p_value(t["z"], t.get("side", "two")) for t in tests])
    leaks, strengths = [], []
    for t, qi in zip(tests, q):
        conf = confidence_from_q(qi)
        if not conf:
            continue
        t = dict(t, q=round(qi, 4), z=round(t["z"], 2), confidence=conf, sample=_sample(t["hands"]))
        side = t.get("side", "two")
        if t["z"] < 0 and t["cost_bb"] > 0 and side != "strength":
            leaks.append(t)
        elif t["z"] > 0 and t["gain_bb"] >= 0 and side != "leak":
            text = t.get("praise") or f"{t['value']:+.1f} bb/100 in {t['hands']} hands."
            strengths.append({"key": t["key"], "title": t["title"], "hands": t["hands"], "sample": t["sample"],
                              "confidence": conf, "z": t["z"], "q": t["q"], "text": text, "value": t["gain_bb"]})
    leaks.sort(key=lambda x: (x["confidence"] != "likely", -x["cost_bb"]))
    strengths.sort(key=lambda x: (x["confidence"] != "likely", -x["value"]))
    return leaks, strengths


# ---- money -------------------------------------------------------------------------------------------------------

def roi_interval(trs, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    """95 % interval of the ROI by bootstrap over tournaments (percentiles 2.5 and 97.5 of ROI = sum(profit) /
    sum(cost) in resamples of whole tournaments; cost includes re-entries). Seeded, so it is reproducible."""
    n = len(trs)
    if n < 2:
        return None
    cost = np.array([_f(t["total_cost"]) for t in trs])
    profit = np.array([_f(t["profit"]) for t in trs])
    if cost.sum() <= 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(samples, n))
    c, p = cost[idx].sum(axis=1), profit[idx].sum(axis=1)
    roi = 100 * p[c > 0] / c[c > 0]
    lo, hi = np.percentile(roi, [2.5, 97.5])
    return {"low": round(float(lo), 1), "high": round(float(hi), 1), "level": 95, "samples": samples}


def money(db, site=SITE):
    trs = db.query("SELECT tournament_id, buyin_total, total_cost, profit, reentries FROM tournament_results "
                   "WHERE site = ?", (site,))
    cost = sum(_f(t["total_cost"]) for t in trs)
    profit = sum(_f(t["profit"]) for t in trs)
    tiers = []
    for lo, hi, label in ((0, 5, "under $5"), (5, 15, "$5-15"), (15, 30, "$15-30"), (30, 10 ** 9, "$30+")):
        g = [t for t in trs if lo <= _f(t["buyin_total"]) < hi]
        if g:
            c, p = sum(_f(t["total_cost"]) for t in g), sum(_f(t["profit"]) for t in g)
            tiers.append({"tier": label, "tournaments": len(g), "cost": round(c, 2), "profit": round(p, 2),
                          "roi_pct": round(100 * p / c, 0) if c else None,
                          "share_of_spend_pct": round(100 * c / cost, 0) if cost else None})
    re = [t for t in trs if int(t["reentries"] or 0) > 0]
    extra = sum(_f(t["buyin_total"]) * int(t["reentries"] or 0) for t in re)
    return {"tournaments": len(trs), "cost": round(cost, 2), "profit": round(profit, 2),
            "roi_pct": round(100 * profit / cost, 1) if cost else None, "roi_interval": roi_interval(trs), "tiers": tiers,
            "reentries": {"tournaments": len(re), "extra_cost": round(extra, 2),
                          "profit": round(sum(_f(t["profit"]) for t in re), 2)}}


def overview(hands, db, site=SITE):
    n = len(hands)
    a = db.query("SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(ev_bb) AS ev, SUM(luck_bb) AS luck FROM hero_allins "
                 "WHERE site = ?", (site,))[0]
    t = db.query("SELECT COUNT(*) AS n, SUM(in_the_money) AS itm FROM tournament_results WHERE site = ?", (site,))[0]
    return {"hands": n, "tournaments": int(t["n"]),
            "itm_pct": round(100 * int(t["itm"] or 0) / int(t["n"]), 1) if int(t["n"]) else None,
            "vpip_pct": round(100 * sum(h["vpip"] for h in hands) / n, 1) if n else None,
            "pfr_pct": round(100 * sum(h["pfr"] for h in hands) / n, 1) if n else None,
            "bb_per_100": round(100 * sum(h["net_bb"] for h in hands) / n, 1) if n else None,
            "bb_per_100_ev": round(100 * sum(h["adj_bb"] for h in hands) / n, 1) if n else None,
            "allins": {"count": int(a["n"]), "actual_bb": round(_f(a["net"]), 1), "ev_bb": round(_f(a["ev"]), 1),
                       "luck_bb": round(_f(a["luck"]), 1)}}


def all_in_strength(db, site=SITE):
    """Not a test: the all-in EV is an expectation over every runout, so it is shown as a fact."""
    a = db.query("SELECT COUNT(*) AS n, SUM(ev_bb) AS ev FROM hero_allins WHERE site = ?", (site,))[0]
    if int(a["n"]) >= HIDE_BELOW and _f(a["ev"]) > 0:
        return {"key": "allin_ev", "title": "Getting it in good", "hands": int(a["n"]), "sample": _sample(int(a["n"])),
                "confidence": None, "text": f"Your all-ins are worth {_f(a['ev']):+,.0f} BB on average outcomes "
                                            f"({int(a['n'])} all-ins): you put the money in as the favourite.",
                "value": _f(a["ev"])}
    return None


def analysis_data(db, site=SITE):
    """The Analysis view: always the whole history."""
    hands = load_hands(db, site)
    tests = spot_tests(hands)
    leaks, strengths = classify(tests)
    if (a := all_in_strength(db, site)) is not None:
        strengths.insert(0, a)
    return {"overview": overview(hands, db, site), "leaks": leaks, "strengths": strengths, "money": money(db, site),
            "tested": len(tests), "thresholds": {"hide_below": HIDE_BELOW, "small_below": SMALL_BELOW,
                                                 "q_likely": Q_LIKELY, "q_possible": Q_POSSIBLE}}
