"""Cross-tournament dashboard: profit curve, luck-adjusted curve, results by category."""
import html
from datetime import datetime, timedelta

from .tournament_report import CSS, SITE, _sign

SMALL_SAMPLE = 30        # below this many tournaments the results are mostly variance


def _f(x):
    return 0.0 if x is None else float(x)


PERIODS = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "1w": timedelta(weeks=1), "2w": timedelta(weeks=2),
           "4w": timedelta(weeks=4), "3m": timedelta(days=91), "6m": timedelta(days=182), "max": None}


def period_start(period, now=None):
    """Start of a dashboard period counted back from now, as 'YYYY-MM-DD HH:MM:SS' (None for max)."""
    span = PERIODS.get(period)
    if span is None:
        return None
    return ((now or datetime.now()) - span).strftime("%Y-%m-%d %H:%M:%S")


# A tournament whose summary reports more entries (1 + re-entries) than were found in Hero's hands
INCOMPLETE = ("1 + COALESCE(r.reentries, 0) > COALESCE((SELECT t.entries_found FROM tournaments t "
              "WHERE t.site = r.site AND t.tournament_id = r.tournament_id), 0)")


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def dashboard_data(db, site=SITE, period="max", now=None):
    """Everything on the dashboard for one period: tournaments by start time, hands by their time."""
    since = period_start(period, now)
    t_when = " AND started_at >= ?" if since else ""
    h_when = " AND played_at >= ?" if since else ""
    arg = (since,) if since else ()

    trs = db.query(f"SELECT * FROM tournament_results WHERE site = ?{t_when} ORDER BY started_at", (site, *arg))
    cost = sum(_f(t["total_cost"]) for t in trs)
    cash = sum(_f(t["cash_won"]) for t in trs)
    tickets = sum(_f(t["ticket_value"]) for t in trs)
    itm = sum(int(t["in_the_money"]) for t in trs)
    profit_curve, profit_points, running = [], [], 0.0
    for t in trs:
        running += _f(t["cash_won"]) - _f(t["total_cost"])
        profit_curve.append(round(running, 2))
        profit_points.append({"at": str(t["started_at"])[:16], "name": t["name"], "buyin": _f(t["buyin_total"]),
                              "profit": round(_f(t["profit"]), 2), "total": round(running, 2)})
    per_tournament = db.query(
        "SELECT hh.tournament_id, MIN(hh.played_at) AS first_at, SUM(hh.net_bb) AS net_bb, "
        "COALESCE((SELECT SUM(a.luck_bb) FROM hero_allins a WHERE a.site = hh.site "
        f"AND a.tournament_id = hh.tournament_id{h_when.replace('played_at', 'a.played_at')}), 0) AS luck_bb, "
        "(SELECT name FROM tournaments t WHERE t.site = hh.site AND t.tournament_id = hh.tournament_id) AS name "
        f"FROM hero_hands hh WHERE hh.site = ?{h_when.replace('played_at', 'hh.played_at')} "
        "GROUP BY hh.site, hh.tournament_id ORDER BY first_at", (*arg, site, *arg))
    actual, adjusted, bb_points, a_run, j_run = [], [], [], 0.0, 0.0
    for r in per_tournament:
        a_run += _f(r["net_bb"])
        j_run += _f(r["net_bb"]) - _f(r["luck_bb"])
        actual.append(round(a_run, 1))
        adjusted.append(round(j_run, 1))
        bb_points.append({"at": str(r["first_at"])[:16], "name": r["name"], "net_bb": round(_f(r["net_bb"]), 1),
                          "luck_bb": round(_f(r["luck_bb"]), 1), "actual": round(a_run, 1), "adjusted": round(j_run, 1)})
    hero = db.query(f"SELECT COUNT(*) AS hands, SUM(vpip) AS vpip, SUM(pfr) AS pfr FROM hero_hands "
                    f"WHERE site = ?{h_when}", (site, *arg))[0]
    n_hands = int(hero["hands"])
    luck = db.query(f"SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(ev_bb) AS ev, SUM(luck_bb) AS luck "
                    f"FROM hero_allins WHERE site = ?{h_when}", (site, *arg))[0]
    ko = db.query(f"SELECT COUNT(*) AS n, SUM(sole) AS sole FROM hero_knockouts WHERE site = ?{h_when}",
                  (site, *arg))[0]
    with_hands = db.scalar(f"SELECT COUNT(DISTINCT tournament_id) FROM hands WHERE site = ?{h_when}", (site, *arg)) or 0
    r_when = t_when.replace("started_at", "r.started_at")
    return {
        "period": period if period in PERIODS else "max", "since": since,
        "knockouts": {"sole": int(ko["sole"] or 0), "shared": int(ko["n"]) - int(ko["sole"] or 0),
                      "per_tournament": int(ko["sole"] or 0) / with_hands if with_hands else None},
        "tournaments": len(trs), "cost": cost, "cash": cash, "tickets": tickets, "profit": cash - cost,
        "roi_pct": 100 * (cash - cost) / cost if cost else None,
        "itm": itm, "itm_pct": _pct(itm, len(trs)), "hands": n_hands,
        "vpip_pct": 100 * _f(hero["vpip"]) / n_hands if n_hands else None,
        "pfr_pct": 100 * _f(hero["pfr"]) / n_hands if n_hands else None,
        "profit_curve": profit_curve, "bb_actual": actual, "bb_adjusted": adjusted,
        "profit_points": profit_points, "bb_points": bb_points,
        "allins": {"count": int(luck["n"]), "net_bb": _f(luck["net"]), "ev_bb": _f(luck["ev"]),
                   "luck_bb": _f(luck["luck"])},
        "tags": [{"tag": r["tag"], "n": int(r["n"]), "cost": _f(r["cost"]), "cash": _f(r["cash"]),
                  "itm": int(r["itm"]), "itm_pct": _pct(int(r["itm"]), int(r["n"])),
                  "roi_pct": 100 * (_f(r["cash"]) - _f(r["cost"])) / _f(r["cost"]) if _f(r["cost"]) else None}
                 for r in db.query(
                     "SELECT g.tag, COUNT(*) AS n, SUM(r.total_cost) AS cost, SUM(r.cash_won) AS cash, "
                     "SUM(r.in_the_money) AS itm FROM tournament_results r JOIN tournament_tags g "
                     "ON g.site = r.site AND g.tournament_id = r.tournament_id "
                     f"WHERE r.site = ?{r_when} AND NOT (g.tag LIKE 'entry:%' AND {INCOMPLETE}) "
                     "GROUP BY g.tag ORDER BY g.tag", (site, *arg))],
        # late reg vs start leaves out tournaments whose summary reports more entries than the hands show
        "entry_incomplete": int(db.scalar(
            "SELECT COUNT(DISTINCT r.tournament_id) FROM tournament_results r JOIN tournament_tags g "
            "ON g.site = r.site AND g.tournament_id = r.tournament_id "
            f"WHERE r.site = ?{r_when} AND g.tag LIKE 'entry:%' AND {INCOMPLETE}", (site, *arg)) or 0),
        "by_buyin": [{"buyin": _f(r["buyin_total"]), "n": int(r["n"]), "cost": _f(r["cost"]), "profit": _f(r["profit"]),
                      "itm": int(r["itm"]), "itm_pct": _pct(int(r["itm"]), int(r["n"])),
                      "roi_pct": 100 * _f(r["profit"]) / _f(r["cost"]) if _f(r["cost"]) else None}
                     for r in db.query("SELECT buyin_total, COUNT(*) AS n, SUM(total_cost) AS cost, SUM(profit) AS profit, "
                                       f"SUM(in_the_money) AS itm FROM tournament_results WHERE site = ?{t_when} "
                                       "GROUP BY buyin_total ORDER BY buyin_total", (site, *arg))],
        "positions": [{"position": r["position"], "hands": int(r["hands"]), "net_bb": _f(r["net_bb"]),
                       "bb_per_100": _f(r["bb_per_100"]), "vpip_pct": _f(r["vpip_pct"]), "pfr_pct": _f(r["pfr_pct"])}
                      for r in db.query(
                          "SELECT position, COUNT(*) AS hands, 100.0 * SUM(vpip) / COUNT(*) AS vpip_pct, "
                          "100.0 * SUM(pfr) / COUNT(*) AS pfr_pct, SUM(net_bb) AS net_bb, "
                          "100.0 * SUM(net_bb) / COUNT(*) AS bb_per_100 FROM hero_hands "
                          f"WHERE site = ?{h_when} GROUP BY position ORDER BY bb_per_100 DESC", (site, *arg))],
        "recent": [{"date": str(t["started_at"])[:10], "name": t["name"], "buyin": _f(t["buyin_total"]),
                    "place": t["finish_place"], "players": t["players"], "cash": _f(t["cash_won"]),
                    "ticket": _f(t["ticket_value"]), "profit": _f(t["profit"])} for t in reversed(trs[-10:])],
    }


