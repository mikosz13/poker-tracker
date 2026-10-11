"""Where Hero finished, as a share of the field: facts from the summaries, no payout structure assumed.

place_pct = place / players x 100 (the final place, over every day of a multi-day tournament; a day-1 advance without
its later days has none). Top 10 % and top 15 % of the field come with a 95 % bootstrap interval over tournaments.
A player of average skill lands in each band in proportion to its width: 10 % of finishes in the top 10 %, and so on.
"""
import numpy as np

from .tournament_report import SITE

BANDS = (("top10", 0, 10), ("10-25", 10, 25), ("25-50", 25, 50), ("50-100", 50, 100))
SAMPLES, SEED = 10_000, 20261011


def share_interval(flags, samples=SAMPLES, seed=SEED):
    """95 % percentile bootstrap interval (in %) of the share of 1s in flags; None below two tournaments."""
    if len(flags) < 2:
        return None
    a = np.array(flags, dtype=float)
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, len(a), size=(samples, len(a)))].mean(axis=1) * 100
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"low": round(float(lo), 1), "high": round(float(hi), 1), "level": 95}


def place_stats(db, site=SITE, since=None):
    when = " AND started_at >= ?" if since else ""
    pcts = [float(r["place_pct"]) for r in db.query(
        f"SELECT place_pct FROM tournament_results WHERE site = ? AND place_pct IS NOT NULL{when}",
        (site, *((since,) if since else ())))]
    n = len(pcts)
    out = {"n": n}
    for key, limit in (("top10", 10), ("top15", 15)):
        flags = [1 if p <= limit else 0 for p in pcts]
        out[key] = {"count": sum(flags), "pct": round(100 * sum(flags) / n, 1) if n else None,
                    "interval": share_interval(flags)}
    out["bands"] = [{"key": key, "count": c, "pct": round(100 * c / n, 1) if n else None, "expected": hi - lo}
                    for key, lo, hi in BANDS
                    for c in [sum(1 for p in pcts if (p > lo or (lo == 0 and p >= 0)) and p <= hi)]]
    return out
