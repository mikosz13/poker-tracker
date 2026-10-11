"""Satellite tickets: which were won, and which were probably used.

GGPoker writes a ticket entry with the full buy-in, so the files never say a tournament was entered with a ticket.
It is inferred, for information only (the cost stays the full buy-in): the first tournament after the satellite whose
name has the satellite's target in it and whose buy-in is the ticket's value.
"""
import re

from .summary import satellite_target
from .tournament_report import SITE

GENERIC = {"wsop", "online", "nlh", "the", "gtd"}


def _words(name):
    return {w for w in re.findall(r"\$?[\w]+", (name or "").lower()) if w not in GENERIC}


def tickets_won(db, site=SITE, since=None):
    """Every ticket won (since a time, if given), newest first: satellite, target, value, and the tournament it was
    probably used in (looked for over the whole history)."""
    sats = db.query("SELECT tournament_id, name, started_at, ticket_value FROM tournament_results WHERE site = ? "
                    "AND ticket_value > 0 ORDER BY started_at", (site,))
    rows = db.query("SELECT tournament_id, name, started_at, buyin_total FROM tournament_results WHERE site = ? "
                    "AND format <> 'satellite' ORDER BY started_at", (site,))
    used, out = set(), []
    for s in sats:
        target, value = satellite_target(s["name"]), float(s["ticket_value"])
        words = _words(target)
        use = next((r for r in rows if r["tournament_id"] not in used and words and words <= _words(r["name"])
                    and str(r["started_at"] or "") > str(s["started_at"] or "")
                    and abs(float(r["buyin_total"] or 0) - value) <= 0.1 * value), None)
        if use:
            used.add(use["tournament_id"])
        out.append({"tournament_id": s["tournament_id"], "satellite": s["name"], "date": str(s["started_at"] or "")[:16],
                    "target": target, "value": round(value, 2),
                    "used_in": {"tournament_id": use["tournament_id"], "name": use["name"],
                                "date": str(use["started_at"])[:16]} if use else None})
    if since:
        out = [x for x in out if x["date"] >= str(since)[:16]]
    return out[::-1]


def tickets_summary(db, site=SITE, since=None):
    items = tickets_won(db, site, since)
    return {"count": len(items), "value": round(sum(x["value"] for x in items), 2),
            "unused_value": round(sum(x["value"] for x in items if not x["used_in"]), 2), "items": items}


def ticket_entries(db, site=SITE):
    """{tournament id: the ticket it was probably entered with}."""
    return {x["used_in"]["tournament_id"]: x for x in tickets_won(db, site) if x["used_in"]}
