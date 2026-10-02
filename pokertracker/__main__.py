import multiprocessing

from .cli import main

if __name__ == "__main__":          # guard: worker processes re-import this module on macOS and Windows
    multiprocessing.freeze_support()
    raise SystemExit(main())
