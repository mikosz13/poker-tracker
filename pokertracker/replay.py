"""Step-by-step replay of one hand, computed on the server so it can be tested.

Every step is a full snapshot (board, pot, stacks, chips committed on the street, who acted), so the UI only
draws snapshots and never re-implements poker accounting.
"""
SITE = "GGPoker"
HERO = "Hero"
BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
VERB = {"folds": "folds", "checks": "checks", "calls": "calls", "bets": "bets", "raises": "raises to",
        "posts_the_ante": "posts ante", "posts_small_blind": "posts small blind", "posts_big_blind": "posts big blind"}


def _n(x):
    return 0.0 if x is None else float(x)


def hand_replay(db, hand_id, site=SITE):
    h = db.query("SELECT * FROM hands WHERE site = ? AND hand_id = ?", (site, hand_id))
    if not h:
        return None
    h = h[0]
    players = db.query("SELECT * FROM hand_players WHERE site = ? AND hand_id = ? ORDER BY seat", (site, hand_id))
    actions = db.query("SELECT * FROM actions WHERE site = ? AND hand_id = ? ORDER BY action_order", (site, hand_id))
    board = (h["board"] or "").split()

    start = {p["nick"]: _n(p["stack"]) for p in players}
    stack = dict(start)
    commit = {p["nick"]: 0.0 for p in players}
    folded, allin = set(), set()
    pot, street, shown = 0.0, "preflop", 0
    steps = []

    def snap(label, acting=None, reveal=False, result=False):
        steps.append({
            "label": label, "street": street, "board": board[:shown], "pot": round(pot, 2), "result": result,
            "players": [{
                "nick": p["nick"], "seat": p["seat"], "position": p["position"], "hero": p["nick"] == HERO,
                "stack": round(stack[p["nick"]], 2), "commit": round(commit[p["nick"]], 2),
                "folded": p["nick"] in folded, "all_in": p["nick"] in allin, "acting": p["nick"] == acting,
                "cards": (p["hole_cards"] or "").split() if (p["nick"] == HERO or reveal) else [],
                "net": round(_n(p["net_won"]), 2) if result else None,
            } for p in players]})

    def deal_to(new_street):
        nonlocal street, shown, commit
        street = new_street
        shown = min(BOARD_LEN[new_street], len(board))
        commit = {n: 0.0 for n in commit}
        snap(f"{new_street.capitalize()}: {' '.join(board[:shown])}")

    snap("Seats and stacks")
    for a in actions:
        if a["street"] != street and a["street"] != "preflop":
            for st in ("flop", "turn", "river"):                  # deal every street up to this one
                if BOARD_LEN[st] > BOARD_LEN[street] and BOARD_LEN[st] <= BOARD_LEN[a["street"]]:
                    deal_to(st)
        nick, act, amount = a["nick"], a["action_type"], _n(a["amount"])
        if act == "posts_the_ante":
            add = amount
        elif act in ("posts_small_blind", "posts_big_blind", "calls"):
            add = amount
            commit[nick] += amount
        elif act in ("bets", "raises"):
            add = amount - commit[nick]
            commit[nick] = amount
        else:
            add = 0.0
            if act == "folds":
                folded.add(nick)
        stack[nick] -= add
        pot += add
        if a["all_in"]:
            allin.add(nick)
        text = f"{nick} {VERB.get(act, act)}" + (f" {amount:,.0f}" if amount and act != "folds" else "")
        snap(text + (" (all-in)" if a["all_in"] else ""), acting=nick)

    for st in ("flop", "turn", "river"):                          # run out the board after an all-in
        if BOARD_LEN[st] > BOARD_LEN[street] and len(board) >= BOARD_LEN[st]:
            deal_to(st)

    # Final state: real chip counts after uncalled bets were returned and pots were paid out
    for n in stack:
        stack[n] = start[n] + _n(next(p["net_won"] for p in players if p["nick"] == n))
    pot = 0.0
    commit = {n: 0.0 for n in commit}
    winners = [p["nick"] for p in players if _n(p["net_won"]) > 0]
    snap("Result: " + (", ".join(f"{w} wins {_n(next(p['net_won'] for p in players if p['nick'] == w)):+,.0f}"
                                 for w in winners) or "no winner recorded"),
         reveal=bool(h["showdown"]), result=True)

    return {"hand_id": hand_id, "tournament_id": h["tournament_id"], "level": h["level"],
            "small_blind": _n(h["small_blind"]), "big_blind": _n(h["big_blind"]), "ante": _n(h["ante"]),
            "played_at": str(h["played_at"])[:16], "table": h["table_name"], "total_pot": _n(h["total_pot"]),
            "steps": steps}
