"""
Centralno upravljanje putanjama — razvoj vs. .app bundle (macOS).

Kada aplikacija radi kao PyInstaller bundle, sys.frozen = True.
Podaci (baza, backup, logovi) idu u:
  - macOS:   ~/Library/Application Support/KataloskaProdaja/
  - Linux:   ~/.local/share/KataloskaProdaja/
  - Windows: %APPDATA%/KataloskaProdaja/

U razvoju (bez bundle-a) podaci ostaju u projektu, u mapi data/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "KataloskaProdaja"


def _user_data_dir() -> Path:
    """Vrati putanju do korisničkih podataka specifičnu za platformu."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


def get_data_dir() -> Path:
    """Vrati data/ folder — u razvoju lokalni, u bundle-u korisnički."""
    if getattr(sys, "frozen", False):
        d = _user_data_dir()
    else:
        # Razvoj: root projekta / data  (paths.py je u app/utils/)
        d = Path(__file__).resolve().parents[2] / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_db_path() -> Path:
    return get_data_dir() / "catalog_sales.db"


def get_backup_dir() -> Path:
    d = get_data_dir() / "backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_log_dir() -> Path:
    d = get_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d
