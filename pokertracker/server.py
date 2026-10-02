"""Local HTTP server for the desktop app: JSON API + the single-page UI. Binds to 127.0.0.1 only."""
import json
import secrets
import threading
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .dashboard import dashboard_data
from .db import Database
from .importer import changed_files, import_files, list_files
from .replay import hand_replay
from .tournament_report import tournament_data

SITE = "GGPoker"
WEB = Path(__file__).resolve().parent / "web"
SESSION_GAP_HOURS = 3        # tournaments closer together than this belong to the same session
WATCH_SECONDS = 20           # how often a watched folder is checked for new exports


def _json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat(sep=" ") if isinstance(obj, datetime) else obj.isoformat()
    if isinstance(obj, (set, tuple)):
        return list(obj)
    raise TypeError(f"not serialisable: {type(obj)}")


def _ts(x):
    return x if isinstance(x, datetime) else datetime.fromisoformat(str(x))


# ---- queries used only by the app ----------------------------------------------

def tournaments_list(db, site=SITE):
    rows = db.query(
        "SELECT t.tournament_id, t.name, t.format, t.buyin_total, t.players, t.finish_place, t.prize_won, "
        "t.prize_is_ticket, t.reentries, t.has_summary, t.started_at, "
        "(SELECT MIN(h.played_at) FROM hands h WHERE h.site = t.site AND h.tournament_id = t.tournament_id) AS first_hand, "
        "(SELECT MAX(h.played_at) FROM hands h WHERE h.site = t.site AND h.tournament_id = t.tournament_id) AS last_hand, "
        "(SELECT COUNT(*) FROM hands h WHERE h.site = t.site AND h.tournament_id = t.tournament_id) AS hands, "
        "r.total_cost, r.profit, r.roi_pct, l.luck_bb, l.allins, "
        "(SELECT SUM(k.sole) FROM hero_knockouts k WHERE k.site = t.site AND k.tournament_id = t.tournament_id) AS knockouts "
        "FROM tournaments t "
        "LEFT JOIN tournament_results r ON r.site = t.site AND r.tournament_id = t.tournament_id "
        "LEFT JOIN tournament_luck l ON l.site = t.site AND l.tournament_id = t.tournament_id "
        "WHERE t.site = ?", (site,))
    tags = {}
    for r in db.query("SELECT tournament_id, tag FROM tournament_tags WHERE site = ?", (site,)):
        tags.setdefault(r["tournament_id"], []).append(r["tag"])
    for r in rows:
        r["tags"] = sorted(tags.get(r["tournament_id"], []))
        r["date"] = str(r["started_at"] or r["first_hand"] or "")[:16]
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def last_session(db, site=SITE):
    """Tournaments of the most recent session: played within SESSION_GAP_HOURS of each other."""
    ts = [t for t in tournaments_list(db, site) if t["last_hand"]]
    if not ts:
        return None
    ts.sort(key=lambda t: str(t["last_hand"]), reverse=True)
    session = [ts[0]]
    for t in ts[1:]:
        gap = _ts(session[-1]["first_hand"]) - _ts(t["last_hand"])
        if gap.total_seconds() > SESSION_GAP_HOURS * 3600:
            break
        session.append(t)
    known = [t for t in session if t["profit"] is not None]
    return {"tournaments": session, "count": len(session),
            "hands": sum(int(t["hands"]) for t in session),
            "profit": sum(float(t["profit"]) for t in known) if known else None,
            "with_result": len(known),
            "luck_bb": sum(float(t["luck_bb"] or 0) for t in session),
            "from": str(session[-1]["first_hand"])[:16], "to": str(session[0]["last_hand"])[:16]}


def tournament_detail(db, tournament_id, site=SITE):
    data = tournament_data(db, tournament_id, site)
    if data is None:
        return None
    data["hand_list"] = db.query(
        "SELECT hh.hand_id, hh.played_at, hh.level, hh.position, hh.net_bb, hp.hole_cards, h.board "
        "FROM hero_hands hh JOIN hands h ON h.site = hh.site AND h.hand_id = hh.hand_id "
        "JOIN hand_players hp ON hp.site = hh.site AND hp.hand_id = hh.hand_id AND hp.is_hero "
        "WHERE hh.site = ? AND hh.tournament_id = ? ORDER BY hh.played_at, hh.hand_id", (site, tournament_id))
    return data


def hand_detail(db, hand_id, site=SITE):
    r = hand_replay(db, hand_id, site)
    if r is None:
        return None
    ids = [x["hand_id"] for x in db.query(
        "SELECT hand_id FROM hands WHERE site = ? AND tournament_id = ? ORDER BY played_at, hand_id",
        (site, r["tournament_id"]))]
    i = ids.index(hand_id)
    r["prev_id"] = ids[i - 1] if i > 0 else None
    r["next_id"] = ids[i + 1] if i + 1 < len(ids) else None
    r["position_in_tournament"] = (i + 1, len(ids))
    return r


def get_setting(db, name):
    return db.scalar("SELECT value FROM settings WHERE name = ?", (name,))


def set_setting(db, name, value):
    db.execute("INSERT INTO settings (name, value) VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET value = excluded.value",
               (name, value))
    db.commit()


