"""Post-tournament report: result, stack path, best/worst position and hands, all-in luck.

tournament_data() gathers everything from the database into a plain dict; render_text() and render_html()
only format it, so the numbers are identical everywhere.
"""
import html
from collections import defaultdict

SITE = "GGPoker"
HERO = "Hero"
MIN_POSITION_HANDS = 8        # smaller samples are shown but never called "best" or "worst"
TOP_N = 3

RANK_NAMES = dict(zip("23456789TJQKA", ["Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights", "Nines",
                                        "Tens", "Jacks", "Queens", "Kings", "Aces"]))
RANK_CHARS = "23456789TJQKA"


def _f(x):
    return None if x is None else float(x)


def describe_hand(score: int) -> str:
    """Human description of an evaluator score (see equity.evaluate for the layout)."""
    cat, nib = score >> 20, [(score >> s) & 15 for s in (16, 12, 8, 4, 0)]
    r = [RANK_NAMES[RANK_CHARS[n]] for n in nib]
    top = RANK_CHARS[nib[0]]
    return {0: f"{top} high", 1: f"pair of {r[0]}", 2: f"two pair, {r[0]} and {r[1]}",
            3: f"three {r[0]}", 4: f"{top}-high straight", 5: f"{top}-high flush",
            6: f"{r[0]} full of {r[1]}", 7: f"four {r[0]}", 8: f"{top}-high straight flush"}[cat]


def _strongest_showdown(rows, folded):
    try:
        import numpy as np
        from .equity import evaluate, parse_cards
    except ImportError:
        return None
    best = None
    for r in rows:
        if not r["showdown"] or r["hand_id"] in folded or not r["hole_cards"] or len((r["board"] or "").split()) < 5:
            continue
        score = int(evaluate(np.array([parse_cards(r["hole_cards"]) + parse_cards(r["board"])]))[0])
        if best is None or score >= best[0]:
            best = (score, r)
    if best is None:
        return None
    score, r = best
    return {"hand_id": r["hand_id"], "hand": describe_hand(score), "hole_cards": r["hole_cards"], "board": r["board"],
            "played_at": str(r["played_at"])[:16], "net_bb": r["net_bb"]}


def _moment(r):
    return {"hand_id": r["hand_id"], "hole_cards": r["hole_cards"], "board": r["board"] or "", "position": r["position"],
            "net_bb": round(r["net_bb"], 1), "pot_bb": round(r["pot_bb"], 1), "played_at": str(r["played_at"])[:16],
            "level": r["level"], "showdown": bool(r["showdown"])}


