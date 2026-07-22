"""PM2 entrypoint: run orchestrator ticks until DONE, then exit 0."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Ensure book/ is on sys.path when launched as script or module
BOOK_ROOT = Path(__file__).resolve().parent
if str(BOOK_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOK_ROOT))

from config import TICK_SLEEP_SECONDS, ensure_dirs  # noqa: E402
from models import load_env, require_api_key  # noqa: E402
from pipeline.orchestrator import tick  # noqa: E402
from pipeline.state import is_done, load_state, save_state  # noqa: E402


def _setup_logging() -> None:
    ensure_dirs()
    log_path = BOOK_ROOT / "logs" / "runner.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def main() -> int:
    _setup_logging()
    log = logging.getLogger("book.runner")
    ensure_dirs()
    load_env()

    if len(sys.argv) > 1 and sys.argv[1] in {"--status", "status"}:
        state = load_state()
        print(f"phase={state.phase} chapter={state.current_chapter} ticks={state.ticks}")
        print(f"done={is_done()} recommendation={state.managing_recommendation}")
        for n in range(1, 25):
            ch = state.chapter(n)
            print(
                f"  ch-{n:02d} drafted={ch.drafted} ok={ch.validation_ok} "
                f"chars={ch.body_chars} scores={ch.scores} revise={ch.needs_revision}"
            )
        return 0

    try:
        require_api_key()
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    if is_done():
        log.info("DONE file already present; exiting 0")
        return 0

    log.info("Starting blue heron book pipeline")
    while True:
        if is_done():
            log.info("Criteria met — exiting cleanly")
            return 0
        state = load_state()
        try:
            state = tick(state)
        except Exception:
            log.exception("Tick error; sleeping then retry (PM2 will also restart on crash)")
            save_state(state)
            time.sleep(max(TICK_SLEEP_SECONDS, 10))
            continue

        if state.phase == "complete" or is_done():
            log.info("Pipeline complete")
            return 0

        time.sleep(TICK_SLEEP_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
