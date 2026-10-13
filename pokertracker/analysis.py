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

from . import preflop
from .dashboard import hand_class, luck_badge, pending_results
from .i18n import num, t
from .places import place_split
from .tickets import tickets_summary
from .tournament_report import SITE

HIDE_BELOW = 30          # fewer hands than this: the spot is not tested
SMALL_BELOW = 100        # fewer hands than this: shown as a small sample
MIN_GROUP = 300          # stack depths and positions need this many hands to be tested
DEPTHS = ((0, 10, "<10 BB"), (10, 15, "10-15 BB"), (15, 25, "15-25 BB"), (25, 40, "25-40 BB"), (40, 10 ** 9, "40+ BB"))
FOLD_TO_3BET_DEPTHS = ((0, 20, "<20 BB"), (20, 40, "20-40 BB"), (40, 10 ** 9, "40+ BB"))
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
    # Hero at showdown: a showdown happened and Hero did not fold on any street (a called all-in always shows cards)
    folded = {r["hand_id"] for r in db.query(
        "SELECT DISTINCT a.hand_id FROM actions a JOIN hands h ON h.site = a.site AND h.hand_id = a.hand_id "
        f"WHERE a.site = ? AND a.nick = 'Hero' AND a.action_type = 'folds'{where}", (site, *args))}
    hands = []
    for r in db.query("SELECT hh.hand_id, hh.tournament_id, hh.played_at, hh.position, hh.stack_bb, hh.net_bb, "
                      "hh.big_blind, hh.decided, hh.vpip, hh.pfr, hp.hole_cards, ae.ev_net, h.showdown FROM hero_hands hh "
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
                      "posted_bb": posted / bb, "decided": int(r["decided"]), "vpip": int(r["vpip"]), "pfr": int(r["pfr"]),
                      "cards": r["hole_cards"] or "", "spot": first, "after_3bet": after,
                      "pf": preflop.hand_stats(a, r["position"]),
                      "showdown": bool(r["showdown"]) and r["hand_id"] not in folded})
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

DEPTH_TIPS = {"10-15 BB": "an.tip.depth10", "25-40 BB": "an.tip.depth25", "40+ BB": "an.tip.depth40"}
LINES = ("open", "3bet", "4bet_cold", "open_shove", "3bet_shove")    # titles: an.line.<spot>


def _versus_fold(key, played, lang):
    """A decision from a blind compared with folding in the same hand, which would have lost exactly the blind and
    ante Hero posted. The difference per hand is (EV-adjusted result + posted chips)."""
    if len(played) < HIDE_BELOW:
        return None
    mean, se = _mean_se([h["adj_bb"] + h["posted_bb"] for h in played])
    played_mean = sum(h["adj_bb"] for h in played) / len(played)
    fold_mean = -sum(h["posted_bb"] for h in played) / len(played)
    return {"key": key, "title": t(lang, f"an.t.{key}"), "kind": "vs_fold", "hands": len(played),
            "value": round(mean, 2), "z": mean / se if se else None, "played": round(played_mean, 2),
            "folded": round(fold_mean, 2), "cost_bb": round(-mean * len(played), 0),
            "gain_bb": round(mean * len(played), 0), "tip": t(lang, f"an.tip.{key}"), "worst": _worst(played)}


