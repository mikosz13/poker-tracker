"""Preflop statistics as PokerTracker 4 counts them: every rate over its own opportunities (docs/tasks/analysis-v2.md).

  VPIP, PFR      hands with a preflop decision (no walk, no all-in forced by a blind or ante); see hero_hands
  RFI            Hero's first decision with everyone before folded (no limpers), not in the big blind; a raise
                 counts, all-in included
  open shove     the RFI opportunities; Hero's raise is all-in
  3-bet          exactly one raise before Hero's first decision (callers allowed, so a squeeze counts); Hero raises.
                 Not a chance when that raise is all-in and Hero cannot raise over it (calling would put Hero all-in:
                 stack - ante <= the amount raised to); an all-in for less than Hero has stays one (an isolation)
  fold to 3-bet  Hero opened (a raise, not all-in) and exactly one re-raise followed; Hero folds
  bb/100 wg EV   every hand; in a hand with an all-in the all-in EV replaces the result

The trend compares the last 30 days with the rest of the history, only with enough hands and opportunities on both
sides, and shows at most one arrow: the largest change beyond noise.
"""
import math
from datetime import datetime, timedelta

MIN_OPP = 30                      # fewer opportunities: greyed, "za mało danych"
TREND_DAYS, TREND_HANDS, TREND_OPP, TREND_Z = 30, 500, 100, 2.5
TREND_STATS = (("vpip", "vpip", "decided"), ("pfr", "pfr", "decided"), ("threebet", "tb", "tb_opp"))
POSITIONS = ("UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB", "BTN/SB")
COUNTS = ("rfi_opp", "rfi", "shove", "tb_opp", "tb", "f3_opp", "f3")


def hand_stats(actions, position, stack=None):
    """Opportunities and actions of one hand, from its preflop actions in order (dicts nick, action_type, amount,
    all_in). stack: Hero's chips at the start of the hand (None when unknown: an all-in raise is then a 3-bet chance)."""
    out = dict.fromkeys(COUNTS, 0)
    raises = callers = 0
    decided = opened = False
    ante, last_to, last_all_in = 0.0, 0.0, False
    for a in actions:
        kind = a["action_type"]
        if kind.startswith("posts"):
            if a["nick"] == "Hero" and kind == "posts_the_ante":
                ante += float(a.get("amount") or 0)
            continue
        if a["nick"] == "Hero":
            if not decided:                                         # Hero's first decision
                decided = True
                if raises == 0 and callers == 0 and position != "BB":
                    out["rfi_opp"] = 1
                    if kind == "raises":
                        out["rfi"], out["shove"] = 1, int(bool(a["all_in"]))
                        opened = not a["all_in"]
                elif raises == 1 and not (last_all_in and stack is not None and stack - ante <= last_to):
                    out["tb_opp"], out["tb"] = 1, int(kind == "raises")
            elif opened:                                            # Hero's next decision after an open
                if raises == 2:                                     # exactly one re-raise came back
                    out["f3_opp"], out["f3"] = 1, int(kind == "folds")
                opened = False
        if kind in ("raises", "bets"):
            raises += 1
            last_to, last_all_in = float(a.get("amount") or 0), bool(a["all_in"])     # "raises X to Y": Y
        elif kind == "calls" and a["nick"] != "Hero":
            callers += 1
    return out


def _blank():
    return {"hands": 0, "decided": 0, "vpip": 0, "pfr": 0, "adj": 0.0, **dict.fromkeys(COUNTS, 0)}


def _add(g, h):
    g["hands"] += 1
    g["adj"] += h["adj_bb"]
    for k in ("decided", "vpip", "pfr"):
        g[k] += h[k]
    for k in COUNTS:
        g[k] += h["pf"][k]


def rate(count, n):
    return {"pct": round(100 * count / n, 1) if n else None, "count": count, "n": n, "few": n < MIN_OPP}


def _finish(g):
    return {"hands": g["hands"], "few": g["hands"] < MIN_OPP,
            "vpip": rate(g["vpip"], g["decided"]), "pfr": rate(g["pfr"], g["decided"]),
            "rfi": rate(g["rfi"], g["rfi_opp"]), "shove": rate(g["shove"], g["rfi_opp"]),
            "threebet": rate(g["tb"], g["tb_opp"]), "fold3": rate(g["f3"], g["f3_opp"]),
            "ev100": round(100 * g["adj"] / g["hands"], 1) if g["hands"] else None}


def summarise(hands):
    g = _blank()
    for h in hands:
        _add(g, h)
    return _finish(g)


def by_position(hands):
    groups = {}
    for h in hands:
        _add(groups.setdefault(h["position"] or "?", _blank()), h)
    order = [p for p in POSITIONS if p in groups] + sorted(p for p in groups if p not in POSITIONS)
    return [dict(_finish(groups[p]), position=p) for p in order]


def by_depth(hands, depths):
    """depths: (low, high, label) bands of Hero's stack in big blinds at the start of the hand."""
    groups = {label: _blank() for _, _, label in depths}
    for h in hands:
        _add(groups[next(label for lo, hi, label in depths if lo <= h["stack_bb"] < hi)], h)
    return [dict(_finish(groups[label]), depth=label, low=lo, high=hi) for lo, hi, label in depths
            if groups[label]["hands"]]


def two_proportions(a, n1, b, n2):
    """z of the difference between two shares a/n1 and b/n2 (pooled standard error)."""
    p = (a + b) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    return (a / n1 - b / n2) / se if se else 0.0


def trend(hands, now=None):
    """The last 30 days against the rest of the history (so recent hands do not count on both sides). Each rate is
    compared only with 500+ hands and 100+ opportunities on each side; an arrow only at |z| >= 2.5, and only for the
    largest change."""
    since = ((now or datetime.now()) - timedelta(days=TREND_DAYS)).strftime("%Y-%m-%d %H:%M")
    recent, older = _blank(), _blank()
    for h in hands:
        _add(recent if h["at"] >= since else older, h)
    out = {"since": since, "recent_hands": recent["hands"], "older_hands": older["hands"], "stats": {}, "arrow": None}
    if min(recent["hands"], older["hands"]) < TREND_HANDS:
        return out
    for key, num, den in TREND_STATS:
        n1, n2 = recent[den], older[den]
        if min(n1, n2) < TREND_OPP:
            continue
        z = two_proportions(recent[num], n1, older[num], n2)
        out["stats"][key] = {"recent": round(100 * recent[num] / n1, 1), "older": round(100 * older[num] / n2, 1),
                             "z": round(z, 2), "n_recent": n1, "n_older": n2}
    beyond = [(abs(s["z"]), k) for k, s in out["stats"].items() if abs(s["z"]) >= TREND_Z]
    if beyond:
        key = max(beyond)[1]
        out["arrow"] = {"key": key, "up": out["stats"][key]["z"] > 0}
    return out
