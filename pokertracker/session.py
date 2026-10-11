"""What happened in the last session, at a glance: a summary sentence, hands to review, the session against your usual
play, the session's luck badge and a few short numbers.

Opponents are named by position only (as in the replayer); hashed IDs never leave the server.
"""
from datetime import datetime

from .analysis import confidence, load_hands
from .dashboard import luck_badge
from .tournament_report import SITE

MIN_HANDS_VS_USUAL = 50      # fewer session hands than this: no comparison with your usual play
REVIEW_POTS = 3              # biggest pots won and lost


def _f(x):
    return 0.0 if x is None else float(x)


def _ts(x):
    return datetime.fromisoformat(str(x)[:19])


def _placeholders(ids):
    return ", ".join("?" for _ in ids)


def _hand_story(db, hand_id, site, hero_equity=None):
    """Hero's cards against the opponent who won the pot (by position), the board and the result."""
    players = db.query("SELECT nick, position, hole_cards, net_won, is_hero FROM hand_players WHERE site = ? AND hand_id = ?",
                       (site, hand_id))
    hand = db.query("SELECT board, big_blind FROM hands WHERE site = ? AND hand_id = ?", (site, hand_id))[0]
    hero = next(p for p in players if p["is_hero"])
    others = [p for p in players if not p["is_hero"]]
    # Hero lost: the rival is whoever won the most; Hero won: whoever lost the most
    rival = (max(others, key=lambda p: _f(p["net_won"])) if _f(hero["net_won"]) < 0
             else min(others, key=lambda p: _f(p["net_won"])) if _f(hero["net_won"]) > 0 else None) if others else None
    if hero_equity is None:
        row = db.query("SELECT equity FROM allin_ev WHERE site = ? AND hand_id = ? AND is_hero", (site, hand_id))
        hero_equity = _f(row[0]["equity"]) if row and row[0]["equity"] is not None else None
    cards = (rival["hole_cards"] or "") if rival else ""
    return {"hand_id": hand_id, "hero_cards": hero["hole_cards"] or "", "rival": rival["position"] if rival else None,
            "rival_cards": cards if len(cards.split()) == 2 else "", "board": hand["board"] or "",
            "equity": round(hero_equity, 3) if hero_equity is not None else None,
            "net_bb": round(_f(hero["net_won"]) / _f(hand["big_blind"]), 1)}


def usual_play(db, exclude_ids, site=SITE):
    """Totals of Hero's hands outside the given tournaments: hands, VPIP and PFR counts, sum and sum of squares in BB."""
    ids = sorted(exclude_ids) or [-1]
    r = db.query("SELECT COUNT(*) AS n, SUM(vpip) AS vpip, SUM(pfr) AS pfr, SUM(net_bb) AS s, SUM(net_bb * net_bb) AS ss "
                 f"FROM hero_hands WHERE site = ? AND tournament_id NOT IN ({_placeholders(ids)})", (site, *ids))[0]
    return {"n": int(r["n"]), "vpip": _f(r["vpip"]), "pfr": _f(r["pfr"]), "sum": _f(r["s"]), "sumsq": _f(r["ss"])}


def totals(hands):
    return {"n": len(hands), "vpip": sum(h["vpip"] for h in hands), "pfr": sum(h["pfr"] for h in hands),
            "sum": sum(h["net_bb"] for h in hands), "sumsq": sum(h["net_bb"] ** 2 for h in hands)}


def vs_usual(session_hands, usual):
    """VPIP, PFR and bb/100 in the session against your usual play (totals of the rest), flagged only beyond chance."""
    n, m = len(session_hands), usual["n"]
    if n < MIN_HANDS_VS_USUAL or m < MIN_HANDS_VS_USUAL:
        return []
    out = []
    for key, label in (("vpip", "VPIP"), ("pfr", "PFR")):
        p_s = sum(h[key] for h in session_hands) / n
        p_u = usual[key] / m
        se = (p_u * (1 - p_u) / n) ** 0.5
        z = (p_s - p_u) / se if se else None
        out.append({"stat": label, "session": round(100 * p_s, 1), "usual": round(100 * p_u, 1), "unit": "%",
                    "z": round(z, 2) if z is not None else None, "confidence": confidence(z)})
    mean_s = sum(h["net_bb"] for h in session_hands) / n
    mean_u = usual["sum"] / m
    sd_u = max(0.0, (usual["sumsq"] - m * mean_u ** 2) / (m - 1)) ** 0.5
    z = (mean_s - mean_u) / (sd_u / n ** 0.5) if sd_u else None
    out.append({"stat": "bb/100", "session": round(100 * mean_s, 1), "usual": round(100 * mean_u, 1), "unit": "",
                "z": round(z, 2) if z is not None else None, "confidence": confidence(z)})
    return out


def max_at_once(intervals):
    """Most tournaments running at the same time, from (start, end) pairs."""
    # at the same moment an end counts before a start: one tournament finishing as the next begins is not two at once
    events = sorted([(s, 1) for s, _ in intervals] + [(e, -1) for _, e in intervals])
    best = cur = 0
    for _, step in events:
        cur += step
        best = max(best, cur)
    return best


