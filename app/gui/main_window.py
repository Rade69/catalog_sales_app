from pathlib import Path

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database.database import DATABASE_URL
from app.gui.pages.campaigns_page import CampaignsPage
from app.gui.pages.customers_page import CustomersPage
from app.gui.pages.dashboard_page import DashboardPage
from app.gui.pages.installments_page import InstallmentsPage
from app.gui.pages.orders_page import OrdersPage
from app.gui.pages.payments_page import PaymentsPage
from app.gui.pages.reports_page import ReportsPage
from app.gui.styles import APP_STYLESHEET
from app.utils.backup_manager import BackupManager


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kataloška prodaja — pregled koncepta")
        self.resize(1440, 900)
        self.setStyleSheet(APP_STYLESHEET)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        sidebar = self._build_sidebar()
        content = self._build_content()

        root_layout.addWidget(sidebar, 0)
        root_layout.addWidget(content, 1)

        self.setCentralWidget(root)
        self.switch_page(0, self.nav_buttons[0])

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(255)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Kataloška prodaja")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("offline desktop koncept")
        subtitle.setStyleSheet("color: #9ca3af; padding: 0 12px 12px 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.stack = QStackedWidget()
        self.pages = [
            ("Dashboard", DashboardPage()),
            ("Kupci", CustomersPage()),
            ("Kampanje", CampaignsPage()),
            ("Narudžbe", OrdersPage()),
            ("Rate", InstallmentsPage()),
            ("Uplate", PaymentsPage()),
            ("Izvještaji", ReportsPage()),
        ]
        self.nav_buttons = []

        for index, (name, page) in enumerate(self.pages):
            btn = QPushButton(name)
            btn.setProperty("nav", True)
            btn.clicked.connect(lambda checked=False, idx=index, button=btn: self.switch_page(idx, button))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
            self.stack.addWidget(page)

        layout.addStretch(1)

        # Backup dugme
        backup_btn = QPushButton("💾 Backup baze")
        backup_btn.setProperty("secondary", True)
        backup_btn.clicked.connect(self._do_backup)
        layout.addWidget(backup_btn)

        footer = QLabel("Verzija 0.5 — Dashboard sa KPI-jevima")
        footer.setStyleSheet("color: #9ca3af; padding: 8px 12px;")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        return sidebar

    def _build_content(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 16, 18, 16)

        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel("Početni pregled modula i toka rada aplikacije.")
        self.page_subtitle.setObjectName("PageSubtitle")

        title_box = QVBoxLayout()
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)

        topbar_layout.addLayout(title_box)
        topbar_layout.addStretch(1)

        layout.addWidget(topbar)
        self.stack.setObjectName("ContentArea")
        layout.addWidget(self.stack, 1)
        return wrapper

    def switch_page(self, index: int, button: QPushButton) -> None:
        self.stack.setCurrentIndex(index)
        self.page_title.setText(self.pages[index][0])
        subtitles = {
            "Dashboard": "Početni pregled modula i toka rada aplikacije.",
            "Kupci": "Baza kupaca, pretraga i pravi unos u SQLite bazu.",
            "Kampanje": "Mjesečni katalog i import cijena iz Excel fajla.",
            "Narudžbe": "Kupovina sa snapshot cijenom i automatskim ratama.",
            "Rate": "Plan otplate po narudžbi i praćenje kašnjenja.",
            "Uplate": "Evidencija svih uplata, uključujući djelimične uplate.",
            "Izvještaji": "Mjesečni iznos uplaćenih sredstava i Excel eksport.",
        }
        self.page_subtitle.setText(subtitles.get(self.pages[index][0], ""))
        page_widget = self.pages[index][1]
        if hasattr(page_widget, "on_activate"):
            page_widget.on_activate()
        self._set_active_button(button)

    def _set_active_button(self, active_button: QPushButton) -> None:
        for btn in self.nav_buttons:
            btn.setProperty("active", btn is active_button)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _do_backup(self) -> None:
        """Kreira backup baze podataka."""
        try:
            # Izvuci putanju do baze iz DATABASE_URL
            db_path = DATABASE_URL.replace("sqlite:///", "")
            backup_dir = Path(__file__).resolve().parents[3] / "backup"
            
            backup_file = BackupManager.backup_database(db_path, backup_dir)
            
            QMessageBox.information(
                self,
                "Backup uspješan",
                f"Backup kreiran:\n{backup_file}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Greška pri backup-u",
                f"Backup nije uspio:\n{str(e)}"
            )
