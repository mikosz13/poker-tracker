"""Desktop entry point: runs the local server and shows it in a native window (pywebview).

Without pywebview installed it falls back to the default browser, so the app works everywhere.
"""
import time
import webbrowser

from .server import serve_in_background


def run(db_url=None, port=0, browser=False):
    server, url = serve_in_background(db_url, port)
    if not browser:
        try:
            import webview
        except ImportError:
            browser = True
            print("pywebview not installed, opening in your browser instead (pip install pywebview).")
        else:
            webview.create_window("Poker Tracker", url, width=1100, height=820, min_size=(800, 600))
            webview.start()
            server.shutdown()
            return
    print(f"Poker Tracker is running at {url}  (Ctrl+C to quit)")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()


def main():
    import multiprocessing
    multiprocessing.freeze_support()     # needed for parallel equity in a packaged (.exe/.app) build
    run()


if __name__ == "__main__":
    main()
