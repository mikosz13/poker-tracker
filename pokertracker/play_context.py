"""When and how you play (docs/tasks/multitabling.md): results and VPIP / PFR by the number of tournaments played at
the same time, the time of day and the time since the session started.

- Tournaments at once: a tournament runs from Hero's first to Hero's last hand in it; a hand counts the tournaments
  running at its minute (itself included).
- Time of day: the hand's time as GG writes it, which is the player's local time (checked on Mik's files, 17.10.2026:
  the file names are in UTC, the hands and summaries two hours later, Polish summer time).
- Session: hands with breaks of at most SESSION_GAP_HOURS, as for "Last session" on the dashboard.

Every group is compared with the rest of the hands AT THE SAME STACK DEPTH (bb/100 by EV, VPIP, PFR): late in a
session or at night the stacks are shorter, and a short stack alone plays fewer hands, so a plain comparison would
blame the clock for the stack. The expected value of a group is what the rest did in each stack band, weighted by the
group's hands per band. The family of tests is corrected with Benjamini-Hochberg and only differences with
q <= Q_SHOWN are reported, as for the leaks. ROI per group is
descriptive, with its bootstrap interval; tournaments are placed by their own hands (the average number of
tournaments at once, Hero's first hand for the time of day and the session).
"""
import math
from bisect import bisect_left, bisect_right
from datetime import datetime

from . import preflop
from .analysis import MIN_TOURNAMENTS, benjamini_hochberg, bootstrap_roi, depth_label, load_hands, p_value
from .tournament_report import SITE

SESSION_GAP_HOURS = 3           # the same rule as the dashboard's "Last session" (server.SESSION_GAP_HOURS)
TABLES = ("1", "2", "3+")
DAYPARTS = ((0, 6, "night"), (6, 12, "morning"), (12, 18, "afternoon"), (18, 24, "evening"))
SESSION_AGE = ((0, 1, "h0"), (1, 2, "h1"), (2, 3, "h2"), (3, math.inf, "h3"))
MIN_TEST_HANDS = 300            # a group (and the rest) needs this many hands to be tested
MIN_TEST_SESSIONS = 5           # ... and hands from this many sessions: one evening is not a habit
Q_SHOWN = 0.05
METRICS = ("ev100", "vpip", "pfr")


def _t(at):
    return datetime.fromisoformat(str(at)[:16])


def tables_at_once(hands):
    """For every hand, how many tournaments were running at its minute (first to last hand of each)."""
    span = {}
    for h in hands:
        a, b = span.get(h["tournament_id"], (h["at"], h["at"]))
        span[h["tournament_id"]] = (min(a, h["at"]), max(b, h["at"]))
    starts, ends = sorted(a for a, _ in span.values()), sorted(b for _, b in span.values())
    return [bisect_right(starts, h["at"]) - bisect_left(ends, h["at"]) for h in hands]


def session_hours(hands, gap_hours=SESSION_GAP_HOURS):
    """For every hand (in time order): (its session's number, the hours since that session started)."""
    out, start, prev, number = [], None, None, -1
    for h in hands:
        t = _t(h["at"])
        if prev is None or (t - prev).total_seconds() > gap_hours * 3600:
            start, number = t, number + 1
        out.append((number, (t - start).total_seconds() / 3600))
        prev = t
    return out


def _table_key(n):
    return TABLES[min(n, len(TABLES)) - 1]


def _band(value, bands):
    return next(key for lo, hi, key in bands if lo <= value < hi)


def _stats(group):
    s = preflop.summarise(group)
    return {"hands": s["hands"], "vpip": s["vpip"], "pfr": s["pfr"], "ev100": s["ev100"]}


def _bands(rest):
    """Per stack band of the rest: VPIP / PFR counts over decided hands, and the mean and variance of the EV result."""
    out = {}
    for h in rest:
        b = out.setdefault(depth_label(h["stack_bb"]), {"decided": 0, "vpip": 0, "pfr": 0, "adj": []})
        b["decided"] += h["decided"]
        b["vpip"] += h["vpip"]
        b["pfr"] += h["pfr"]
        b["adj"].append(h["adj_bb"])
    for b in out.values():
        n = len(b["adj"])
        b["mean"] = sum(b["adj"]) / n
        b["var"] = sum((x - b["mean"]) ** 2 for x in b["adj"]) / (n - 1) if n > 1 else None
    return out


