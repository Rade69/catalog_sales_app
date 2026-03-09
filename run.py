import sys
from PySide6.QtWidgets import QApplication

from app.database.database import init_db
from app.gui.main_window import MainWindow
from app.services.installment_service import InstallmentService


def main() -> None:
    init_db()

    # Sinhronizuj status rata pri pokretanju
    InstallmentService.sync_statuses()

    app = QApplication(sys.argv)
    app.setApplicationName("Catalog Sales App")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
