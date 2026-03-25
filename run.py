import sys

from PySide6.QtWidgets import QApplication

from app.utils.logger import setup_logging, get_logger
from app.database.database import run_migrations, DB_PATH
from app.gui.main_window import MainWindow
from app.services.installment_service import InstallmentService
from app.utils.backup_manager import BackupManager
from app.utils.paths import get_backup_dir


def main() -> None:
    setup_logging()
    log = get_logger("app.startup")
    log.info("Pokretanje aplikacije")

    # Run Alembic migrations to ensure database schema is up to date
    run_migrations()
    log.info("Alembic migracije primijenjene, baza: %s", DB_PATH)

    # Automatski backup pri pokretanju
    try:
        backup_file = BackupManager.auto_backup(DB_PATH, get_backup_dir(), keep=7)
        log.info("Auto-backup kreiran: %s", backup_file.name)
    except Exception:
        log.exception("Auto-backup nije uspio")

    # Sinhronizuj status rata pri pokretanju
    try:
        InstallmentService.sync_statuses()
        log.info("Statusi rata sinhronizovani")
    except Exception:
        log.exception("sync_statuses nije uspio")

    app = QApplication(sys.argv)
    app.setApplicationName("Kataloška prodaja")

    window = MainWindow()
    window.show()

    log.info("GUI pokrenut")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
