"""Analysis view: leaks, strengths and money over the whole history, with built-in tips.

Leaks are measured against a baseline, never as raw sums: a call from the big blind is compared with folding in the
same spot (the blind is lost either way), and folding to 3-bets is a frequency. Every number carries its sample; with
too few hands a finding is not shown, and with few it is marked as a small sample. Reference ranges are rough guides.
"""
from collections import defaultdict

from .dashboard import hand_class
from .tournament_report import SITE

HIDE_BELOW = 30          # fewer hands than this: the finding is not shown
SMALL_BELOW = 100        # fewer hands than this: shown as a small sample
DEPTHS = ((0, 10, "<10 BB"), (10, 15, "10-15 BB"), (15, 25, "15-25 BB"), (25, 40, "25-40 BB"), (40, 10 ** 9, "40+ BB"))
FOLD_TO_3BET_DEPTHS = ((0, 20, "under 20 BB"), (20, 40, "20-40 BB"), (40, 10 ** 9, "40+ BB"))
FOLD_TO_3BET_HIGH = 0.70  # above this, opponents can 3-bet you with anything (rough guide)
FOLD_TO_3BET_GUIDE = 0.55  # roughly where solid players are; used only to size the leak
UNRANKED_POSITIONS = ("SB", "BB", "BTN/SB")


def _f(x):
    return 0.0 if x is None else float(x)


def depth_label(stack_bb, depths=DEPTHS):
    return next(label for lo, hi, label in depths if lo <= stack_bb < hi)


