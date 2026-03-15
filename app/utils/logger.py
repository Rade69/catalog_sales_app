"""
Centralizovano logiranje za aplikaciju.

Log fajl: data/logs/app.log
Rotacija: 1 MB, čuva 5 starih fajlova
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.utils.paths import get_log_dir

LOG_DIR = get_log_dir()
LOG_FILE = LOG_DIR / "app.log"

_initialized = False


def setup_logging() -> None:
    """Pozovi jednom pri pokretanju aplikacije."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler: max 1 MB, zadržava 5 starih fajlova
    fh = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console handler (samo WARNING+)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)
    root_logger.addHandler(ch)

    # Smanji šum od SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Uhvati neuhvaćene iznimke
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("app.uncaught").critical(
            "Neuhvaćena iznimka", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _excepthook


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
