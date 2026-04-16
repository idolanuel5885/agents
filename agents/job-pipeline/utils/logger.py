"""Structured logging setup with Rich console output."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    handlers = []

    # File handler (always full debug)
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    handlers.append(fh)

    # Console handler — try Rich, fall back to plain
    try:
        from rich.logging import RichHandler
        ch = RichHandler(
            level=level,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
    except ImportError:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    handlers.append(ch)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers, force=True)

    # Quiet noisy third-party loggers
    for noisy in ["httpx", "httpcore", "playwright", "asyncio", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
