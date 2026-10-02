"""Cross-tournament dashboard: profit curve, luck-adjusted curve, results by category."""
import html

from .tournament_report import CSS, SITE, _sign

SMALL_SAMPLE = 30        # below this many tournaments the results are mostly variance


def _f(x):
    return 0.0 if x is None else float(x)


def dashboard_data(db, site=SITE):
    trs = db.query("SELECT * FROM tournament_results WHERE site = ? ORDER BY started_at", (site,))
    cost = sum(_f(t["total_cost"]) for t in trs)
    cash = sum(_f(t["cash_won"]) for t in trs)
    tickets = sum(_f(t["ticket_value"]) for t in trs)
    profit_curve, running = [], 0.0
    for t in trs:
        running += _f(t["cash_won"]) - _f(t["total_cost"])
        profit_curve.append(round(running, 2))
    per_tournament = db.query(
        "SELECT hh.tournament_id, MIN(hh.played_at) AS first_at, SUM(hh.net_bb) AS net_bb, "
        "COALESCE((SELECT SUM(a.luck_bb) FROM hero_allins a WHERE a.site = hh.site "
        "AND a.tournament_id = hh.tournament_id), 0) AS luck_bb "
        "FROM hero_hands hh WHERE hh.site = ? GROUP BY hh.site, hh.tournament_id ORDER BY first_at", (site,))
    actual, adjusted, a_run, j_run = [], [], 0.0, 0.0
    for r in per_tournament:
        a_run += _f(r["net_bb"])
        j_run += _f(r["net_bb"]) - _f(r["luck_bb"])
        actual.append(round(a_run, 1))
        adjusted.append(round(j_run, 1))
    hero = db.query("SELECT COUNT(*) AS hands, SUM(vpip) AS vpip, SUM(pfr) AS pfr FROM hero_hands")[0]
    n_hands = int(hero["hands"])
    luck = db.query("SELECT COUNT(*) AS n, SUM(net_bb) AS net, SUM(ev_bb) AS ev, SUM(luck_bb) AS luck "
                    "FROM hero_allins")[0]
    ko = db.query("SELECT COUNT(*) AS n, SUM(sole) AS sole, COUNT(DISTINCT tournament_id) AS t FROM hero_knockouts "
                  "WHERE site = ?", (site,))[0]
    with_hands = db.scalar("SELECT COUNT(DISTINCT tournament_id) FROM hands WHERE site = ?", (site,)) or 0
    return {
        "knockouts": {"sole": int(ko["sole"] or 0), "shared": int(ko["n"]) - int(ko["sole"] or 0),
                      "per_tournament": int(ko["sole"] or 0) / with_hands if with_hands else None},
        "tournaments": len(trs), "cost": cost, "cash": cash, "tickets": tickets, "profit": cash - cost,
        "roi_pct": 100 * (cash - cost) / cost if cost else None,
        "itm": sum(int(t["in_the_money"]) for t in trs), "hands": n_hands,
        "vpip_pct": 100 * _f(hero["vpip"]) / n_hands if n_hands else None,
        "pfr_pct": 100 * _f(hero["pfr"]) / n_hands if n_hands else None,
        "profit_curve": profit_curve, "bb_actual": actual, "bb_adjusted": adjusted,
        "allins": {"count": int(luck["n"]), "net_bb": _f(luck["net"]), "ev_bb": _f(luck["ev"]),
                   "luck_bb": _f(luck["luck"])},
        "tags": [{"tag": r["tag"], "n": int(r["tournaments"]), "cost": _f(r["total_cost"]), "cash": _f(r["cash_won"]),
                  "itm": int(r["itm"]), "roi_pct": _f(r["roi_pct"])}
                 for r in db.query("SELECT * FROM tag_results ORDER BY tag")],
        "by_buyin": [{"buyin": _f(r["buyin_total"]), "n": int(r["n"]), "cost": _f(r["cost"]), "profit": _f(r["profit"]),
                      "itm": int(r["itm"]), "roi_pct": 100 * _f(r["profit"]) / _f(r["cost"]) if _f(r["cost"]) else None}
                     for r in db.query("SELECT buyin_total, COUNT(*) AS n, SUM(total_cost) AS cost, SUM(profit) AS profit, "
                                       "SUM(in_the_money) AS itm FROM tournament_results WHERE site = ? "
                                       "GROUP BY buyin_total ORDER BY buyin_total", (site,))],
        "positions": [{"position": r["position"], "hands": int(r["hands"]), "net_bb": _f(r["net_bb"]),
                       "bb_per_100": _f(r["bb_per_100"]), "vpip_pct": _f(r["vpip_pct"]), "pfr_pct": _f(r["pfr_pct"])}
                      for r in db.query("SELECT * FROM hero_position_stats ORDER BY bb_per_100 DESC")],
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
