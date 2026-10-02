"""Plain-text report built from the SQL views."""


def _f(x, nd=2):
    return f"{float(x):,.{nd}f}"


def build_report(db) -> str:
    out = []
    formats = db.query("SELECT * FROM format_results ORDER BY format")
    if formats:
        out.append("RESULTS BY FORMAT (ROI is cash only; tickets shown separately)")
        for r in formats:
            n = int(r["tournaments"])
            ticket = f" | tickets ${_f(r['ticket_value'], 0)}" if float(r["ticket_value"]) else ""
            out.append(f"  {r['format']:<10} n={n:<3} cost ${_f(r['total_cost'])} | cash ${_f(r['cash_won'])}"
                       f"{ticket} | ITM {int(r['itm'])}/{n} | ROI {_f(r['roi_pct'], 0)}%")
        out.append("")

    tags = db.query("SELECT * FROM tag_results ORDER BY tag")
    if tags:
        out.append("BY CATEGORY (cash ROI; a tournament counts under each of its tags)")
        for r in tags:
            n = int(r["tournaments"])
            out.append(f"  {r['tag']:<34} n={n:<3} cost ${_f(r['total_cost'])} | cash ${_f(r['cash_won'])} | "
                       f"ITM {int(r['itm'])}/{n} | ROI {_f(r['roi_pct'], 0)}%")
        out.append("")

    trs = db.query(
        "SELECT tr.*, "
        "(SELECT COUNT(*) FROM hands h WHERE h.site = tr.site AND h.tournament_id = tr.tournament_id) AS hands "
        "FROM tournament_results tr ORDER BY tr.started_at")
    if trs:
        out.append("TOURNAMENTS")
        for r in trs:
            notes = ["no hand history"] if int(r["hands"]) == 0 else []
            prize = f"${_f(r['prize_won'])}" + (" ticket" if float(r["ticket_value"]) else "")
            out.append(f"  {str(r['started_at'])[:10]}  {str(r['name'])[:34]:<34} {r['format']:<9} "
                       f"{r['finish_place']}/{r['players']}  cost ${_f(r['total_cost'])}  won {prize}"
                       + (f"  [{'; '.join(notes)}]" if notes else ""))
        out.append("")

    pending = db.query("SELECT tournament_id, name FROM tournaments WHERE NOT has_summary ORDER BY tournament_id")
    if pending:
        out.append(f"WITHOUT SUMMARY (no ROI yet): {', '.join(str(p['tournament_id']) for p in pending)}")
        out.append("")

    hero = db.query("SELECT COUNT(*) AS hands, ROUND(100.0 * SUM(vpip) / COUNT(*), 1) AS vpip, "
                    "ROUND(100.0 * SUM(pfr) / COUNT(*), 1) AS pfr, ROUND(SUM(net_bb), 0) AS net_bb FROM hero_hands")[0]
    if int(hero["hands"]):
        out.append(f"HERO: {int(hero['hands'])} hands | VPIP {_f(hero['vpip'], 1)}% | PFR {_f(hero['pfr'], 1)}% "
                   f"| net {_f(hero['net_bb'], 0)} BB")
        out.append("  by position:")
        for r in db.query("SELECT * FROM hero_position_stats ORDER BY bb_per_100 DESC"):
            out.append(f"    {str(r['position']):<7} {int(r['hands']):>4} hands  VPIP {_f(r['vpip_pct'], 0):>3}%  "
                       f"PFR {_f(r['pfr_pct'], 0):>3}%  {_f(r['bb_per_100'], 1):>7} bb/100")
        out.append("  by stack depth:")
        for r in db.query("SELECT * FROM hero_stack_depth_stats ORDER BY depth"):
            out.append(f"    {r['depth']:<12} {int(r['hands']):>4} hands  VPIP {_f(r['vpip_pct'], 0):>3}%  "
                       f"PFR {_f(r['pfr_pct'], 0):>3}%  {_f(r['bb_per_100'], 1):>7} bb/100")
    luck = db.query("SELECT COUNT(*) AS n, ROUND(SUM(net_bb), 1) AS net, ROUND(SUM(ev_bb), 1) AS ev, "
                    "ROUND(SUM(luck_bb), 1) AS luck, SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS won, "
                    "ROUND(SUM(equity), 1) AS exp_won, SUM(bad_beat) AS bb, SUM(suckout) AS so FROM hero_allins")[0]
    if int(luck["n"]):
        out += ["", f"ALL-IN LUCK ({int(luck['n'])} all-ins with cards to come)",
                f"  actual {_f(luck['net'], 1)} BB | expected {_f(luck['ev'], 1)} BB | luck {_f(luck['luck'], 1)} BB",
                f"  won {int(luck['won'])} (expected {_f(luck['exp_won'], 1)}) | bad beats {int(luck['bb'])} | "
                f"suckouts {int(luck['so'])}"]
        for r in db.query("SELECT * FROM hero_allins WHERE bad_beat = 1 OR suckout = 1 ORDER BY played_at"):
            kind = "bad beat" if r["bad_beat"] else "suckout"
            out.append(f"    {str(r['played_at'])[:16]}  {kind:<8} {r['hole_cards']} on {r['board_at_lock'] or 'preflop'} "
                       f"({r['lock_street']}) equity {_f(100 * float(r['equity']), 1)}%  {_f(r['luck_bb'], 1)} BB")
    return "\n".join(out) if out else "Database is empty. Run: pokertracker import <folder>"