def tournament_data(db, tournament_id, site=SITE):
    t = db.query("SELECT * FROM tournaments WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    if not t:
        return None
    t = t[0]
    res = db.query("SELECT * FROM tournament_results WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    rows = db.query(
        "SELECT hh.hand_id, hh.level, hh.played_at, hh.big_blind, hh.position, hh.stack_bb, hh.net_won, hh.net_bb, "
        "hh.vpip, hh.pfr, hp.hole_cards, h.board, h.showdown, h.total_pot FROM hero_hands hh "
        "JOIN hands h ON h.site = hh.site AND h.hand_id = hh.hand_id "
        "JOIN hand_players hp ON hp.site = hh.site AND hp.hand_id = hh.hand_id AND hp.is_hero "
        "WHERE hh.site = ? AND hh.tournament_id = ? ORDER BY hh.played_at, hh.hand_id", (site, tournament_id))
    for r in rows:
        for k in ("big_blind", "stack_bb", "net_won", "net_bb", "total_pot"):
            r[k] = _f(r[k])
        r["pot_bb"] = (r["total_pot"] or 0) / r["big_blind"]
    folded = {r["hand_id"] for r in db.query(
        "SELECT DISTINCT a.hand_id FROM actions a JOIN hands h ON h.site = a.site AND h.hand_id = a.hand_id "
        "WHERE a.site = ? AND h.tournament_id = ? AND a.nick = ? AND a.action_type = 'folds'",
        (site, tournament_id, HERO))}

    data = {"tournament_id": tournament_id, "name": t["name"], "has_summary": bool(t["has_summary"]),
            "tags": [r["tag"] for r in db.query("SELECT tag FROM tournament_tags WHERE site = ? AND tournament_id = ? "
                                                "ORDER BY tag", (site, tournament_id))],
            "entries": [{"entry_no": int(e["entry_no"]), "level": int(e["entry_level"]),
                         "stack_bb": _f(e["start_stack_bb"]), "fresh": bool(e["starts_fresh"])}
                        for e in db.query("SELECT * FROM entries WHERE site = ? AND tournament_id = ? ORDER BY entry_no",
                                          (site, tournament_id))],
            "hands": len(rows)}
    if res:
        r = res[0]
        data["result"] = {"place": r["finish_place"], "players": r["players"], "prize": _f(r["prize_won"]),
                          "ticket": _f(r["ticket_value"]) > 0, "cost": _f(r["total_cost"]), "profit": _f(r["profit"]),
                          "roi_pct": _f(r["roi_pct"]), "started_at": str(r["started_at"])[:16]}
    if not rows:
        return data

    n = len(rows)
    data["levels"] = (min(r["level"] for r in rows), max(r["level"] for r in rows))
    data["period"] = (str(rows[0]["played_at"])[:16], str(rows[-1]["played_at"])[:16])
    data["vpip_pct"] = 100.0 * sum(r["vpip"] for r in rows) / n
    data["pfr_pct"] = 100.0 * sum(r["pfr"] for r in rows) / n
    data["net_bb"] = sum(r["net_bb"] for r in rows)
    last = rows[-1]
    end_bb = max(0.0, (last["stack_bb"] * last["big_blind"] + last["net_won"]) / last["big_blind"])
    path = [round(r["stack_bb"], 1) for r in rows] + [round(end_bb, 1)]   # stack before each hand, then after the last
    peak_idx = max(range(len(path)), key=lambda i: path[i])
    data["stack"] = {"path": path, "start_bb": path[0], "end_bb": path[-1],
                     "peak_bb": path[peak_idx], "peak_after_hands": peak_idx,     # 0 = at the start
                     "levels": [r["level"] for r in rows] + [last["level"]]}

    pos = defaultdict(lambda: {"hands": 0, "net_bb": 0.0, "vpip": 0, "pfr": 0})
    for r in rows:
        p = pos[r["position"] or "?"]
        p["hands"] += 1; p["net_bb"] += r["net_bb"]; p["vpip"] += r["vpip"]; p["pfr"] += r["pfr"]
    plist = [{"position": k, "hands": v["hands"], "net_bb": round(v["net_bb"], 1),
              "bb_per_100": round(100 * v["net_bb"] / v["hands"], 1),
              "vpip_pct": round(100 * v["vpip"] / v["hands"], 0), "pfr_pct": round(100 * v["pfr"] / v["hands"], 0)}
             for k, v in pos.items()]
    plist.sort(key=lambda p: -p["bb_per_100"])
    enough = [p for p in plist if p["hands"] >= MIN_POSITION_HANDS]
    data["positions"] = plist
    data["best_position"] = enough[0] if enough else None
    data["worst_position"] = enough[-1] if len(enough) > 1 else None

    by_net = sorted(rows, key=lambda r: r["net_bb"])
    data["biggest_wins"] = [_moment(r) for r in reversed(by_net[-TOP_N:]) if r["net_bb"] > 0]
    data["biggest_losses"] = [_moment(r) for r in by_net[:TOP_N] if r["net_bb"] < 0]
    data["strongest_showdown"] = _strongest_showdown(rows, folded)

    ko = db.query("SELECT COUNT(*) AS n, SUM(sole) AS sole FROM hero_knockouts WHERE site = ? AND tournament_id = ?",
                  (site, tournament_id))[0]
    data["knockouts"] = {"sole": int(ko["sole"] or 0), "shared": int(ko["n"]) - int(ko["sole"] or 0)}

    allins = db.query("SELECT * FROM hero_allins WHERE site = ? AND tournament_id = ? ORDER BY played_at",
                      (site, tournament_id))
    data["allins"] = {
        "count": len(allins),
        "net_bb": sum(_f(a["net_bb"]) for a in allins), "ev_bb": sum(_f(a["ev_bb"]) for a in allins),
        "luck_bb": sum(_f(a["luck_bb"]) for a in allins),
        "won": sum(1 for a in allins if a["result"] == "win"),
        "expected_won": sum(_f(a["equity"]) or 0 for a in allins),
        "notable": [{"hand_id": a["hand_id"], "kind": "bad beat" if a["bad_beat"] else "suckout", "hole_cards": a["hole_cards"],
                     "board": a["board_at_lock"], "street": a["lock_street"], "equity": _f(a["equity"]),
                     "luck_bb": _f(a["luck_bb"]), "played_at": str(a["played_at"])[:16]}
                    for a in allins if a["bad_beat"] or a["suckout"]]}
    return data


# ---- text -------------------------------------------------------------------

def _mom(m):
    board = m["board"] or "preflop"
    return (f"{m['hole_cards']} ({m['position']}) {m['net_bb']:+.1f} BB, pot {m['pot_bb']:.0f} BB, "
            f"board {board}{'' if m['showdown'] else ', no showdown'}")


def render_text(d) -> str:
    if d is None:
        return "Tournament not found."
    out = [f"{d['name']} #{d['tournament_id']}"]
    res = d.get("result")
    if res:
        prize = f"${res['prize']:,.2f}" + (" (ticket)" if res["ticket"] else "")
        out.append(f"  {res['started_at'][:10]} | place {res['place']}/{res['players']} | won {prize} on cost "
                   f"${res['cost']:,.2f} | ROI {res['roi_pct']:+,.0f}% (cash)")
    else:
        out.append("  no summary imported (no result / ROI)")
    if d["tags"]:
        out.append("  tags: " + ", ".join(d["tags"]))
    for e in d["entries"]:
        out.append(f"  entry #{e['entry_no']}: level {e['level']}, {e['stack_bb']:.0f} BB"
                   + ("" if e["fresh"] else " (history incomplete)"))
    if not d["hands"]:
        return "\n".join(out + ["  no hand history imported"])
    s = d["stack"]
    out += [f"  {d['hands']} hands, levels {d['levels'][0]}-{d['levels'][1]}, {d['period'][0]} to {d['period'][1]}",
            f"  VPIP {d['vpip_pct']:.1f}% | PFR {d['pfr_pct']:.1f}% | net {d['net_bb']:+.1f} BB",
            f"  stack: {s['start_bb']:.0f} BB -> {s['end_bb']:.0f} BB, peak {s['peak_bb']:.0f} BB after {s['peak_after_hands']} hands"]
    bp, wp = d["best_position"], d["worst_position"]
    if bp:
        out.append(f"  best position: {bp['position']} {bp['net_bb']:+.1f} BB in {bp['hands']} hands ({bp['bb_per_100']:+.0f} bb/100)")
    if wp:
        out.append(f"  worst position: {wp['position']} {wp['net_bb']:+.1f} BB in {wp['hands']} hands ({wp['bb_per_100']:+.0f} bb/100)")
    if not bp:
        out.append(f"  positions: fewer than {MIN_POSITION_HANDS} hands each, too small to rank")
    if d["biggest_wins"]:
        out.append("  biggest wins:")
        out += [f"    {_mom(m)}" for m in d["biggest_wins"]]
    if d["biggest_losses"]:
        out.append("  biggest losses:")
        out += [f"    {_mom(m)}" for m in d["biggest_losses"]]
    ko = d["knockouts"]
    if ko["sole"] or ko["shared"]:
        out.append(f"  knockouts: {ko['sole']}" + (f" (+{ko['shared']} shared)" if ko["shared"] else ""))
    sd = d["strongest_showdown"]
    if sd:
        out.append(f"  strongest showdown hand: {sd['hand']} ({sd['hole_cards']} on {sd['board']})")
    a = d["allins"]
    if a["count"]:
        out.append(f"  all-ins: {a['count']} | actual {a['net_bb']:+.1f} BB vs EV {a['ev_bb']:+.1f} BB | luck {a['luck_bb']:+.1f} BB "
                   f"| won {a['won']} (expected {a['expected_won']:.1f})")
        out.append("    (EV = what you win on average given your equity at the all-in; luck = actual - EV)")
        for n in a["notable"]:
            out.append(f"    {n['kind']}: {n['hole_cards']} on {n['board'] or 'preflop'} ({n['street']}) "
                       f"equity {100 * n['equity']:.1f}%, {n['luck_bb']:+.1f} BB")
    return "\n".join(out)


# ---- html (single self-contained file, readable on a phone) ---------------------

CSS = ("body{font:16px/1.4 system-ui,sans-serif;margin:0 auto;max-width:640px;padding:12px;background:#fff;color:#111}"
       "h1{font-size:1.2rem;margin:.2em 0}h2{font-size:1rem;margin:1.2em 0 .3em}.m{color:#666;font-size:.85rem}"
       ".k{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.k div{background:#f3f3f3;border-radius:8px;padding:8px}"
       ".k b{display:block;font-size:1.15rem}table{border-collapse:collapse;width:100%}td,th{padding:4px 6px;text-align:right;"
       "border-bottom:1px solid #ddd}td:first-child,th:first-child{text-align:left}.p{color:#0a7d2c}.n{color:#c0392b}"
       ".sh{color:#c62828}.sd{color:#1f62c9}.sc{color:#1b7f37}svg{width:100%;height:auto;background:#f3f3f3;border-radius:8px}"
       "@media(prefers-color-scheme:dark){body{background:#111;color:#eee}.k div,svg{background:#222}"
       "td,th{border-color:#333}.m{color:#aaa}.p{color:#4cd37b}.n{color:#ff7b6b}.sh{color:#ff6b6b}.sd{color:#5aa2ff}.sc{color:#4cd37b}}")
SUITS = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}


