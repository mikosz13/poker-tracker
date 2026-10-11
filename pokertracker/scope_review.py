"""A read-only look at what the scope rules would leave out of a database, before any import removes it.

For every summary in an export folder that the rules leave out as a whole tournament (a freeroll, an unreadable
summary, Sit & Go and the like), it shows the amounts on the summary and what the database holds for it now. It also
lists tournaments that were probably entered with a satellite ticket: they always stay, because GGPoker writes a ticket
entry with the full buy-in.
"""
import re

from .importer import FUSE_COUNT, FUSE_SHARE, SITE, classify, list_files, read_source
from .scope import UNRECOGNISED
from .summary import OutOfScope, UnrecognisedSummary, parse_summary

BUYIN = re.compile(r"^Buy-in: (.*)$", re.M)
RECEIVED = re.compile(r"received a total of (.*?)\.?\s*$", re.M)
GENERIC = {"wsop", "online", "nlh", "the"}


def _words(name):
    return {w for w in re.findall(r"\$?[\w]+", (name or "").lower()) if w not in GENERIC}


def review(db, folder, site=SITE):
    """{"remove": [...], "fuse": {...}, "ticket_entries": [...]}; nothing is written."""
    out, read, unreadable = {}, 0, 0
    for f in list_files(folder):
        for label, text in read_source(f):
            if classify(text or "") != "summary":
                continue
            read += 1
            try:
                parse_summary(text)
                continue
            except OutOfScope as e:
                tid, name, reason = e.tournament_id, e.name, e.reason
            except UnrecognisedSummary as e:
                if e.tournament_id is None:
                    continue
                tid, name, reason = e.tournament_id, e.name, UNRECOGNISED
                unreadable += 1
            buyin, received = BUYIN.search(text), RECEIVED.search(text)
            out[tid] = {"tournament_id": tid, "name": name, "reason": reason, "file": label,
                        "buyin": buyin[1].strip() if buyin else "", "received": received[1].strip() if received else "",
                        "hands": int(db.scalar("SELECT COUNT(*) FROM hands WHERE site = ? AND tournament_id = ?",
                                               (site, tid)) or 0),
                        "in_database": bool(db.scalar("SELECT COUNT(*) FROM tournaments WHERE site = ? AND tournament_id = ?",
                                                      (site, tid)))}
    trips = unreadable > FUSE_COUNT or (unreadable > 1 and unreadable / max(read, 1) > FUSE_SHARE)
    return {"remove": sorted(out.values(), key=lambda r: (not r["in_database"], r["reason"], r["tournament_id"])),
            "fuse": {"summaries": read, "unreadable": unreadable, "trips": trips},
            "ticket_entries": ticket_entries(db, site)}


def ticket_entries(db, site=SITE):
    """Tournaments started after a satellite won a seat to a tournament of the same name: probably a ticket entry."""
    won = db.query("SELECT t.tournament_id, t.name, t.started_at, t.prize_won, g.tag FROM tournaments t "
                   "JOIN tournament_tags g ON g.site = t.site AND g.tournament_id = t.tournament_id "
                   "WHERE t.site = ? AND t.prize_is_ticket AND g.tag LIKE 'target:%'", (site,))
    rows = db.query("SELECT tournament_id, name, started_at, buyin_total FROM tournaments WHERE site = ? AND format <> "
                    "'satellite' AND has_summary", (site,))
    found = []
    for s in won:
        target = _words(s["tag"].split(":", 1)[1])
        for t in rows:
            if target and target <= _words(t["name"]) and str(t["started_at"] or "") > str(s["started_at"] or ""):
                found.append({"tournament_id": t["tournament_id"], "name": t["name"], "started_at": str(t["started_at"]),
                              "buyin": float(t["buyin_total"] or 0), "satellite_id": s["tournament_id"],
                              "satellite": s["name"], "ticket": float(s["prize_won"] or 0)})
                break                                            # one ticket, the first tournament after it
    return found


def render(r):
    lines = []
    remove = [x for x in r["remove"] if x["in_database"]]
    lines.append(f"Would be removed from the database ({len(remove)}):")
    for x in remove or [None]:
        lines.append("  (none)" if x is None else
                     f"  #{x['tournament_id']} {x['name']} | {x['reason']} | buy-in {x['buyin'] or '?'} | "
                     f"received {x['received'] or '?'} | {x['hands']} hands in the database | {x['file']}")
    later = [x for x in r["remove"] if not x["in_database"]]
    lines.append(f"Not in the database, would stay out ({len(later)}):")
    for x in later or [None]:
        lines.append("  (none)" if x is None else
                     f"  #{x['tournament_id']} {x['name']} | {x['reason']} | buy-in {x['buyin'] or '?'} | "
                     f"received {x['received'] or '?'}")
    fz = r["fuse"]
    lines.append(f"Unreadable summaries: {fz['unreadable']} of {fz['summaries']}"
                 + (" - the safety fuse would trip: nothing would be removed for them" if fz["trips"] else ""))
    lines.append(f"Probably entered with a ticket, always kept ({len(r['ticket_entries'])}):")
    for x in r["ticket_entries"] or [None]:
        lines.append("  (none)" if x is None else
                     f"  #{x['tournament_id']} {x['name']} ({x['started_at'][:10]}, buy-in ${x['buyin']:,.2f}) "
                     f"<- ${x['ticket']:,.2f} ticket from #{x['satellite_id']} {x['satellite']}")
    return "\n".join(lines)