def _chart(series, colors=("#2f80ed", "#e67e22")):
    w, h = 300, 110
    values = [v for s in series for v in s]
    if len(values) < 2:
        return "<p class=m>Not enough data for a chart yet.</p>"
    lo, hi = min(0, min(values)), max(0, max(values))
    span = (hi - lo) or 1
    y = lambda v: h - 8 - (v - lo) / span * (h - 16)
    parts = [f'<line x1="0" x2="{w}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="currentColor" stroke-opacity=".3"/>']
    for s, color in zip(series, colors):
        pts = " ".join(f"{i * w / max(len(s) - 1, 1):.1f},{y(v):.1f}" for i, v in enumerate(s))
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>')
    return f'<svg viewBox="0 0 {w} {h}" role="img">{"".join(parts)}</svg>'


def render_html(d) -> str:
    e = html.escape
    if not d["tournaments"] and not d["hands"]:
        return "<!doctype html><meta charset=utf-8><p>No data yet. Import some files first.</p>"
    roi = f"{d['roi_pct']:+,.0f}%" if d["roi_pct"] is not None else "-"
    parts = ["<h1>Tournament dashboard</h1>",
             f"<div class=k><div>Tournaments<b>{d['tournaments']}</b></div>"
             f"<div>Profit (cash)<b>{_sign(d['profit'], '{:+,.0f} $')}</b></div><div>ROI<b>{roi}</b></div></div>",
             f"<p class=m>cost ${d['cost']:,.0f} | cash ${d['cash']:,.0f}"
             + (f" | tickets ${d['tickets']:,.0f} (not in ROI)" if d["tickets"] else "")
             + f" | in the money {d['itm']}/{d['tournaments']} | {d['hands']} hands</p>"]
    if d["tournaments"] < SMALL_SAMPLE:
        parts.append(f"<p class=m><b>Small sample ({d['tournaments']} tournaments).</b> In tournaments, results this "
                     f"small are mostly variance, so do not read much into the ROI yet.</p>")
    parts.append("<h2>Cash profit, cumulative ($)</h2>" + _chart([d["profit_curve"]]))
    a = d["allins"]
    parts.append("<h2>Net result in BB: actual vs all-in adjusted</h2>" + _chart([d["bb_actual"], d["bb_adjusted"]])
                 + "<p class=m><span style='color:#2f80ed'>&#9632;</span> actual &nbsp; "
                   "<span style='color:#e67e22'>&#9632;</span> adjusted (actual minus all-in luck)</p>")
    if a["count"]:
        parts.append(f"<p>{a['count']} all-ins: actual {_sign(a['net_bb'])} BB, EV {_sign(a['ev_bb'])} BB, "
                     f"luck {_sign(a['luck_bb'])} BB.</p>")
    if d["tags"]:
        rows = "".join(f"<tr><td>{e(t['tag'])}</td><td>{t['n']}</td><td>{t['itm']}</td>"
                       f"<td>{_sign(t['roi_pct'], '{:+,.0f}%')}</td></tr>" for t in d["tags"])
        parts.append(f"<h2>By category (cash ROI)</h2><table><tr><th>Tag</th><th>n</th><th>ITM</th><th>ROI</th></tr>{rows}</table>")
    if d["recent"]:
        rows = "".join(f"<tr><td>{r['date'][5:]}</td><td>${r['buyin']:,.0f}</td><td>{r['place']}/{r['players']}</td>"
                       f"<td>{_sign(r['profit'], '{:+,.0f}')}{' +ticket' if r['ticket'] else ''}</td></tr>" for r in d["recent"])
        parts.append(f"<h2>Recent tournaments</h2><table><tr><th>Date</th><th>Buy-in</th><th>Place</th><th>Profit $</th></tr>{rows}</table>")
    return ("<!doctype html><html lang=en><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Tournament dashboard</title><style>{CSS}</style><body>{''.join(parts)}</body></html>")