def spot_tests(hands, lang="en"):
    """Every spot checked, with its z score (negative = worse than the baseline). One family of tests."""
    tests = []
    by = defaultdict(list)
    for h in hands:
        by[(h["position"], h["spot"])].append(h)
    tests.append(_versus_fold("bb_defence", by[("BB", "call_vs_open")], lang))
    tests.append(_versus_fold("sb_complete", by[("SB", "limp")], lang))
    tests.append(_versus_fold("sb_flat", by[("SB", "call_vs_open")], lang))

    # folding after your own open was 3-bet: a frequency against a rough guide, by stack depth
    for lo, hi, label in FOLD_TO_3BET_DEPTHS:
        faced = [h for h in hands if h["spot"] == "open" and h["after_3bet"] and lo <= h["stack_bb"] < hi]
        if len(faced) < HIDE_BELOW:
            continue
        folds = [h for h in faced if h["after_3bet"] == "fold"]
        freq = len(folds) / len(faced)
        se = (FOLD_TO_3BET_HIGH * (1 - FOLD_TO_3BET_HIGH) / len(faced)) ** 0.5
        lost = -sum(h["adj_bb"] for h in folds) / len(folds) if folds else 0.0
        tests.append({"key": f"fold_to_3bet_{label}", "title": t(lang, "an.t.fold_to_3bet", depth=label),
                      "kind": "frequency", "hands": len(faced), "value": round(100 * freq, 1),
                      "z": -(freq - FOLD_TO_3BET_HIGH) / se,          # folding more than the guide is the bad side
                      "guide": t(lang, "an.guide.fold_to_3bet"),
                      "cost_bb": round(max(0.0, freq - FOLD_TO_3BET_GUIDE) * len(faced) * lost, 0), "gain_bb": 0,
                      "tip": t(lang, "an.tip.fold_to_3bet"),
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
            tests.append(group_test(f"depth_{label}", t(lang, "an.t.depth", depth=label), g,
                                    t(lang, DEPTH_TIPS.get(label, "an.tip.depth"))))
    for pos in sorted({h["position"] for h in hands if h["position"] and h["position"] not in UNRANKED_POSITIONS}):
        g = [h for h in hands if h["position"] == pos]
        if len(g) >= MIN_GROUP:
            tests.append(group_test(f"position_{pos}", t(lang, "an.t.position", pos=pos), g,
                                    t(lang, "an.tip.positionBTN" if pos == "BTN" else "an.tip.position")))
    classes = defaultdict(list)
    for h in hands:
        if k := hand_class(h["cards"]):
            classes[k].append(h)
    for k, g in sorted(classes.items()):
        if len(g) >= HIDE_BELOW:
            tests.append(group_test(f"hand_{k}", t(lang, "an.t.hand", hand=k), g, t(lang, "an.tip.hand"),
                                    kind="net_bb", vs_fold=True, side="leak"))   # winning with QQ is no praise
    for spot in LINES:
        g = [h for h in hands if h["spot"] == spot]
        if len(g) >= HIDE_BELOW:
            x = group_test(f"line_{spot}", t(lang, f"an.line.{spot}"), g, "", kind="net_bb", side="strength")
            x["praise"] = t(lang, "an.praise", n=len(g), bb=num(lang, x["gain_bb"], 0, sign=True),
                            per=num(lang, x["gain_bb"] / len(g), 2, sign=True))
            x["line"] = True
            tests.append(x)
    return [x for x in tests if x and x["z"] is not None]


def classify(tests, lang="en"):
    """Correct the whole family for multiple comparisons and split it into leaks and strengths."""
    q = benjamini_hochberg([p_value(x["z"], x.get("side", "two")) for x in tests])
    leaks, strengths = [], []
    for x, qi in zip(tests, q):
        conf = confidence_from_q(qi)
        if not conf:
            continue
        x = dict(x, q=round(qi, 4), z=round(x["z"], 2), confidence=conf, sample=_sample(x["hands"]))
        side = x.get("side", "two")
        if x["z"] < 0 and x["cost_bb"] > 0 and side != "strength":
            leaks.append(x)
        elif x["z"] > 0 and x["gain_bb"] >= 0 and side != "leak":
            text = x.get("praise") or t(lang, "an.strengthPer100", n=x["hands"],
                                        value=num(lang, x["value"], 1, sign=True))
            strengths.append({"key": x["key"], "title": x["title"], "hands": x["hands"], "sample": x["sample"],
                              "confidence": conf, "z": x["z"], "q": x["q"], "text": text, "value": x["gain_bb"]})
    leaks.sort(key=lambda x: (x["confidence"] != "likely", -x["cost_bb"]))
    strengths.sort(key=lambda x: (x["confidence"] != "likely", -x["value"]))
    return leaks, strengths


# ---- money -------------------------------------------------------------------------------------------------------

MIN_TOURNAMENTS = 10     # money groups with fewer tournaments are not judged
TIERS = ((0, 5, "under5"), (5, 15, "5-15"), (15, 30, "15-30"), (30, 10 ** 9, "30+"))    # labels: money.tier.<key>


def bootstrap_roi(pairs, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    """ROI of (cost, cash returned) pairs, one per tournament, with a 95 % percentile bootstrap interval and a
    two-sided bootstrap p-value for "ROI differs from zero" (twice the smaller share of resampled ROIs on one side of
    zero). Seeded, so it is reproducible."""
    n = len(pairs)
    cost = np.array([c for c, _ in pairs], dtype=float)
    ret = np.array([r for _, r in pairs], dtype=float)
    if n < 2 or cost.sum() <= 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(samples, n))
    c, r = cost[idx].sum(axis=1), ret[idx].sum(axis=1)
    keep = c > 0
    roi = 100 * (r[keep] - c[keep]) / c[keep]
    lo, hi = np.percentile(roi, [2.5, 97.5])
    p = min(1.0, max(2 * min(float((roi <= 0).mean()), float((roi >= 0).mean())), 1 / samples))
    return {"roi_pct": round(100 * (ret.sum() - cost.sum()) / cost.sum(), 1), "low": round(float(lo), 1),
            "high": round(float(hi), 1), "level": 95, "samples": samples, "p": p, "n": n}


def roi_interval(trs, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    """95 % bootstrap interval of the ROI over tournaments (cost includes re-entries)."""
    b = bootstrap_roi([(_f(t["total_cost"]), _f(t["total_cost"]) + _f(t["profit"])) for t in trs], samples, seed)
    return None if b is None else {k: b[k] for k in ("low", "high", "level", "samples")}


def _money_group(key, label, pairs, kind):
    cost = sum(c for c, _ in pairs)
    ret = sum(r for _, r in pairs)
    g = {"key": key, "label": label, "kind": kind, "tournaments": len(pairs), "cost": round(cost, 2),
         "returned": round(ret, 2), "profit": round(ret - cost, 2),
         "roi_pct": round(100 * (ret - cost) / cost, 1) if cost else None,
         "interval": None, "verdict_key": "too_few", "confidence": None}
    if len(pairs) >= MIN_TOURNAMENTS:
        g["boot"] = bootstrap_roi(pairs)
    return g


def money(db, site=SITE, lang="en"):
    """Money over the whole history, judged like the leaks: every group with enough tournaments is one test (its
    bootstrap p-value), the family is corrected with Benjamini-Hochberg, and only results beyond chance get a verdict.

    Re-entries: a re-entry is decided after the first entry busted, so without it the tournament would have returned
    nothing; the whole prize of a tournament with re-entries is the return of its re-entries. First entries return the
    prize only in tournaments without a re-entry (the first entry lasted to the end)."""
    trs = db.query("SELECT tournament_id, buyin_total, total_cost, cash_won, ticket_value, won_total, profit, "
                   "cash_profit, reentries, format, summary_missing, provisional FROM tournament_results WHERE site = ? "
                   "ORDER BY tournament_id",
                   (site,))                                # one fixed order: the seeded resampling picks the same rows
    cost = sum(_f(r["total_cost"]) for r in trs)
    profit = sum(_f(r["profit"]) for r in trs)                 # tickets at face value
    cash_profit = sum(_f(r["cash_profit"]) for r in trs)
    pair = lambda r: (_f(r["total_cost"]), _f(r["won_total"]))
    tiers = [_money_group(key, t(lang, f"money.tier.{key}"), [pair(r) for r in trs if lo <= _f(r["buyin_total"]) < hi],
                          "tier")
             for lo, hi, key in TIERS if any(lo <= _f(r["buyin_total"]) < hi for r in trs)]
    formats = []
    for fmt in sorted({r["format"] or "unknown" for r in trs}):
        g = [r for r in trs if (r["format"] or "unknown") == fmt]
        m = _money_group(fmt, t(lang, f"format.{fmt}"), [pair(r) for r in g], "format")
        m["tickets"] = round(sum(_f(r["ticket_value"]) for r in g), 2)       # the part of the return that is seats
        formats.append(m)
    first = _money_group("first", t(lang, "money.firstEntries"),
                         [(_f(r["buyin_total"]), 0.0 if int(r["reentries"] or 0) else _f(r["won_total"])) for r in trs],
                         "entries")
    re_entries = _money_group("re", t(lang, "money.reEntries"),
                              [(_f(r["buyin_total"]) * int(r["reentries"]), _f(r["won_total"]))
                               for r in trs if int(r["reentries"] or 0) > 0], "entries")

    family = [g for g in tiers + formats + [first, re_entries] if g.get("boot")]
    for g, q in zip(family, benjamini_hochberg([g["boot"]["p"] for g in family])):
        b = g.pop("boot")
        g["interval"] = {"low": b["low"], "high": b["high"], "level": 95}
        g["q"] = round(q, 4)
        g["confidence"] = confidence_from_q(q) if (b["high"] < 0 or b["low"] > 0) else None
        g["verdict_key"] = ("losing" if b["high"] < 0 else "winning") if g["confidence"] else "too_little"
    for g in tiers + formats + [first, re_entries]:
        g.pop("boot", None)
        g["verdict"] = t(lang, f"money.verdict.{g['verdict_key']}")
        g["share_of_spend_pct"] = round(100 * g["cost"] / cost, 1) if cost else None
        g["share_of_result_pct"] = round(100 * g["profit"] / profit, 1) if profit else None

    stacks = {r["kind"]: {"avg_bb": round(_f(r["bb"]), 1), "entries": int(r["n"])} for r in db.query(
        "SELECT CASE WHEN entry_no = 1 THEN 'first' ELSE 're' END AS kind, AVG(start_stack_bb) AS bb, COUNT(*) AS n "
        "FROM entries WHERE site = ? GROUP BY 1", (site,))}
    first["avg_start_bb"], re_entries["avg_start_bb"] = (stacks.get(k, {}).get("avg_bb") for k in ("first", "re"))
    return {"tournaments": len(trs), "cost": round(cost, 2), "profit": round(profit, 2),
            "roi_pct": round(100 * profit / cost, 1) if cost else None, "roi_interval": roi_interval(trs),
            "cash_profit": round(cash_profit, 2), "roi_cash_pct": round(100 * cash_profit / cost, 1) if cost else None,
            "pending": pending_results(trs),
            "tiers": tiers, "formats": formats, "first_entries": first, "re_entries": re_entries,
            "tested": len(family), "facts": money_facts(tiers, formats, first, re_entries, lang),
            "by_buyin": _rows_by(db, site, "buyin_total", "SELECT buyin_total AS key, COUNT(*) AS n, SUM(total_cost) AS cost, "
                                 "SUM(profit) AS profit, SUM(cashed) AS cashed FROM tournament_results WHERE site = ? "
                                 "GROUP BY buyin_total ORDER BY buyin_total"),
            "by_tag": _rows_by(db, site, "tag", "SELECT g.tag AS key, COUNT(*) AS n, SUM(r.total_cost) AS cost, "
                               "SUM(r.profit) AS profit, SUM(r.cashed) AS cashed FROM tournament_results r "
                               "JOIN tournament_tags g ON g.site = r.site AND g.tournament_id = r.tournament_id "
                               "WHERE r.site = ? AND g.tag NOT LIKE 'entry:%' GROUP BY g.tag ORDER BY g.tag"),
            "tickets": tickets_summary(db, site)}


def _rows_by(db, site, _key, sql):
    """Plain per-row results (whole history) for Money's detail tables: tournaments, cost, profit, ROI, cashed."""
    return [{"key": r["key"], "n": int(r["n"]), "cost": round(_f(r["cost"]), 2), "profit": round(_f(r["profit"]), 2),
             "roi_pct": round(100 * _f(r["profit"]) / _f(r["cost"]), 1) if _f(r["cost"]) else None,
             "cashed": int(r["cashed"] or 0), "cashed_pct": round(100 * int(r["cashed"] or 0) / int(r["n"]), 1)}
            for r in db.query(sql, (site,))]


def money_facts(tiers, formats, first, re_entries, lang="en"):
    """Facts, not advice, and only about groups judged beyond chance."""
    facts = []
    pct = lambda x, sign=False: num(lang, x, 0, sign) + "%"
    sig = sorted([g for g in tiers if g["confidence"]], key=lambda g: -g["share_of_spend_pct"])
    for i, g in enumerate(sig):
        facts.append(t(lang, "money.fact.tier" + ("Loses" if g["profit"] < 0 else "Wins"), label=g["label"],
                       share=pct(g["share_of_spend_pct"]))
                     + t(lang, "money.fact.biggest" if i == 0 else "money.fact.end"))
    for g in formats:
        if g["confidence"]:
            facts.append(t(lang, "money.fact.format" + ("Loses" if g["profit"] < 0 else "Wins"), Label=g["label"].capitalize(),
                           tournaments=t(lang, "common.tournaments", n=g["tournaments"]),
                           share=pct(g["share_of_spend_pct"])))
    if (first["confidence"] or re_entries["confidence"]) and first["roi_pct"] is not None:
        if re_entries["roi_pct"] is None:                              # no re-entries in the history
            facts.append(t(lang, "money.fact.noReentries", first=pct(first["roi_pct"], True)))
        else:
            facts.append(t(lang, "money.fact.entries", first=pct(first["roi_pct"], True),
                           re=pct(re_entries["roi_pct"], True), re_bb=num(lang, re_entries.get("avg_start_bb") or 0),
                           first_bb=num(lang, first.get("avg_start_bb") or 0)))
    return facts


def overview(hands, db, site=SITE):
    n = len(hands)
    a = db.query("SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(ev_bb) AS ev, SUM(luck_bb) AS luck FROM hero_allins "
                 "WHERE site = ?", (site,))[0]
    t = db.query("SELECT COUNT(*) AS n, SUM(cashed) AS cashed, SUM(in_the_money) AS itm, COUNT(in_the_money) AS itm_n, "
                 "SUM(CASE WHEN format = 'bounty' THEN cashed ELSE 0 END) AS cashed_b, "
                 "SUM(CASE WHEN format = 'bounty' THEN 1 ELSE 0 END) AS n_b FROM tournament_results WHERE site = ?",
                 (site,))[0]
    pct = lambda a, b: round(100 * int(a or 0) / int(b), 1) if int(b or 0) else None
    return {"hands": n, "tournaments": int(t["n"]),
            # ITM only without bounties; in bounty tournaments "cashed" (place or bounty) is what the files tell
            "itm": int(t["itm"] or 0), "itm_n": int(t["itm_n"] or 0), "itm_pct": pct(t["itm"], t["itm_n"]),
            "bounty_cashed": int(t["cashed_b"] or 0), "bounty_n": int(t["n_b"] or 0),
            "bounty_cashed_pct": pct(t["cashed_b"], t["n_b"]),
            "places": place_split(db, site),
            "decided": (d := sum(h["decided"] for h in hands)),
            "vpip_pct": round(100 * sum(h["vpip"] for h in hands) / d, 1) if d else None,
            "pfr_pct": round(100 * sum(h["pfr"] for h in hands) / d, 1) if d else None,
            "bb_per_100": round(100 * sum(h["net_bb"] for h in hands) / n, 1) if n else None,
            "bb_per_100_ev": round(100 * sum(h["adj_bb"] for h in hands) / n, 1) if n else None,
            "allins": {"count": int(a["n"]), "actual_bb": round(_f(a["net"]), 1), "ev_bb": round(_f(a["ev"]), 1),
                       "luck_bb": round(_f(a["luck"]), 1)},
            "luck_badge": luck_badge(db.query("SELECT equity, ev_bb, invested_bb, luck_bb FROM hero_allins WHERE site = ?",
                                              (site,)))}


SHOWDOWN_POINTS = 300    # the chart's points at most; the last hand is always one of them


def showdown_lines(hands, points=SHOWDOWN_POINTS):
    """Cumulative result in BB over the hands, split into hands Hero took to showdown and the rest (steals, uncalled
    shoves, pots given up, blinds and antes folded), plus the total with the all-in EV in place of the result.
    Total = with showdown + without showdown, exactly. Points: [hand number, date, total, showdown, no showdown, EV]."""
    total = sd = nsd = ev = 0.0
    step = max(1, math.ceil(len(hands) / points))
    out, count = [], 0
    for k, h in enumerate(hands, 1):
        total += h["net_bb"]
        ev += h["adj_bb"]
        if h["showdown"]:
            sd += h["net_bb"]
            count += 1
        else:
            nsd += h["net_bb"]
        if k % step == 0 or k == len(hands):
            out.append({"n": k, "at": h["at"], "total": round(total, 1), "sd": round(sd, 1), "nsd": round(nsd, 1),
                        "ev": round(ev, 1)})
    return {"hands": len(hands), "showdowns": count, "points": out,
            "final": {"total": round(total, 1), "sd": round(sd, 1), "nsd": round(nsd, 1), "ev": round(ev, 1)}}


def all_in_strength(db, site=SITE, lang="en"):
    """Not a test: the all-in EV is an expectation over every runout, so it is shown as a fact."""
    a = db.query("SELECT COUNT(*) AS n, SUM(ev_bb) AS ev FROM hero_allins WHERE site = ?", (site,))[0]
    if int(a["n"]) >= HIDE_BELOW and _f(a["ev"]) > 0:
        return {"key": "allin_ev", "title": t(lang, "an.t.allin_ev"), "hands": int(a["n"]),
                "sample": _sample(int(a["n"])), "confidence": None,
                "text": t(lang, "an.allinText", n=int(a["n"]), ev=num(lang, _f(a["ev"]), 0, sign=True)),
                "value": _f(a["ev"])}
    return None


def analysis_data(db, site=SITE, lang="en"):
    """The Analysis view: always the whole history. lang: the language of titles, tips and facts."""
    hands = load_hands(db, site)
    tests = spot_tests(hands, lang)
    leaks, strengths = classify(tests, lang)
    if (a := all_in_strength(db, site, lang)) is not None:
        strengths.insert(0, a)
    return {"overview": overview(hands, db, site), "leaks": leaks, "strengths": strengths,
            # Analysis v2: PT4-style rates over their opportunities, by position and stack depth, and the trend
            "showdown": showdown_lines(hands),
            "preflop": {"total": preflop.summarise(hands), "positions": preflop.by_position(hands),
                        "depths": preflop.by_depth(hands, DEPTHS), "trend": preflop.trend(hands),
                        "min_opp": preflop.MIN_OPP},
            "money": money(db, site, lang), "tested": len(tests),
            "thresholds": {"hide_below": HIDE_BELOW, "small_below": SMALL_BELOW,
                           "q_likely": Q_LIKELY, "q_possible": Q_POSSIBLE}}