def _cards(text):
    out = []
    for c in (text or "").split():
        cls = f' class="s{c[1]}"' if c[1] in "hdc" else ""      # four-colour deck; spades keep the text colour
        out.append(f"<span{cls}>{html.escape(c[0] + SUITS[c[1]])}</span>")
    return " ".join(out) or "preflop"


def _sign(x, fmt="{:+.1f}"):
    return f'<span class="{"p" if x >= 0 else "n"}">{fmt.format(x)}</span>'


def _chart(stack):
    pts = stack["path"]
    w, h, top = 300, 110, max(max(pts), 1)
    xs = [i * w / max(len(pts) - 1, 1) for i in range(len(pts))]
    line = " ".join(f"{x:.1f},{h - 6 - (v / top) * (h - 12):.1f}" for x, v in zip(xs, pts))
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Stack in big blinds per hand">'
            f'<polyline fill="none" stroke="#2f80ed" stroke-width="2" points="{line}"/>'
            f'<text x="4" y="12" font-size="10" fill="currentColor">{top:.0f} BB</text></svg>')


def render_html(d) -> str:
    if d is None:
        return "<p>Tournament not found.</p>"
    e = html.escape
    parts = [f"<h1>{e(d['name'])} <span class=m>#{d['tournament_id']}</span></h1>"]
    res = d.get("result")
    if res:
        prize = f"${res['prize']:,.2f}" + (" ticket" if res["ticket"] else "")
        parts.append(f"<div class=k><div>Place<b>{res['place']}/{res['players']}</b></div><div>Prize<b>{prize}</b></div>"
                     f"<div>ROI (cash)<b>{res['roi_pct']:+,.0f}%</b></div></div>")
        parts.append(f"<p class=m>{e(res['started_at'])} | cost ${res['cost']:,.2f}</p>")
    if d["tags"]:
        parts.append(f"<p class=m>{e(', '.join(d['tags']))}</p>")
    if d["entries"]:
        parts.append("<p class=m>" + "; ".join(
            f"entry {x['entry_no']}: level {x['level']}, {x['stack_bb']:.0f} BB" + ("" if x["fresh"] else " (incomplete)")
            for x in d["entries"]) + "</p>")
    if d["hands"]:
        s, a = d["stack"], d["allins"]
        ko = d["knockouts"]
        ko_txt = str(ko["sole"]) + (f" +{ko['shared']} shared" if ko["shared"] else "")
        parts.append(f"<div class=k><div>Hands<b>{d['hands']}</b></div><div>VPIP / PFR<b>{d['vpip_pct']:.0f} / {d['pfr_pct']:.0f}</b></div>"
                     f"<div>Net<b>{_sign(d['net_bb'], '{:+.0f} BB')}</b></div><div>Knockouts<b>{ko_txt}</b></div></div>")
        parts.append(f"<h2>Stack (BB)</h2>{_chart(s)}<p class=m>{s['start_bb']:.0f} to {s['end_bb']:.0f} BB, peak "
                     f"{s['peak_bb']:.0f} BB after {s['peak_after_hands']} hands</p>")
        rows = "".join(f"<tr><td>{e(p['position'])}</td><td>{p['hands']}</td><td>{_sign(p['net_bb'])}</td>"
                       f"<td>{_sign(p['bb_per_100'], '{:+.0f}')}</td></tr>" for p in d["positions"])
        parts.append(f"<h2>Positions</h2><table><tr><th>Pos</th><th>Hands</th><th>BB</th><th>bb/100</th></tr>{rows}</table>")
        if not d["best_position"]:
            parts.append(f"<p class=m>Fewer than {MIN_POSITION_HANDS} hands per position: too small to rank.</p>")
        for title, key in (("Biggest wins", "biggest_wins"), ("Biggest losses", "biggest_losses")):
            if d[key]:
                items = "".join(f"<li>{_cards(m['hole_cards'])} {_sign(m['net_bb'])} BB ({e(str(m['position']))}), board "
                                f"{_cards(m['board'])}</li>" for m in d[key])
                parts.append(f"<h2>{title}</h2><ul>{items}</ul>")
        if d["strongest_showdown"]:
            sd = d["strongest_showdown"]
            parts.append(f"<h2>Strongest showdown hand</h2><p>{e(sd['hand'])}: {_cards(sd['hole_cards'])} on {_cards(sd['board'])}</p>")
        if a["count"]:
            items = "".join(f"<li>{e(n['kind'])}: {_cards(n['hole_cards'])} on {_cards(n['board'])}, equity "
                            f"{100 * n['equity']:.0f}%, {_sign(n['luck_bb'])} BB</li>" for n in a["notable"])
            parts.append(f"<h2>All-ins</h2><p>{a['count']} all-ins: actual {_sign(a['net_bb'])} BB, EV {_sign(a['ev_bb'])} BB, "
                         f"luck {_sign(a['luck_bb'])} BB. Won {a['won']} (expected {a['expected_won']:.1f}).</p>"
                         "<p class=m>EV = what you win on average given your equity at the all-in. "
                         f"Luck = actual - EV.</p><ul>{items}</ul>")
    return ("<!doctype html><html lang=en><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{e(d['name'])}</title><style>{CSS}</style><body>{''.join(parts)}</body></html>")
