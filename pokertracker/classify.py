"""Automatic tournament classification, derived only from imported data (no manual input).

Tags are "group:value" strings. Everything is computed from the summary (name, buy-in, field size,
re-entries) and from the hand histories (level length, level Hero entered at).
"""
import re
import statistics
from datetime import datetime

MIN_LEVEL_PAIRS = 3          # consecutive-level pairs needed before the level length is trusted

# Thresholds (total buy-in in $, field size, minutes per level)
STAKE_TIERS = [(5.5, "micro"), (30, "low"), (100, "mid"), (500, "high")]     # above the last: "super"
FIELD_SIZES = [(50, "small"), (200, "medium"), (1000, "large")]              # above the last: "huge"
SPEED_BOUNDS = [(3.5, "hyper"), (6.5, "turbo")]                              # above: "regular"

SAT_TARGET = re.compile(r"Satellite to (?:#\d+: )?(?P<target>.+?)(?:, \d+ Seats)?$", re.I)


def _ts(x):
    return x if isinstance(x, datetime) else datetime.fromisoformat(str(x))


def level_minutes(rows):
    """Median minutes per blind level from (level, played_at) rows, plus the number of level pairs used.

    Uses the mean timestamp of each observed level and the gap between consecutive levels. The median is robust
    against breaks; returns (None, pairs) when there are too few pairs to trust the number.
    """
    by_level = {}
    for level, ts in rows:
        by_level.setdefault(int(level), []).append(_ts(ts).timestamp() / 60)
    means = {lv: sum(v) / len(v) for lv, v in by_level.items()}
    gaps = [means[lv + 1] - means[lv] for lv in sorted(means) if lv + 1 in means]
    if len(gaps) < MIN_LEVEL_PAIRS:
        return None, len(gaps)
    return round(statistics.median(gaps), 1), len(gaps)


def classify(name, fmt, buyin_total, players, minutes, first_entry_level, reentries):
    tags = []
    if fmt:
        tags.append(f"format:{fmt}")
    low = (name or "").lower()
    if fmt != "satellite" and "mystery" in low:
        tags.append("mystery-bounty")
    if fmt == "satellite" and (m := SAT_TARGET.search(name or "")):
        tags.append(f"target:{m['target']}")
    if buyin_total is not None:
        total = float(buyin_total)
        tags.append("stake:" + next((lbl for lim, lbl in STAKE_TIERS if total <= lim), "super"))
    if players:
        tags.append("field:" + next((lbl for lim, lbl in FIELD_SIZES if players < lim), "huge"))
    if minutes is not None:
        tags.append("speed:" + next((lbl for lim, lbl in SPEED_BOUNDS if minutes <= lim), "regular"))
    if first_entry_level is not None:
        tags.append("entry:start" if first_entry_level == 1 else "entry:late")
    if reentries:
        tags.append("re-entered")
    return tags


def refresh_classification(db, site, tournament_id):
    """Recompute structure facts and tags of one tournament from what is stored (safe to repeat)."""
    t = db.query("SELECT * FROM tournaments WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    if not t:
        return
    t = t[0]
    hands = db.query("SELECT level, played_at FROM hands WHERE site = ? AND tournament_id = ?",
                     (site, tournament_id))
    minutes, pairs = level_minutes([(h["level"], h["played_at"]) for h in hands])
    first = db.query("SELECT entry_level FROM entries WHERE site = ? AND tournament_id = ? AND entry_no = 1",
                     (site, tournament_id))
    first_level = int(first[0]["entry_level"]) if first else None
    tags = classify(t["name"], t["format"], t["buyin_total"], t["players"], minutes, first_level, t["reentries"])

    db.execute("DELETE FROM tournament_structure WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    db.execute("INSERT INTO tournament_structure (site, tournament_id, level_minutes, level_pairs, hands_seen) "
               "VALUES (?, ?, ?, ?, ?)", (site, tournament_id, minutes, pairs, len(hands)))
    db.execute("DELETE FROM tournament_tags WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    db.executemany("INSERT INTO tournament_tags (site, tournament_id, tag) VALUES (?, ?, ?)",
                   [(site, tournament_id, tag) for tag in tags])
