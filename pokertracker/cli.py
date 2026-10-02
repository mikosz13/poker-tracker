import argparse

from .db import Database
from .importer import import_path
from .report import build_report
from .dashboard import dashboard_data, render_html as dashboard_html
from .tournament_report import render_html, render_text, tournament_data


def main(argv=None):
    p = argparse.ArgumentParser(prog="pokertracker", description="GGPoker tournament tracker")
    p.add_argument("--db", help="database URL (default: $DATABASE_URL or sqlite:///pokertracker.db)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create tables and views")
    imp = sub.add_parser("import", help="import hand histories / summaries (.txt, .pdf, .zip, folders)")
    imp.add_argument("paths", nargs="+")
    imp.add_argument("--no-equity", action="store_true", help="skip the all-in EV computation")
    imp.add_argument("--only-new", action="store_true", help="skip files that are unchanged since the last import")
    sub.add_parser("report", help="print results and statistics")
    app = sub.add_parser("app", help="open the desktop app")
    app.add_argument("--browser", action="store_true", help="use the default browser instead of a native window")
    app.add_argument("--port", type=int, default=0)
    dash = sub.add_parser("dashboard", help="all-tournament overview (HTML, phone friendly)")
    dash.add_argument("--html", metavar="FILE", default="dashboard.html")
    tr = sub.add_parser("tournament", help="post-tournament report (latest tournament if no id is given)")
    tr.add_argument("tournament_id", nargs="?", type=int)
    tr.add_argument("--html", metavar="FILE", help="also write a self-contained HTML report (phone friendly)")
    args = p.parse_args(argv)

    if args.cmd == "app":
        from .app import run
        run(args.db, args.port, args.browser)
        return 0

    with Database(args.db) as db:
        db.init_schema()       # idempotent; also refreshes the views
        if args.cmd == "import":
            print(f"database: {db.url}")
            for path in args.paths:
                s = import_path(db, path, equity=not args.no_equity, skip_unchanged=args.only_new)
                print(f"{path}: {s.files} files ({s.hand_files} hand histories, {s.summary_files} summaries) | "
                      f"{s.unchanged} unchanged | hands: {s.hands_new} new, {s.hands_duplicate} duplicates | all-ins with EV: {s.allins} | "
                      f"tournaments: {len(s.tournaments)}")
                if s.ignored:
                    print("  not imported (out of scope): " + ", ".join(
                        f"{n} {reason}" + (" files" if reason == "cash game" else "")
                        for reason, n in s.ignored_counts().items()))
                for msg in s.skipped:
                    print(f"  skipped {msg}")
        elif args.cmd == "report":
            print(build_report(db))
        elif args.cmd == "dashboard":
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(dashboard_html(dashboard_data(db)))
            print(f"HTML written to {args.html}")
        elif args.cmd == "tournament":
            tid = args.tournament_id or db.scalar(
                "SELECT tournament_id FROM tournaments t ORDER BY (SELECT MAX(played_at) FROM hands h "
                "WHERE h.site = t.site AND h.tournament_id = t.tournament_id) DESC LIMIT 1")
            data = tournament_data(db, tid) if tid else None
            print(render_text(data))
            if args.html and data:
                with open(args.html, "w", encoding="utf-8") as f:
                    f.write(render_html(data))
                print(f"HTML written to {args.html}")
    return 0
