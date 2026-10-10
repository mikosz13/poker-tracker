import json
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from pokertracker.server import serve_in_background
from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(cls.tmp.name)
        cls.exports = root / "exports"
        cls.exports.mkdir()
        for name, text in (("hh.txt", HISTORY), ("3way.txt", HAND_3WAY), ("sum.txt", SUMMARY_BOUNTY), ("sat.txt", SUMMARY_SATELLITE)):
            (cls.exports / name).write_text(text)
        cls.server, cls.url = serve_in_background(f"sqlite:///{root / 'test.db'}", watch_seconds=0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.url + path.lstrip("/")) as r:
            return r.status, r.read()

    def post(self, path, body, token=True):
        req = urllib.request.Request(self.url + path.lstrip("/"), data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **({"X-Token": self.server.token} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def wait_idle(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            st = json.loads(self.get("/api/status")[1])
            if not st.get("running"):
                return st
            time.sleep(0.05)
        self.fail("import did not finish")

    def test_flow(self):
        status, page = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(self.server.token.encode(), page)                 # token injected into the page
        self.assertEqual(self.post("/api/import", {"path": str(self.exports)}, token=False)[0], 403)
        self.assertEqual(self.post("/api/import", {"path": "/definitely/not/here"})[0], 400)
        status, s = self.post("/api/import", {"path": str(self.exports)})
        self.assertEqual(status, 202)
        st = self.wait_idle()
        self.assertIsNone(st["error"])
        self.assertEqual((st["result"]["hands_new"], st["result"]["summary_files"], st["done"], st["total"]), (4, 2, 4, 4))

        dash = json.loads(self.get("/api/dashboard")[1])
        self.assertEqual(dash["dashboard"]["tournaments"], 2)
        self.assertIsNotNone(dash["session"])

        ts = json.loads(self.get("/api/tournaments")[1])
        self.assertEqual({t["tournament_id"] for t in ts}, {900001, 900002, 900003})

        t = json.loads(self.get("/api/tournament/900001")[1])
        self.assertEqual(len(t["hand_list"]), 3)
        hand = json.loads(self.get("/api/hand/" + t["hand_list"][1]["hand_id"])[1])
        self.assertEqual((hand["prev_id"], hand["next_id"]), ("TM1000000001", "TM1000000003"))
        self.assertGreater(len(hand["steps"]), 5)

        settings = json.loads(self.get("/api/settings")[1])
        self.assertEqual(settings["import_folder"], str(self.exports))

    def test_analysis_endpoint(self):
        status, body = self.get("/api/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(set(json.loads(body)), {"overview", "leaks", "strengths", "money", "thresholds"})

    def test_deck_colours_setting(self):
        four = lambda: json.loads(self.get("/api/settings")[1])["four_color"]
        self.assertTrue(four())                                   # four colours by default
        status, body = self.post("/api/display", {"four_color": False})
        self.assertEqual((status, body["four_color"]), (200, False))
        self.assertFalse(four())
        self.assertEqual(self.post("/api/display", {"four_color": False}, token=False)[0], 403)
        self.post("/api/display", {"four_color": True})
        self.assertTrue(four())

    def test_watched_folder_imports_new_files(self):
        self.post("/api/import", {"path": str(self.exports)})
        self.wait_idle()
        self.assertTrue(self.post("/api/watch", {"enabled": True})[1]["watch"])
        extra = (self.exports / "later.txt")
        extra.write_text(HISTORY.replace("TM100000000", "TM200000000").replace("#900001", "#900004"))
        end = time.time() + 20
        while time.time() < end:
            st = json.loads(self.get("/api/status")[1])
            if st.get("source") == "auto" and not st["running"] and st.get("result"):
                break
            time.sleep(0.1)
        self.assertEqual((st["source"], st["result"]["hands_new"], st["result"]["unchanged"]), ("auto", 3, 4))
        self.post("/api/watch", {"enabled": False})
        extra.unlink()

    def test_not_found(self):
        for path in ("/api/tournament/1", "/api/hand/nope", "/api/nothing"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.get(path)
            self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
