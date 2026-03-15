from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


class BackupManager:
    @staticmethod
    def backup_database(db_path: str | Path, backup_dir: str | Path) -> Path:
        db_path = Path(db_path)
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"catalog_sales_{timestamp}.db"
        shutil.copy2(db_path, backup_file)
        return backup_file

    @staticmethod
    def auto_backup(db_path: str | Path, backup_dir: str | Path, keep: int = 7) -> Path:
        """Kreira backup i briše stare kopije (zadržava `keep` najnovijih)."""
        backup_file = BackupManager.backup_database(db_path, backup_dir)

        # Sortiraj po imenu (timestamp u imenu → sort = hronološki)
        existing = sorted(Path(backup_dir).glob("catalog_sales_*.db"))
        for old in existing[:-keep]:
            try:
                old.unlink()
            except Exception:
                pass

        return backup_file
