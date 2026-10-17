"""Variance (docs/tasks/variance.md): what the next N tournaments could look like if they go like the ones played.

Every tournament becomes a result in buy-ins (cost with re-entries and the prize, tickets at face value, divided by
its buy-in), so a $54 and a $5 tournament weigh the same. A run draws N of them at random with replacement
(bootstrap) and adds them up; 10,000 runs with a fixed seed give the spread of the result and of the largest drawdown.
"What if my ROI were X": every prize is scaled by the same factor, so a tournament without a prize stays at minus its
cost (nobody loses more than they paid) and the shape of the results is kept.

What it cannot see: changes in skill, fields or structures; it only repeats the results there are.
"""
from datetime import datetime, timedelta

import numpy as np

from .tournament_report import SITE

RUNS = 10_000
SEED = 20261017
HORIZONS = (100, 500, 1000)
DEFAULT_N = 500
ROI_MIN, ROI_MAX = -20, 50          # the "what if" slider, in %
SMALL_BELOW = 100                   # fewer tournaments: the simulation repeats a few results, said clearly
RECENT = 30                         # the average buy-in of the last tournaments turns buy-ins into dollars
FAN_POINTS = 40                     # points of the percentile fan
CHUNK = 1000                        # runs simulated at once (memory: CHUNK x N)
WEEKLY_BELOW_DAYS = 120             # a shorter history shows the average buy-in by week, a longer one by month

_CACHE = {}


def load(db, site=SITE):
    """The tournaments in the order of their ids (one fixed order: the seeded draws pick the same rows), without the
    ones whose prize is unknown (a later day without its summary and nothing typed in)."""
    rows = db.query("SELECT tournament_id, started_at, buyin_total, total_cost, won_total, summary_missing, provisional "
                    "FROM tournament_results WHERE site = ? AND buyin_total > 0 ORDER BY tournament_id", (site,))
    unknown = [r for r in rows if int(r["summary_missing"] or 0) and not int(r["provisional"] or 0)]
    used = [r for r in rows if r not in unknown]
    bi = np.array([float(r["buyin_total"]) for r in used])
    cost = np.array([float(r["total_cost"]) for r in used]) / bi if used else np.zeros(0)
    won = np.array([float(r["won_total"] or 0) for r in used]) / bi if used else np.zeros(0)
    return rows, used, len(unknown), cost, won


def roi_factor(cost, won, roi_pct):
    """The factor on every prize that makes the ROI (in buy-ins) equal roi_pct; None without any prize."""
    if roi_pct is None:
        return 1.0
    return None if won.sum() <= 0 else (1 + roi_pct / 100) * cost.sum() / won.sum()


def simulate(profit, n, runs=RUNS, seed=SEED, points=FAN_POINTS):
    """Final results, largest drawdowns (from the highest point so far, the start included) and the cumulative result
    at `points` steps, for `runs` draws of n tournaments. The same seed draws the same tournaments whatever the
    prizes, so the "what if" slider moves the picture smoothly."""
    rng = np.random.default_rng(seed)
    at = np.unique(np.linspace(1, n, min(points, n)).round().astype(int)) - 1
    finals, drawdowns, fan = [], [], []
    for start in range(0, runs, CHUNK):
        k = min(CHUNK, runs - start)
        path = np.cumsum(profit[rng.integers(0, len(profit), size=(k, n))], axis=1)
        peak = np.maximum.accumulate(np.maximum(path, 0), axis=1)
        finals.append(path[:, -1])
        drawdowns.append((peak - path).max(axis=1))
        fan.append(path[:, at])
    return np.concatenate(finals), np.concatenate(drawdowns), np.concatenate(fan), at + 1


def abi_series(rows):
    """Average buy-in by week (short histories) or month, oldest first."""
    if not rows:
        return {"unit": "month", "points": []}
    when = [datetime.fromisoformat(str(r["started_at"])[:19]) for r in rows]
    weekly = (max(when) - min(when)).days < WEEKLY_BELOW_DAYS
    groups = {}
    for r, w in zip(rows, when):
        key = (w.date() - timedelta(days=w.weekday())).isoformat() if weekly else w.strftime("%Y-%m")
        groups.setdefault(key, []).append(float(r["buyin_total"]))
    return {"unit": "week" if weekly else "month",
            "points": [{"key": k, "abi": round(sum(v) / len(v), 2), "tournaments": len(v)} for k, v in sorted(groups.items())]}


def _r(x, d=1):
    return round(float(x), d)


def variance_data(db, site=SITE, n=DEFAULT_N, roi=None):
    """Everything the Variance tab shows; n: tournaments ahead, roi: the "what if" ROI in % (None: as played)."""
    n = n if n in HORIZONS else DEFAULT_N
    rows, used, unknown, cost, won = load(db, site)
    recent = sorted(rows, key=lambda r: str(r["started_at"]))[-RECENT:]
    out = {"tournaments": len(used), "unknown": unknown, "small": len(used) < SMALL_BELOW, "small_below": SMALL_BELOW,
           "n": n, "horizons": list(HORIZONS), "runs": RUNS, "roi_min": ROI_MIN, "roi_max": ROI_MAX,
           "abi_recent": _r(sum(float(r["buyin_total"]) for r in recent) / len(recent), 2) if recent else None,
           "abi_recent_n": len(recent), "abi": abi_series(sorted(rows, key=lambda r: str(r["started_at"]))),
           "roi_played": _r(100 * (won.sum() / cost.sum() - 1)) if len(used) and cost.sum() else None,
           "roi": None, "result": None}
    if len(used) < 2:
        return out
    roi = None if roi is None else max(ROI_MIN, min(ROI_MAX, float(roi)))
    factor = roi_factor(cost, won, roi)
    if factor is None:                                  # nothing won yet: there is no prize to scale
        roi, factor = None, 1.0
    out["roi"] = out["roi_played"] if roi is None else _r(roi)
    key = (cost.tobytes(), won.tobytes(), n, round(factor, 9))
    if key not in _CACHE:
        finals, dd, fan, steps = simulate(won * factor - cost, n)
        _CACHE.clear()
        _CACHE[key] = {
            "result": {"p5": _r(np.percentile(finals, 5)), "median": _r(np.median(finals)),
                       "p95": _r(np.percentile(finals, 95)), "loss_pct": _r(100 * (finals < 0).mean())},
            "drawdown": {"median": _r(np.median(dd)), "p95": _r(np.percentile(dd, 95))},
            "bankroll": int(np.ceil(np.percentile(dd, 95))),
            "fan": [{"n": int(s), **{p: _r(v) for p, v in zip(("p5", "p25", "p50", "p75", "p95"),
                                                                np.percentile(fan[:, i], [5, 25, 50, 75, 95]))}}
                    for i, s in enumerate(steps)]}
    out.update(_CACHE[key])
    return out
