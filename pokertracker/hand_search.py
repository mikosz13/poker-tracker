"""Hand search (docs/tasks/hand-search.md): one row per Hero hand with everything the filters need (hand_facts),
rebuilt after each import, and one parameterised query over it.

Every filter is a fixed piece of SQL with "?" placeholders; values never become part of the SQL text, and the
preflop actions come from a fixed list. The preflop counts are the Analysis v2 definitions (preflop.hand_stats), so
"3-bet" here finds exactly the hands Analysis counts as 3-bets.
"""
from .dashboard import hand_class
from .tournament_report import SITE

COLUMNS = ("site", "hand_id", "tournament_id", "played_at", "name", "buyin_total", "format", "position", "cards",
           "hand_class", "stack_bb", "action", "rfi", "shove", "threebet", "fold3", "all_in", "showdown", "net_bb",
           "adj_bb")

# preflop action filters: key -> SQL (no values), the Analysis v2 counts or Hero's first spot
ACTIONS = {
    "rfi": "rfi = 1",                                     # raise first in (no limpers), all-in included
    "open_raise": "action = 'open'",                      # Hero's first raise in an unraised pot, limpers or not
    "3bet_shove": "action = '3bet_shove'",
    "open_shove": "shove = 1",
    "limp": "action = 'limp'",                            # complete from the small blind included
    "call_vs_open": "action = 'call_vs_open'",
    "threebet": "threebet = 1",                           # a squeeze counts
    "fold_vs_open": "action = 'fold_vs_open'",
    "fold_to_3bet": "fold3 = 1",                          # after Hero's own open (not all-in), re-raised once
    "cold_4bet": "action = '4bet_cold'",
    "bb_check": "action = 'bb_check'",
    "fold_unopened": "action = 'fold_unopened'",
}
MAX_IDS = 5000          # result ids sent for next / previous in the replayer


def refresh_hand_facts(db, tournament_ids=None, site=SITE):
    """Rebuild the rows of these tournaments (all when None) from what is stored."""
    from .analysis import load_hands                    # here: analysis imports a lot, the importer imports us
    ids = None if tournament_ids is None else sorted(tournament_ids)
    where, args = "", ()
    if ids is not None:
        if not ids:
            return 0
        where = f" AND h.tournament_id IN ({', '.join('?' for _ in ids)})"
        args = tuple(ids)
    all_in = {r["hand_id"] for r in db.query(
        "SELECT DISTINCT a.hand_id FROM actions a JOIN hands h ON h.site = a.site AND h.hand_id = a.hand_id "
        f"WHERE a.site = ? AND a.nick = 'Hero' AND a.all_in{where}", (site, *args))}
    played = {r["hand_id"]: r["played_at"] for r in db.query(         # to the second (load_hands keeps minutes)
        f"SELECT h.hand_id, h.played_at FROM hands h WHERE h.site = ?{where}", (site, *args))}
    info = {r["tournament_id"]: r for r in db.query(
        "SELECT tournament_id, name, buyin_total, format FROM tournaments WHERE site = ?", (site,))}
    rows = []
    for h in load_hands(db, site, ids):
        t = info.get(h["tournament_id"]) or {}
        pf = h["pf"]
        rows.append((site, h["hand_id"], h["tournament_id"], played.get(h["hand_id"], h["at"]), t.get("name"), t.get("buyin_total"),
                     t.get("format"), h["position"], h["cards"] or None, hand_class(h["cards"]), round(h["stack_bb"], 2),
                     h["spot"], pf["rfi"], pf["shove"], pf["tb"], pf["f3"], int(h["hand_id"] in all_in),
                     int(h["showdown"]), round(h["net_bb"], 2), round(h["adj_bb"], 2)))
    if ids is None:
        db.execute("DELETE FROM hand_facts WHERE site = ?", (site,))
    else:
        db.execute(f"DELETE FROM hand_facts WHERE site = ? AND tournament_id IN ({', '.join('?' for _ in ids)})",
                   (site, *ids))
    db.executemany(f"INSERT INTO hand_facts ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", rows)
    return len(rows)


def _list(value):
    return [x for x in (value or "").split(",") if x]


def build_where(f, site=SITE):
    """(SQL after WHERE, parameters) for a filter dict of strings, as the API receives them; unknown or empty
    filters are ignored."""
    sql, args = ["site = ?"], [site]
    if f.get("since"):
        sql.append("played_at >= ?"); args.append(f["since"])
    if f.get("until"):
        sql.append("played_at <= ?"); args.append(f["until"])
    if f.get("buyin"):
        sql.append("buyin_total = ?"); args.append(float(f["buyin"]))
    if f.get("format"):
        sql.append("format = ?"); args.append(f["format"])
    for key, column in (("position", "position"), ("cards", "hand_class")):
        values = _list(f.get(key))
        if values:
            sql.append(f"{column} IN ({', '.join('?' for _ in values)})"); args += values
    if f.get("stack_min"):
        sql.append("stack_bb >= ?"); args.append(float(f["stack_min"]))
    if f.get("stack_max"):
        sql.append("stack_bb < ?"); args.append(float(f["stack_max"]))
    if f.get("action") in ACTIONS:
        sql.append(ACTIONS[f["action"]])
    for key in ("all_in", "showdown"):
        if f.get(key) in ("0", "1"):
            sql.append(f"{key} = ?"); args.append(int(f[key]))
    value = "adj_bb" if f.get("ev") == "1" else "net_bb"
    if f.get("result") == "won":
        sql.append(f"{value} > 0")
    elif f.get("result") == "lost":
        sql.append(f"{value} < 0")
    if f.get("min_bb"):
        sql.append(f"ABS({value}) >= ?"); args.append(float(f["min_bb"]))
    return " AND ".join(sql), args


def search(db, f, site=SITE, offset=0, limit=100):
    """Hands matching the filters, newest first: a page of rows, the totals, and the ids of the first MAX_IDS for
    next / previous in the replayer."""
    where, args = build_where(f, site)
    total = db.query(f"SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(adj_bb) AS adj FROM hand_facts WHERE {where}",
                     tuple(args))[0]
    page = db.query(f"SELECT hand_id, tournament_id, played_at, name, buyin_total, position, cards, stack_bb, action, "
                    f"all_in, showdown, net_bb, adj_bb FROM hand_facts WHERE {where} "
                    "ORDER BY played_at DESC, hand_id DESC LIMIT ? OFFSET ?", (*args, int(limit), int(offset)))
    ids = [r["hand_id"] for r in db.query(f"SELECT hand_id FROM hand_facts WHERE {where} "
                                          "ORDER BY played_at DESC, hand_id DESC LIMIT ?", (*args, MAX_IDS))]
    num = lambda x: round(float(x or 0), 1)
    return {"count": int(total["n"]), "net_bb": num(total["net"]), "adj_bb": num(total["adj"]),
            "offset": int(offset), "limit": int(limit), "ids": ids,
            "hands": [{**r, "played_at": str(r["played_at"])[:16], "stack_bb": num(r["stack_bb"]),
                       "net_bb": num(r["net_bb"]), "adj_bb": num(r["adj_bb"])} for r in page]}