class ImportJob:
    """One import at a time, in a background thread, with progress the UI can poll."""

    def __init__(self, url):
        self.url = url
        self.lock = threading.Lock()
        self.state = {"running": False}

    def start(self, folder, skip_unchanged=True, source="manual"):
        with self.lock:
            if self.state.get("running"):
                return False
            self.state = {"running": True, "done": 0, "total": 0, "current": "", "source": source, "folder": folder,
                          "result": None, "error": None, "started_at": datetime.now().isoformat(timespec="seconds")}
        threading.Thread(target=self._run, args=(folder, skip_unchanged), daemon=True).start()
        return True

    def _run(self, folder, skip_unchanged):
        try:
            with Database(self.url) as db:
                files = list_files(Path(folder).expanduser())
                self.state["total"] = len(files)

                def progress(done, total, name):
                    self.state.update(done=done, total=total, current=name)

                s = import_files(db, files, progress=progress, skip_unchanged=skip_unchanged)
                result = {"files": s.files, "hand_files": s.hand_files, "summary_files": s.summary_files,
                          "unchanged": s.unchanged, "hands_new": s.hands_new, "hands_duplicate": s.hands_duplicate,
                          "allins": s.allins, "tournaments": len(s.tournaments), "skipped": s.skipped,
                          "source": self.state["source"], "finished_at": datetime.now().isoformat(timespec="seconds")}
                set_setting(db, "import_folder", folder)
                set_setting(db, "last_import", json.dumps(result))
                self.state["result"] = result
        except Exception as e:                                   # surface any problem in the UI
            self.state["error"] = f"{type(e).__name__}: {e}"
        finally:
            self.state["running"] = False

    def status(self):
        return dict(self.state)


def _watch_loop(job, url, stop, every):
    """Import new exports from the saved folder while watching is switched on."""
    while not stop.wait(every):
        try:
            with Database(url) as db:
                folder = get_setting(db, "import_folder")
                if get_setting(db, "watch") != "1" or not folder or job.state.get("running"):
                    continue
                if Path(folder).expanduser().exists() and changed_files(db, Path(folder).expanduser()):
                    job.start(folder, skip_unchanged=True, source="auto")
        except Exception:
            pass


# ---- HTTP ----------------------------------------------------------------------

def make_server(db_url=None, port=0, watch_seconds=None):
    token = secrets.token_urlsafe(16)
    with Database(db_url) as db:
        db.init_schema()
        url = db.url
    job = ImportJob(url)
    stop = threading.Event()
    threading.Thread(target=_watch_loop, args=(job, url, stop, watch_seconds or WATCH_SECONDS), daemon=True).start()

    def status_payload(db):
        last = get_setting(db, "last_import")
        return {**job.status(), "watch": get_setting(db, "watch") == "1",
                "import_folder": get_setting(db, "import_folder"), "last_import": json.loads(last) if last else None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):                     # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, default=_json).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                page = (WEB / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                return self._send(200, page.encode(), "text/html; charset=utf-8")
            with Database(url) as db:
                if path == "/api/dashboard":
                    return self._send(200, {"dashboard": dashboard_data(db), "session": last_session(db)})
                if path == "/api/tournaments":
                    return self._send(200, tournaments_list(db))
                if path.startswith("/api/tournament/"):
                    try:
                        d = tournament_detail(db, int(path.rsplit("/", 1)[1]))
                    except ValueError:
                        d = None
                    return self._send(200 if d else 404, d or {"error": "tournament not found"})
                if path.startswith("/api/hand/"):
                    d = hand_detail(db, path.rsplit("/", 1)[1])
                    return self._send(200 if d else 404, d or {"error": "hand not found"})
                if path == "/api/settings":
                    return self._send(200, {"import_folder": get_setting(db, "import_folder"), "database": url,
                                            "watch": get_setting(db, "watch") == "1",
                                            "four_color": get_setting(db, "four_color") != "0"})
                if path == "/api/status":
                    return self._send(200, status_payload(db))
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.headers.get("X-Token") != token:              # only our own page may trigger imports
                return self._send(403, {"error": "forbidden"})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/import":
                folder = (body.get("path") or "").strip()
                if not folder or not Path(folder).expanduser().exists():
                    return self._send(400, {"error": "Folder not found. Paste the folder where you save PokerCraft exports."})
                if not job.start(folder, skip_unchanged=not body.get("rescan"), source="manual"):
                    return self._send(409, {"error": "An import is already running."})
                with Database(url) as db:
                    set_setting(db, "import_folder", folder)
                    return self._send(202, status_payload(db))
            if self.path == "/api/watch":
                with Database(url) as db:
                    set_setting(db, "watch", "1" if body.get("enabled") else "0")
                    return self._send(200, status_payload(db))
            if self.path == "/api/display":                       # four-colour deck (default) or classic two colours
                with Database(url) as db:
                    set_setting(db, "four_color", "1" if body.get("four_color", True) else "0")
                    db.commit()
                    return self._send(200, {"four_color": get_setting(db, "four_color") != "0"})
            self._send(404, {"error": "not found"})

    class Server(ThreadingHTTPServer):
        def shutdown(self):
            stop.set()
            super().shutdown()

    server = Server(("127.0.0.1", port), Handler)
    server.token = token
    server.job = job
    return server


def serve_in_background(db_url=None, port=0, watch_seconds=None):
    server = make_server(db_url, port, watch_seconds)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"