def session_insights(db, tournaments, site=SITE):
    """tournaments: rows of the session as tournaments_list builds them (newest first)."""
    tids = {t["tournament_id"] for t in tournaments}
    if not tids:
        return None
    mine = load_hands(db, site, tids)
    ph, args = _placeholders(tids), (site, *tids)

    # busts: the hand after which an entry's stack was zero
    busts = []
    for h in mine:
        if h["stack_bb"] + h["net_bb"] <= 0.005:
            story = _hand_story(db, h["hand_id"], site)
            story.update(tournament_id=h["tournament_id"], at=h["at"],
                         name=next(t["name"] for t in tournaments if t["tournament_id"] == h["tournament_id"]))
            busts.append(story)
    allins = db.query(f"SELECT hand_id, tournament_id, equity, ev_bb, invested_bb, luck_bb, bad_beat, suckout "
                      f"FROM hero_allins WHERE site = ? AND tournament_id IN ({ph})", args)
    beats = [dict(_hand_story(db, a["hand_id"], site, _f(a["equity"])), kind="bad beat" if a["bad_beat"] else "suckout",
                  luck_bb=round(_f(a["luck_bb"]), 1)) for a in allins if a["bad_beat"] or a["suckout"]]
    by_net = sorted(mine, key=lambda h: h["net_bb"])
    pots = {"lost": [_hand_story(db, h["hand_id"], site) for h in by_net[:REVIEW_POTS] if h["net_bb"] < 0],
            "won": [_hand_story(db, h["hand_id"], site) for h in reversed(by_net[-REVIEW_POTS:]) if h["net_bb"] > 0]}

    badge = luck_badge(allins)
    starts = [_ts(t["first_hand"]) for t in tournaments if t["first_hand"]]
    ends = [_ts(t["last_hand"]) for t in tournaments if t["last_hand"]]
    entries = {r["tournament_id"]: int(r["n"]) for r in db.query(
        f"SELECT tournament_id, COUNT(*) AS n FROM entries WHERE site = ? AND tournament_id IN ({ph}) GROUP BY tournament_id",
        args)}
    reentries = cost = 0
    for t in tournaments:
        k = int(t["reentries"]) if t["has_summary"] and t["reentries"] is not None else max(0, entries.get(t["tournament_id"], 1) - 1)
        reentries += k
        cost += k * _f(t["buyin_total"])
    placed = [t for t in tournaments if t["finish_place"]]
    best = min(placed, key=lambda t: t["finish_place"] / max(1, t["players"] or 1)) if placed else None
    numbers = {"minutes": round((max(ends) - min(starts)).total_seconds() / 60) if starts and ends else None,
               "max_at_once": max_at_once([(_ts(t["first_hand"]), _ts(t["last_hand"])) for t in tournaments
                                           if t["first_hand"] and t["last_hand"]]),
               "knockouts": int(sum(_f(t["knockouts"]) for t in tournaments)),
               "reentries": reentries, "reentry_cost": round(cost, 2),
               "best": {"name": best["name"], "place": best["finish_place"], "players": best["players"]} if best else None}
    result = {"busts": busts, "beats": beats, "pots": pots, "luck": badge, "vs_usual": vs_usual(mine, usual_play(db, tids, site)),
              "numbers": numbers, "hands": len(mine)}
    result["summary"] = summary_sentence(tournaments, result)
    return result


def summary_sentence(tournaments, s):
    known = [t for t in tournaments if t["profit"] is not None]
    itm = sum(1 for t in known if _f(t["prize_won"]) > 0)
    parts = [f"{len(tournaments)} tournament{'s' if len(tournaments) != 1 else ''}"]
    if known:
        profit = sum(_f(t["profit"]) for t in known)
        parts.append(f"{itm} in the money, {'+' if profit >= 0 else '−'}${abs(profit):,.2f}"
                     + (f" ({len(tournaments) - len(known)} without a summary yet)" if len(known) < len(tournaments) else ""))
    else:
        parts.append("no summaries yet, so no result")
    text = ", ".join(parts) + "."
    b = s["luck"]
    if b["count"]:
        luck = f" All-in luck {'+' if b['luck_bb'] >= 0 else '−'}{abs(b['luck_bb']):,.0f} BB, {b['level'].lower()}"
        text += luck + (f" (about 1 in {b['one_in']})." if b.get("one_in") and b["level"] != "Average" else ".")
    if s["busts"]:
        text += f" Busted {len(s['busts'])} time{'s' if len(s['busts']) != 1 else ''}"
        # the most painful bust: as the favourite, for the most chips (equity x BB lost)
        worst = max((x for x in s["busts"] if x["equity"] is not None and x["equity"] >= 0.5 and x["rival_cards"]),
                    key=lambda x: x["equity"] * abs(x["net_bb"]), default=None)
        if worst and worst["rival_cards"]:
            text += (f"; worth a look: {_short(worst['hero_cards'])} vs {_short(worst['rival_cards'])} "
                     f"in {worst['name']}")
        text += "."
    return text


def _short(cards):
    """'Kh Kd' -> 'KK', 'As Qd' -> 'AQo', 'As Qs' -> 'AQs'."""
    c = cards.split()
    if len(c) != 2:
        return cards
    order = "23456789TJQKA"
    hi, lo = sorted(c, key=lambda x: order.index(x[0]), reverse=True)
    return hi[0] + lo[0] if hi[0] == lo[0] else hi[0] + lo[0] + ("s" if hi[1] == lo[1] else "o")