def expected_test(metric, group, sessions, bands):
    """(z, the group's value, the value expected from the rest at the group's stack depths, sessions), or None when the
    group has fewer than MIN_TEST_SESSIONS sessions or a stack band without any rest to compare with.

    Each hand gives observed minus expected: for VPIP / PFR the hand's 0 or 1 against the rest's rate in its stack band
    (decided hands only), for bb/100 by EV its result against the rest's mean in its band. Hands of one session are
    not independent (the same mood, tables, tournaments), so the variance of the total is counted by session
    (cluster-robust: the sum over sessions of their squared totals, times G / (G - 1)); for EV it also adds the
    uncertainty of the band means."""
    totals, counts = {}, {}
    obs = exp = 0.0
    n = 0
    for h, session in zip(group, sessions):
        band = depth_label(h["stack_bb"])
        b = bands.get(band)
        if metric == "ev100":
            if b is None or b["var"] is None:
                return None
            o, e = h["adj_bb"], b["mean"]
            counts[band] = counts.get(band, 0) + 1
        else:
            if not h["decided"]:
                continue
            if b is None or not b["decided"]:
                return None
            o, e = h[metric], b[metric] / b["decided"]
        totals[session] = totals.get(session, 0.0) + o - e
        obs, exp, n = obs + o, exp + e, n + 1
    g = len(totals)
    if n < 2 or g < MIN_TEST_SESSIONS:
        return None
    var = g / (g - 1) * sum(x * x for x in totals.values())
    if metric == "ev100":
        var += sum(k * k * bands[d]["var"] / len(bands[d]["adj"]) for d, k in counts.items())
    if not var:
        return None
    return (obs - exp) / math.sqrt(var), round(100 * obs / n, 1), round(100 * exp / n, 1), g


def context_data(db, site=SITE, hands=None):
    """The three splits with their tests; hands: load_hands(db) when the caller has them already."""
    hands = sorted(hands if hands is not None else load_hands(db, site), key=lambda h: (h["at"], h["hand_id"]))
    if not hands:
        return {"dims": [], "findings": [], "closest": None, "tested": 0, "gap_hours": SESSION_GAP_HOURS}
    at_once, sess = tables_at_once(hands), session_hours(hands)
    session_of = [k for k, _ in sess]
    keys = {"tables": [_table_key(n) for n in at_once],
            "daypart": [_band(_t(h["at"]).hour, DAYPARTS) for h in hands],
            "session": [_band(x, SESSION_AGE) for _, x in sess]}
    order = {"tables": list(TABLES), "daypart": [k for *_, k in DAYPARTS], "session": [k for *_, k in SESSION_AGE]}

    # tournaments (multi-day events as one, under their result) placed by their own hands
    event = {r["tournament_id"]: r["ev"] for r in db.query(
        "SELECT tournament_id, COALESCE(event_id, tournament_id) AS ev FROM tournaments WHERE site = ?", (site,))}
    results = {r["tournament_id"]: (float(r["total_cost"]), float(r["won_total"] or 0)) for r in db.query(
        "SELECT tournament_id, total_cost, won_total, summary_missing, provisional FROM tournament_results "
        "WHERE site = ? AND total_cost > 0 AND NOT (summary_missing = 1 AND provisional = 0)", (site,))}
    per_t = {}
    for i, h in enumerate(hands):
        e = event.get(h["tournament_id"], h["tournament_id"])
        p = per_t.setdefault(e, {"n": 0, "tables": 0, "first": i})
        p["n"] += 1
        p["tables"] += at_once[i]
    t_key = {"tables": {e: _table_key(max(1, round(p["tables"] / p["n"]))) for e, p in per_t.items()},
             "daypart": {e: keys["daypart"][p["first"]] for e, p in per_t.items()},
             "session": {e: keys["session"][p["first"]] for e, p in per_t.items()}}

    dims, family = [], []
    for dim in ("tables", "daypart", "session"):
        rows = []
        for key in order[dim]:
            idx = [i for i, k in enumerate(keys[dim]) if k == key]
            if not idx:
                continue
            group = [hands[i] for i in idx]
            rest = [h for h, k in zip(hands, keys[dim]) if k != key]
            g = _stats(group)
            pairs = [results[e] for e, k in sorted(t_key[dim].items()) if k == key and e in results]
            boot = bootstrap_roi(pairs) if len(pairs) >= MIN_TOURNAMENTS else None
            cost, won = sum(c for c, _ in pairs), sum(w for _, w in pairs)
            row = {"key": key, **g,
                   "share_pct": round(100 * len(group) / len(hands), 1), "tournaments": len(pairs),
                   "sessions": len({session_of[i] for i in idx}),
                   "roi_pct": round(100 * (won - cost) / cost, 1) if cost else None,
                   "interval": {"low": boot["low"], "high": boot["high"], "level": 95} if boot else None}
            if len(group) >= MIN_TEST_HANDS and len(rest) >= MIN_TEST_HANDS:
                bands = _bands(rest)
                for metric in METRICS:
                    t = expected_test(metric, group, [session_of[i] for i in idx], bands)
                    if t:
                        family.append({"dim": dim, "key": key, "metric": metric, "z": t[0], "p": p_value(t[0]),
                                       "value": t[1], "expected": t[2], "hands": len(group), "sessions": t[3]})
            rows.append(row)
        dims.append({"key": dim, "rows": rows})
    for f, q in zip(family, benjamini_hochberg([f["p"] for f in family])):
        f["q"] = round(q, 4)
        f["z"] = round(f["z"], 2)
        f["p"] = round(f["p"], 4)
    findings = sorted((f for f in family if f["q"] <= Q_SHOWN), key=lambda f: f["q"])
    closest = None if findings or not family else min(family, key=lambda f: f["p"])
    return {"dims": dims, "findings": findings, "closest": closest, "tested": len(family),
            "gap_hours": SESSION_GAP_HOURS, "min_test_hands": MIN_TEST_HANDS, "min_test_sessions": MIN_TEST_SESSIONS}
