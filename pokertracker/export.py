"""Export (docs/tasks/export.md): a hand or a tournament as plain text for forums and chats, and CSV files of the
tournament list and of the hand search.

Opponents stay anonymous: they are named by their position only. A provisional prize (typed in while PokerCraft
offers no summary) is marked as provisional wherever it leaves the app.
"""
import csv
import io
import unicodedata
from datetime import date
from pathlib import Path

from .i18n import money, num, t
from .tournament_report import SITE

STREETS = ("preflop", "flop", "turn", "river")
ORDER = ("UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "BTN/SB", "SB", "BB")   # preflop acting order
BOARD_CARDS = {"flop": 3, "turn": 4, "river": 5}
VERBS = {"folds": "fold", "checks": "check", "calls": "call", "bets": "bet", "raises": "raise to"}


def _bb(lang, chips, big_blind):
    return num(lang, float(chips) / float(big_blind), 1) + " BB"


def _provisional(db, tournament_id, site=SITE):
    """True when the tournament's result (or its multi-day event's) counts a prize typed in."""
    event = db.scalar("SELECT COALESCE(event_id, tournament_id) FROM tournaments WHERE site = ? AND tournament_id = ?",
                      (site, tournament_id))
    return bool(event and db.scalar("SELECT provisional FROM tournament_results WHERE site = ? AND tournament_id = ?",
                                    (site, event)))


def hand_text(db, hand_id, lang="en", site=SITE):
    """One hand as plain text: header, stacks in BB by position, Hero's cards, every street, shown cards, result."""
    h = db.query("SELECT h.*, t.name FROM hands h JOIN tournaments t ON t.site = h.site AND t.tournament_id = h.tournament_id "
                 "WHERE h.site = ? AND h.hand_id = ?", (site, hand_id))
    if not h:
        return None
    h = h[0]
    bb = float(h["big_blind"])
    players = db.query("SELECT nick, position, seat, stack, hole_cards, net_won, is_hero FROM hand_players "
                       "WHERE site = ? AND hand_id = ? ORDER BY seat", (site, hand_id))
    players.sort(key=lambda p: ORDER.index(p["position"]) if p["position"] in ORDER else len(ORDER) + p["seat"])
    who = {p["nick"]: ("Hero" if p["is_hero"] else (p["position"] or f"Seat {p['seat']}")) for p in players}
    hero = next((p for p in players if p["is_hero"]), None)
    lines = [f"GGPoker · {h['name']} · " + t(lang, "ht.level", level=h["level"], sb=num(lang, h["small_blind"], 0),
                                                bb=num(lang, h["big_blind"], 0), ante=num(lang, h["ante"], 0)),
             t(lang, "ht.stacks") + " " + " · ".join(
                 f"{who[p['nick']]}{' (' + p['position'] + ')' if p['is_hero'] and p['position'] else ''} "
                 f"{_bb(lang, p['stack'], bb)}" for p in players)]
    if hero and hero["hole_cards"]:
        lines.append(f"Hero: {hero['hole_cards']}")
    board = (h["board"] or "").split()
    actions = db.query("SELECT nick, street, action_type, amount, all_in FROM actions WHERE site = ? AND hand_id = ? "
                       "ORDER BY action_order", (site, hand_id))
    for street in STREETS:
        acts = [a for a in actions if a["street"] == street and not a["action_type"].startswith("posts")]
        if not acts:
            continue
        cards = " ".join(board[:BOARD_CARDS[street]]) if street in BOARD_CARDS else ""
        cards = " " + cards if cards else ""
        said = [f"{who.get(a['nick'], a['nick'])} {VERBS.get(a['action_type'], a['action_type'])}"
                + (f" {_bb(lang, a['amount'], bb)}" if a["action_type"] in ("calls", "bets", "raises") else "")
                + (" all-in" if a["all_in"] else "") for a in acts]
        lines.append(f"{street.capitalize()}{cards}: " + ", ".join(said))
    if board:                                     # the whole board, also when an all-in left no later actions
        lines.append(f"Board: {' '.join(board)}")
    shown = [f"{who[p['nick']]} {p['hole_cards']}" for p in players if not p["is_hero"] and p["hole_cards"]]
    if shown:
        lines.append(t(lang, "ht.shown") + " " + ", ".join(shown))
    if hero:
        ev = db.scalar("SELECT ev_net FROM allin_ev WHERE site = ? AND hand_id = ? AND is_hero", (site, hand_id))
        result = t(lang, "ht.result", net=num(lang, float(hero["net_won"]) / bb, 1, sign=True))
        if ev is not None:
            result += " " + t(lang, "ht.ev", ev=num(lang, float(ev) / bb, 1, sign=True))
        lines.append(result)
    if _provisional(db, h["tournament_id"], site):
        lines.append(t(lang, "ht.provisional"))
    return "\n".join(lines)


def tournament_text(db, tournament_id, lang="en", site=SITE):
    """A tournament's result as a few lines (multi-day events under their last day, as in the app)."""
    r = db.query("SELECT * FROM tournament_results WHERE site = ? AND tournament_id = ?", (site, tournament_id))
    if not r:
        return None
    r = r[0]
    place = f"{r['finish_place']}/{r['players']}" if r["finish_place"] else "–"
    # entries from the cost: a multi-day event pays every flight that went through and its re-entries
    entries = round(float(r["total_cost"]) / float(r["buyin_total"])) if r["buyin_total"] else 1 + int(r["reentries"] or 0)
    lines = [f"GGPoker · {r['name']} · {str(r['started_at'])[:10]}",
             t(lang, "tt.line", buyin=money(lang, r["buyin_total"]), entries=entries, place=place,
               won=money(lang, float(r["cash_won"]) + float(r["ticket_value"] or 0)), cost=money(lang, r["total_cost"]),
               profit=money(lang, r["profit"], sign=True),
               roi=num(lang, r["roi_pct"], 0, sign=True) + "%" if r["roi_pct"] is not None else "–")]
    if int(r["provisional"] or 0):
        lines.append(t(lang, "ht.provisional"))
    elif int(r["summary_missing"] or 0):
        lines.append(t(lang, "tt.missing"))
    return "\n".join(lines)


def csv_text(header, rows, lang="en"):
    """CSV for Excel: UTF-8 with a BOM, a header row; Polish uses decimal commas and therefore ';' between fields."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";" if lang == "pl" else ",", lineterminator="\r\n")
    w.writerow(header)
    for row in rows:
        w.writerow([("" if v is None else (f"{v:.2f}".replace(".", ",") if lang == "pl" else f"{v:.2f}")
                     if isinstance(v, float) else v) for v in row])
    return "﻿" + out.getvalue()


def _f(x):
    return None if x is None else float(x)


def fold(text):
    """Text for matching: no case, no accents or Polish letters (the Tournaments tab's search does the same)."""
    text = unicodedata.normalize("NFD", str(text)).replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def name_matches(row, query):
    """Every word of the query is in the tournament's name (or "#id")."""
    hay = fold(row.get("name") or "") + f" #{row['tournament_id']}"
    return all(w in hay for w in fold(query or "").split())


def tournaments_csv(db, f, lang="en", site=SITE):
    """The tournament list with its filters (name search, since / until, buy-in, format, entry), as the Tournaments
    tab shows it."""
    from .server import tournaments_list                 # here: the server imports this module
    rows = []
    for r in tournaments_list(db, site):
        if f.get("q") and not name_matches(r, f["q"]):
            continue
        when = str(r["date"])
        if (f.get("since") and when < f["since"][:16]) or (f.get("until") and when > f["until"][:16]):
            continue
        if f.get("buyin") and str(r["buyin_total"]) != f["buyin"] and _f(r["buyin_total"]) != _f(f["buyin"]):
            continue
        if f.get("format") and r["format"] != f["format"]:
            continue
        if f.get("entry") and f"entry:{f['entry']}" not in r["tags"]:
            continue
        rows.append([when, r["tournament_id"], r["name"], r["format"], _f(r["buyin_total"]), 1 + int(r["reentries"] or 0),
                     r["finish_place"], r["players"], _f(r["prize_won"]), _f(r["prize_ticket"]), _f(r["total_cost"]),
                     _f(r["profit"]), _f(r["roi_pct"]), t(lang, "csv.yes") if int(r.get("provisional") or 0) else t(lang, "csv.no")])
    header = [t(lang, k) for k in ("csv.date", "csv.id", "csv.name", "csv.format", "csv.buyin", "csv.entries",
                                   "csv.place", "csv.players", "csv.cash", "csv.ticket", "csv.cost", "csv.profit",
                                   "csv.roi", "csv.provisional")]
    return csv_text(header, rows, lang), len(rows)


def hands_csv(db, f, lang="en", site=SITE):
    """Every hand of a search (no paging)."""
    from .hand_search import search
    total = search(db, f, site, limit=1)["count"]
    hands = search(db, f, site, limit=max(total, 1))["hands"]
    rows = [[h["played_at"], h["hand_id"], h["name"], h["position"], h["cards"], _f(h["stack_bb"]),
             t(lang, "spot." + h["action"]) if h["action"] else "",
             t(lang, "csv.yes") if h["all_in"] else t(lang, "csv.no"), t(lang, "csv.yes") if h["showdown"] else t(lang, "csv.no"),
             _f(h["net_bb"]), _f(h["adj_bb"])] for h in hands]
    header = [t(lang, k) for k in ("csv.date", "csv.hand", "csv.name", "csv.position", "csv.cards", "csv.stack",
                                   "csv.action", "csv.allin", "csv.showdown", "csv.bb", "csv.bbEv")]
    return csv_text(header, rows, lang), len(rows)


def save(text, stem, folder=None):
    """Write an export into the Downloads folder (the home folder without one), named with today's date; never
    overwrites: a second export the same day gets (2), (3) ..."""
    folder = Path(folder) if folder else (Path.home() / "Downloads" if (Path.home() / "Downloads").is_dir() else Path.home())
    path = folder / f"{stem}-{date.today().isoformat()}.csv"
    k = 2
    while path.exists():
        path = folder / f"{stem}-{date.today().isoformat()} ({k}).csv"
        k += 1
    path.write_text(text, encoding="utf-8")
    return str(path)