def preflop_spots(actions):
    """Hero's preflop decisions in one hand, from its preflop actions in order (dicts nick, action_type, all_in).

    Returns (first, after_3bet): first is Hero's first voluntary spot, after_3bet Hero's answer when an open was
    3-bet ("fold", "call" or "4bet"), or None.
      raises before Hero  first decision        spot
      0                   raise / all-in        open / open_shove
      0                   call                  limp (sb_complete in the small blind)
      0                   check (big blind)     bb_check
      0                   fold                  fold_unopened
      1                   call / raise / fold   call_vs_open / 3bet (3bet_shove) / fold_vs_open
      2+                  call / raise / fold   call_vs_3bet_cold / 4bet_cold / fold_vs_3bet_cold
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


def load_hands(db, site=SITE):
    """One row per hand Hero played, with the preflop spots, stack depth and result in BB."""
    acts = defaultdict(list)
    for a in db.query("SELECT hand_id, nick, action_type, all_in FROM actions WHERE site = ? AND street = 'preflop' "
                      "ORDER BY hand_id, action_order", (site,)):
        acts[a["hand_id"]].append(a)
    hands = []
    for r in db.query("SELECT hh.hand_id, hh.tournament_id, hh.played_at, hh.position, hh.stack_bb, hh.net_bb, "
                      "hh.vpip, hh.pfr, hp.hole_cards FROM hero_hands hh JOIN hand_players hp "
                      "ON hp.site = hh.site AND hp.hand_id = hh.hand_id AND hp.is_hero WHERE hh.site = ? "
                      "ORDER BY hh.played_at, hh.hand_id", (site,)):
        first, after = preflop_spots(acts.get(r["hand_id"], []))
        hands.append({"hand_id": r["hand_id"], "tournament_id": r["tournament_id"], "at": str(r["played_at"])[:16],
                      "position": r["position"], "stack_bb": _f(r["stack_bb"]), "net_bb": _f(r["net_bb"]),
                      "vpip": int(r["vpip"]), "pfr": int(r["pfr"]), "cards": r["hole_cards"] or "",
                      "spot": first, "after_3bet": after})
    return hands


def _group(hands):
    n = len(hands)
    net = sum(h["net_bb"] for h in hands)
    mean = net / n if n else 0.0
    var = sum((h["net_bb"] - mean) ** 2 for h in hands) / (n - 1) if n > 1 else 0.0
    return {"hands": n, "net_bb": round(net, 1), "per_hand": round(mean, 2) if n else None,
            "bb_per_100": round(100 * mean, 1) if n else None, "se": (var / n) ** 0.5 if n > 1 else None}


def confidence(z):
    """How sure a finding is, from z = result / standard error: 'likely' beyond 2, 'possible' beyond 1, else None.

    Poker results swing a lot from hand to hand, so most differences within one standard error are just chance.
    """
    if z is None:
        return None
    return "likely" if abs(z) >= 2 else "possible" if abs(z) >= 1 else None


def _z(value, se):
    return value / se if se else None


def _sample(n):
    return "hidden" if n < HIDE_BELOW else "small" if n < SMALL_BELOW else "ok"


def _worst(hands, k=5):
    return [{"hand_id": h["hand_id"], "at": h["at"], "position": h["position"], "cards": h["cards"],
             "stack_bb": round(h["stack_bb"], 1), "net_bb": round(h["net_bb"], 1)}
            for h in sorted(hands, key=lambda h: h["net_bb"])[:k]]


def _versus_fold(name, title, played, folded, tip):
    """A decision compared with folding in the same spot: the blind already in the pot is lost either way."""
    p, f = _group(played), _group(folded)
    if p["hands"] < HIDE_BELOW or f["hands"] < HIDE_BELOW:
        return None
    diff = p["per_hand"] - f["per_hand"]
    z = _z(diff, ((p["se"] or 0) ** 2 + (f["se"] or 0) ** 2) ** 0.5)
    if diff >= 0 or not confidence(z):
        return None
    return {"key": name, "title": title, "kind": "vs_fold", "sample": _sample(p["hands"]),
            "hands": p["hands"], "value": round(diff, 2), "played": p, "folded": f, "z": round(z, 2),
            "confidence": confidence(z), "cost_bb": round(-diff * p["hands"], 0), "tip": tip, "worst": _worst(played)}


def leaks(hands):
    out = []
    by_spot = defaultdict(list)
    for h in hands:
        by_spot[(h["position"], h["spot"])].append(h)
    bb = lambda spot: by_spot[("BB", spot)]
    sb = lambda spot: by_spot[("SB", spot)]
    out.append(_versus_fold(
        "bb_defence", "Big blind: calling an open", bb("call_vs_open"), bb("fold_vs_open"),
        "On average your calls from the big blind end worse than folding would have. Call less with offsuit hands "
        "that are easily dominated (e.g. KJo, QTo, A8o) against early positions, 3-bet your strongest hands instead "
        "of calling, and do not pay off to the river with one pair out of position."))
    out.append(_versus_fold(
        "sb_complete", "Small blind: completing or limping", sb("limp"), sb("fold_unopened"),
        "From the small blind you play out of position for the whole hand. Raise or fold instead of completing."))
    out.append(_versus_fold(
        "sb_flat", "Small blind: calling an open", sb("call_vs_open"), sb("fold_vs_open"),
        "Calling from the small blind invites the big blind in and leaves you out of position. 3-bet or fold more."))

    # folding after your own open was 3-bet: a frequency, by stack depth
    for lo, hi, label in FOLD_TO_3BET_DEPTHS:
        faced = [h for h in hands if h["spot"] == "open" and h["after_3bet"] and lo <= h["stack_bb"] < hi]
        folds = [h for h in faced if h["after_3bet"] == "fold"]
        if len(faced) < HIDE_BELOW:
            continue
        freq = len(folds) / len(faced)
        if freq <= FOLD_TO_3BET_HIGH:
            continue
        lost = -sum(h["net_bb"] for h in folds) / len(folds) if folds else 0.0
        z = _z(freq - FOLD_TO_3BET_HIGH, (freq * (1 - freq) / len(faced)) ** 0.5)
        out.append({"key": f"fold_to_3bet_{label}", "title": f"Folding to 3-bets ({label})", "kind": "frequency",
                    "z": round(z, 2) if z else None, "confidence": confidence(z) or "possible",
                    "sample": _sample(len(faced)), "hands": len(faced), "value": round(100 * freq, 1),
                    "guide": "rough guide: around half; above 70 % opponents can 3-bet you with anything",
                    "cost_bb": round((freq - FOLD_TO_3BET_GUIDE) * len(faced) * lost, 0),
                    "tip": "You fold most of the time when your open is re-raised. Open a little tighter from early "
                           "positions so you have hands to continue with, and with 20-40 BB answer more 3-bets "
                           "with an all-in or a call.",
                    "worst": _worst(folds)})

    # stack depths and positions outside the blinds that lose
    for label in [d[2] for d in DEPTHS]:
        g = [h for h in hands if depth_label(h["stack_bb"]) == label]
        s = _group(g)
        z = _z(s["per_hand"] or 0, s["se"])
        if s["hands"] >= 300 and s["net_bb"] < 0 and confidence(z):
            out.append({"key": f"depth_{label}", "title": f"Stack {label}", "kind": "bb_per_100", "sample": "ok",
                        "z": round(z, 2), "confidence": confidence(z),
                        "hands": s["hands"], "value": s["bb_per_100"], "cost_bb": round(-s["net_bb"], 0),
                        "tip": DEPTH_TIPS.get(label, "Review the biggest losses at this stack depth."), "worst": _worst(g)})
    for pos in sorted({h["position"] for h in hands if h["position"] not in UNRANKED_POSITIONS and h["position"]}):
        g = [h for h in hands if h["position"] == pos]
        s = _group(g)
        z = _z(s["per_hand"] or 0, s["se"])
        if s["hands"] >= 300 and s["net_bb"] < 0 and confidence(z):
            out.append({"key": f"position_{pos}", "title": f"Position {pos}", "kind": "bb_per_100", "sample": "ok",
                        "z": round(z, 2), "confidence": confidence(z),
                        "hands": s["hands"], "value": s["bb_per_100"], "cost_bb": round(-s["net_bb"], 0),
                        "tip": "BTN" == pos and "The button should be your best seat. Fewer calls, more raises, and "
                               "keep betting when checked to." or "Play a little tighter from this seat.",
                        "worst": _worst(g)})

    # starting hands that lose clearly
    classes = defaultdict(list)
    for h in hands:
        if k := hand_class(h["cards"]):
            classes[k].append(h)
    losing = sorted(((k, _group(g), g) for k, g in classes.items() if len(g) >= HIDE_BELOW), key=lambda x: x[1]["net_bb"])
    # with ~80 hand types some look bad by pure chance, so a hand type needs 2 standard errors and stays "possible"
    for k, s, g in losing[:3]:
        z = _z(s["per_hand"] or 0, s["se"])
        if s["net_bb"] <= -50 and z is not None and z <= -2:
            out.append({"key": f"hand_{k}", "title": f"Starting hand {k}", "kind": "net_bb", "sample": _sample(s["hands"]),
                        "z": round(z, 2), "confidence": "possible",
                        "hands": s["hands"], "value": s["net_bb"], "cost_bb": round(-s["net_bb"], 0),
                        "tip": "With this many hands a result depends mostly on a few big pots, and among ~80 hand "
                               "types one or two look bad by chance. Look at those pots: was it a dominated hand "
                               "calling a raise?",
                        "worst": _worst(g)})
    # likely leaks first, then by what they cost
    return sorted([x for x in out if x and x["cost_bb"] > 0],
                  key=lambda x: (x["confidence"] != "likely", -x["cost_bb"]))


DEPTH_TIPS = {
    "10-15 BB": "At 10-15 BB most hands should be all-in or fold. Avoid raising and folding, and avoid calling.",
    "25-40 BB": "At 25-40 BB re-shoving all-in over an open is often the best play. Calling and playing after the "
                "flop with this stack loses for you.",
    "40+ BB": "With a deep stack small edges after the flop decide. Review the biggest losses: were they one-pair hands "
              "paid off to the river?",
}


def strengths(hands, db, site=SITE):
    out = []
    lines = (("open", "Open raising"), ("3bet", "3-betting"), ("4bet_cold", "4-betting"), ("open_shove", "Open shoving"),
             ("3bet_shove", "Re-shoving all-in"))
    for spot, title in lines:
        s = _group([h for h in hands if h["spot"] == spot])
        z = _z(s["per_hand"] or 0, s["se"])
        if s["hands"] >= HIDE_BELOW and s["net_bb"] > 0 and confidence(z):
            out.append({"key": f"line_{spot}", "title": title, "hands": s["hands"], "sample": _sample(s["hands"]),
                        "confidence": confidence(z), "z": round(z, 2),
                        "text": f"{s['net_bb']:+,.0f} BB in {s['hands']} hands ({s['per_hand']:+.2f} BB per hand).",
                        "value": s["net_bb"]})
    for pos in sorted({h["position"] for h in hands if h["position"] and h["position"] not in UNRANKED_POSITIONS}):
        s = _group([h for h in hands if h["position"] == pos])
        z = _z(s["per_hand"] or 0, s["se"])
        if s["hands"] >= 300 and s["net_bb"] > 0 and confidence(z):
            out.append({"key": f"position_{pos}", "title": f"Position {pos}", "hands": s["hands"], "sample": "ok",
                        "confidence": confidence(z), "z": round(z, 2),
                        "text": f"{s['bb_per_100']:+.1f} bb/100 in {s['hands']} hands.", "value": s["net_bb"]})
    for label in [d[2] for d in DEPTHS]:
        s = _group([h for h in hands if depth_label(h["stack_bb"]) == label])
        z = _z(s["per_hand"] or 0, s["se"])
        if s["hands"] >= 300 and s["net_bb"] > 0 and confidence(z):
            out.append({"key": f"depth_{label}", "title": f"Stack {label}", "hands": s["hands"], "sample": "ok",
                        "confidence": confidence(z), "z": round(z, 2),
                        "text": f"{s['bb_per_100']:+.1f} bb/100 in {s['hands']} hands.", "value": s["net_bb"]})
    a = db.query("SELECT COUNT(*) AS n, SUM(ev_bb) AS ev, SUM(net_bb) AS net FROM hero_allins WHERE site = ?", (site,))[0]
    if int(a["n"]) >= HIDE_BELOW and _f(a["ev"]) > 0:
        out.append({"key": "allin_ev", "title": "Getting it in good", "hands": int(a["n"]), "sample": _sample(int(a["n"])),
                    "confidence": "likely",                    # an expectation over every runout, not a noisy result
                    "text": f"Your all-ins are worth {_f(a['ev']):+,.0f} BB on average outcomes ({int(a['n'])} all-ins): "
                            f"you put the money in as the favourite.", "value": _f(a["ev"])})
    return sorted(out, key=lambda x: -x["value"])


def money(db, site=SITE):
    trs = db.query("SELECT tournament_id, buyin_total, total_cost, profit, reentries, cash_won, ticket_value "
                   "FROM tournament_results WHERE site = ?", (site,))
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
            "roi_pct": round(100 * profit / cost, 1) if cost else None,
            "roi_margin_pct": roi_margin(trs), "tiers": tiers,
            "reentries": {"tournaments": len(re), "extra_cost": round(extra, 2),
                          "profit": round(sum(_f(t["profit"]) for t in re), 2)}}


def roi_margin(trs):
    """95 % margin of the ROI (in percentage points) from the spread of tournament results.

    ROI = sum(profit) / sum(cost) is a ratio; its standard error is sqrt(sum((profit_i - ROI * cost_i)^2)) / sum(cost),
    with the small-sample correction n / (n - 1). Big-field tournaments spread a lot, so this is wide.
    """
    n = len(trs)
    cost = sum(_f(t["total_cost"]) for t in trs)
    if n < 2 or not cost:
        return None
    roi = sum(_f(t["profit"]) for t in trs) / cost
    ss = sum((_f(t["profit"]) - roi * _f(t["total_cost"])) ** 2 for t in trs) * n / (n - 1)
    return round(100 * 1.96 * ss ** 0.5 / cost, 0)


def overview(hands, db, site=SITE):
    n = len(hands)
    a = db.query("SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(ev_bb) AS ev, SUM(luck_bb) AS luck FROM hero_allins "
                 "WHERE site = ?", (site,))[0]
    t = db.query("SELECT COUNT(*) AS n, SUM(in_the_money) AS itm FROM tournament_results WHERE site = ?", (site,))[0]
    return {"hands": n, "tournaments": int(t["n"]), "itm_pct": round(100 * int(t["itm"] or 0) / int(t["n"]), 1) if int(t["n"]) else None,
            "vpip_pct": round(100 * sum(h["vpip"] for h in hands) / n, 1) if n else None,
            "pfr_pct": round(100 * sum(h["pfr"] for h in hands) / n, 1) if n else None,
            "bb_per_100": round(100 * sum(h["net_bb"] for h in hands) / n, 1) if n else None,
            "allins": {"count": int(a["n"]), "actual_bb": round(_f(a["net"]), 1), "ev_bb": round(_f(a["ev"]), 1),
                       "luck_bb": round(_f(a["luck"]), 1)}}


def analysis_data(db, site=SITE):
    """The Analysis view: always the whole history."""
    hands = load_hands(db, site)
    return {"overview": overview(hands, db, site), "leaks": leaks(hands), "strengths": strengths(hands, db, site),
            "money": money(db, site), "thresholds": {"hide_below": HIDE_BELOW, "small_below": SMALL_BELOW}}
