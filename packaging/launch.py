"""Entry point used by PyInstaller for the desktop build: the app window, or the command line when arguments are
given (`PokerTracker serve --port 8790`, `PokerTracker import FOLDER`; used by the packaged-app smoke test)."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()     # first: the equity worker processes start this same binary
    if len(sys.argv) > 1:
        from pokertracker.cli import main
        sys.exit(main(sys.argv[1:]))
    from pokertracker.app import main
    main()
