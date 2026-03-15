import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.database.database import DATABASE_URL, DB_PATH
from app.gui.icons import get_pixmap
from app.utils.logger import LOG_FILE
from app.utils.paths import get_backup_dir
from app.gui.pages.campaigns_page import CampaignsPage
from app.services.dashboard_service import DashboardService
from app.gui.pages.customers_page import CustomersPage
from app.gui.pages.dashboard_page import DashboardPage
from app.gui.pages.installments_page import InstallmentsPage
from app.gui.pages.orders_page import OrdersPage
from app.gui.pages.payments_page import PaymentsPage
from app.gui.pages.price_list_page import PriceListPage
from app.gui.pages.reports_page import ReportsPage
from app.gui.styles import APP_STYLESHEET
from app.utils.backup_manager import BackupManager
from app.services.historical_import_service import HistoricalImportService


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kataloška prodaja")
        self.resize(1440, 900)
        self.setMinimumSize(800, 500)  # spriječava sizeHint od strana da blokira maximize
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

        # Statusna traka
        self._setup_status_bar()

        self.switch_page(0, self.nav_buttons[0])
        self._update_overdue_badge()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Naslov
        title = QLabel("Kataloška prodaja")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        # Navigacija
        self.stack = QStackedWidget()
        self.pages = [
            ("Kontrolna ploča", DashboardPage()),
            ("Kupci", CustomersPage()),
            ("Narudžbe", OrdersPage()),
            ("Pogodnosti", CampaignsPage()),
            ("Cjenovnik", PriceListPage()),
            ("Uplate", PaymentsPage()),
            ("Izvještaji", ReportsPage()),
            ("Postavke", self._create_settings_page()),
        ]
        self.page_names = [
            "Kontrolna ploča", "Kupci", "Narudžbe", "Pogodnosti", "Cjenovnik",
            "Uplate", "Izvještaji", "Postavke"
        ]
        self.nav_buttons = []
        self.nav_icons = [
            "dashboard", "customers", "orders", "campaigns", "pricelist",
            "payments", "reports", "settings"
        ]

        for index, (name, page) in enumerate(self.pages):
            btn = self._create_nav_button(name, index, self.nav_icons[index])
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
            self.stack.addWidget(page)

        # Badge za kasne rate na "Uplate" dugmetu (index 5)
        self._overdue_badge = QLabel("")
        self._overdue_badge.setFixedSize(22, 22)
        self._overdue_badge.setAlignment(Qt.AlignCenter)
        self._overdue_badge.setStyleSheet("""
            QLabel {
                background-color: #ef4444;
                color: white;
                border-radius: 11px;
                font-size: 11px;
                font-weight: 700;
            }
        """)
        self._overdue_badge.hide()
        # Ubaci badge u layout "Uplate" dugmeta
        uplate_btn = self.nav_buttons[5]
        uplate_btn.layout().addWidget(self._overdue_badge)

        layout.addStretch(1)

        # Backup dugme na dnu sidebara
        backup_btn = self._create_backup_button()
        layout.addWidget(backup_btn)

        return sidebar

    def _create_nav_button(self, text: str, index: int, icon_name: str) -> QPushButton:
        """Kreira navigacijsko dugme sa ikonicom."""
        btn = QPushButton()
        btn.setProperty("nav", True)
        btn.setFixedHeight(44)
        btn.setCursor(Qt.PointingHandCursor)
        
        # Kreiraj layout za dugme (ikonica + tekst)
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Ikonica
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(get_pixmap(icon_name, "#9ca3af", 20))
        layout.addWidget(icon_label)
        
        # Tekst
        text_label = QLabel(text)
        text_label.setStyleSheet("color: #c5d5f0; font-size: 14px; font-weight: 600;")
        layout.addWidget(text_label, 1)
        
        layout.addStretch(1)
        
        # Sačuvaj reference za ažuriranje
        btn._icon_label = icon_label
        btn._text_label = text_label
        btn._icon_name = icon_name
        
        # Connect
        btn.clicked.connect(lambda checked=False, idx=index, button=btn: self.switch_page(idx, button))
        
        return btn

    def _update_nav_button_style(self, btn: QPushButton, is_active: bool) -> None:
        """Ažurira stil navigacijskog dugmeta."""
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.2);
                    border: none;
                    border-left: 4px solid #ffffff;
                    border-radius: 8px;
                    padding-left: 8px;
                }
                QLabel {
                    color: white;
                    font-weight: 700;
                    background: transparent;
                }
            """)
            btn._icon_label.setPixmap(get_pixmap(btn._icon_name, "#ffffff", 20))
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-left: 4px solid transparent;
                    border-radius: 8px;
                    padding-left: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.1);
                }
                QLabel {
                    color: #c5d5f0;
                    font-weight: 600;
                    background: transparent;
                }
            """)
            btn._icon_label.setPixmap(get_pixmap(btn._icon_name, "#c5d5f0", 20))

    def _create_backup_button(self) -> QPushButton:
        """Kreira backup dugme za dno sidebara."""
        btn = QPushButton()
        btn.setProperty("backup", True)
        btn.setFixedHeight(42)
        btn.setCursor(Qt.PointingHandCursor)

        # Kreiraj layout za dugme (ikonica + tekst)
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Backup ikonica (SVG)
        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setPixmap(get_pixmap("backup", "#ffffff", 20))
        layout.addWidget(icon_label)

        # Tekst
        text_label = QLabel("Backup")
        text_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
        layout.addWidget(text_label, 1)

        layout.addStretch(1)

        # Connect
        btn.clicked.connect(self._do_backup)

        return btn

    def _create_settings_page(self) -> QWidget:
        """Kreira stranicu Postavke."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(16)

        # ── Backup sekcija ──────────────────────────────────────────────
        backup_card = QFrame()
        backup_card.setProperty("card", True)
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(18, 18, 18, 18)
        backup_layout.setSpacing(8)

        backup_title = QLabel("Backup baze podataka")
        backup_title.setProperty("sectionTitle", True)
        backup_layout.addWidget(backup_title)

        backup_dir = get_backup_dir()
        existing_backups = sorted(backup_dir.glob("catalog_sales_*.db")) if backup_dir.exists() else []
        last_backup_text = (
            f"Zadnji backup: {existing_backups[-1].name}" if existing_backups
            else "Nema sačuvanih backupa."
        )
        self._backup_status_lbl = QLabel(last_backup_text)
        self._backup_status_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        backup_layout.addWidget(self._backup_status_lbl)

        backup_path_lbl = QLabel(f"Folder: {backup_dir}")
        backup_path_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        backup_path_lbl.setWordWrap(True)
        backup_layout.addWidget(backup_path_lbl)

        backup_btns = QHBoxLayout()
        backup_btn = QPushButton("💾 Kreiraj backup sada")
        backup_btn.setProperty("primary", True)
        backup_btn.setFixedWidth(210)
        backup_btn.clicked.connect(self._do_backup_from_settings)
        backup_btns.addWidget(backup_btn)

        open_backup_btn = QPushButton("📂 Otvori folder")
        open_backup_btn.setProperty("secondary", True)
        open_backup_btn.setFixedWidth(140)
        open_backup_btn.clicked.connect(lambda: self._open_in_files(backup_dir))
        backup_btns.addWidget(open_backup_btn)
        backup_btns.addStretch(1)
        backup_layout.addLayout(backup_btns)

        layout.addWidget(backup_card)

        # ── Log fajl sekcija ────────────────────────────────────────────
        log_card = QFrame()
        log_card.setProperty("card", True)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 18, 18, 18)
        log_layout.setSpacing(8)

        log_title = QLabel("Log fajl")
        log_title.setProperty("sectionTitle", True)
        log_layout.addWidget(log_title)

        log_path_lbl = QLabel(f"Putanja: {LOG_FILE}")
        log_path_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        log_path_lbl.setWordWrap(True)
        log_layout.addWidget(log_path_lbl)

        log_btns = QHBoxLayout()
        open_log_btn = QPushButton("📄 Otvori log fajl")
        open_log_btn.setProperty("secondary", True)
        open_log_btn.setFixedWidth(160)
        open_log_btn.clicked.connect(lambda: self._open_file(LOG_FILE))
        log_btns.addWidget(open_log_btn)

        open_log_dir_btn = QPushButton("📂 Otvori folder")
        open_log_dir_btn.setProperty("secondary", True)
        open_log_dir_btn.setFixedWidth(140)
        open_log_dir_btn.clicked.connect(lambda: self._open_in_files(LOG_FILE.parent))
        log_btns.addWidget(open_log_dir_btn)
        log_btns.addStretch(1)
        log_layout.addLayout(log_btns)

        layout.addWidget(log_card)

        # ── Historijski uvoz ────────────────────────────────────────────
        hist_card = QFrame()
        hist_card.setProperty("card", True)
        hist_layout = QVBoxLayout(hist_card)
        hist_layout.setContentsMargins(18, 18, 18, 18)
        hist_layout.setSpacing(8)

        hist_title = QLabel("Uvoz istorijskih podataka")
        hist_title.setProperty("sectionTitle", True)
        hist_layout.addWidget(hist_title)

        hist_desc = QLabel(
            "Uvezi kupce i narudžbe iz Excel evidencije rata.\n"
            "Podržan format: 4-1-11-2-1-3-Sanja-*.xlsx\n"
            "Duplikati (isti br. ugovora) se automatski preskaču."
        )
        hist_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        hist_desc.setWordWrap(True)
        hist_layout.addWidget(hist_desc)

        self._hist_status = QLabel("")
        self._hist_status.setStyleSheet("color: #6b7280; font-size: 12px;")
        self._hist_status.setWordWrap(True)
        hist_layout.addWidget(self._hist_status)

        hist_btn = QPushButton("Odaberi Excel fajl i uvezi...")
        hist_btn.setProperty("secondary", True)
        hist_btn.setFixedWidth(240)
        hist_btn.clicked.connect(self._do_historical_import)
        hist_layout.addWidget(hist_btn)

        layout.addWidget(hist_card)
        layout.addStretch(1)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        return page

    def _do_backup_from_settings(self) -> None:
        """Backup iz settings stranice — ažurira i status label."""
        self._do_backup()
        backup_dir = get_backup_dir()
        existing = sorted(backup_dir.glob("catalog_sales_*.db")) if backup_dir.exists() else []
        if existing and hasattr(self, "_backup_status_lbl"):
            self._backup_status_lbl.setText(f"Zadnji backup: {existing[-1].name}")

    @staticmethod
    def _open_in_files(path: Path) -> None:
        """Otvori folder u Files Manageru (cross-platform)."""
        path = Path(path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    @staticmethod
    def _open_file(path: Path) -> None:
        """Otvori fajl u podrazumjevanoj aplikaciji."""
        path = Path(path)
        if not path.exists():
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["start", str(path)], shell=True)
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _build_content(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.stack, 1)
        return wrapper

    def switch_page(self, index: int, button: QPushButton) -> None:
        self.stack.setCurrentIndex(index)
        self.page_title.setText(self.page_names[index])
        subtitles = {
            "Kontrolna ploča": "Pregled ključnih pokazatelja poslovanja.",
            "Kupci": "Baza kupaca, pretraga i unos u SQLite bazu.",
            "Narudžbe": "Kupovina sa snapshot cijenom i automatskim ratama.",
            "Pogodnosti": "Mjesečni katalog i import cijena iz Excel fajla.",
            "Cjenovnik": "Pregled i import cjenovnika iz Excel fajla.",
            "Uplate": "Evidencija svih uplata, uključujući djelimične uplate.",
            "Izvještaji": "Miesečni iznos uplaćenih sredstava i Excel eksport.",
            "Postavke": "Konfiguracija sistema i backup baze podataka.",
        }
        self.page_subtitle.setText(subtitles.get(self.page_names[index], ""))
        
        # Pozovi on_activate ako postoji
        page_widget = self.stack.currentWidget()
        if hasattr(page_widget, "on_activate"):
            page_widget.on_activate()
        
        self._update_last_refresh()
        self._update_overdue_badge()
        self._update_nav_button_style(button, is_active=True)
        
        # Resetuj ostala dugmad
        for btn in self.nav_buttons:
            if btn is not button:
                self._update_nav_button_style(btn, is_active=False)

    def _do_backup(self) -> None:
        """Kreira backup baze podataka."""
        try:
            backup_file = BackupManager.backup_database(DB_PATH, get_backup_dir())

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

    def _do_historical_import(self) -> None:
        """Uvozi historijske kupce i narudžbe iz Excel fajla."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Excel evidenciju rata",
            "",
            "Excel fajlovi (*.xlsx *.xls);;Svi fajlovi (*)"
        )
        if not file_path:
            return

        try:
            # Preview
            preview = HistoricalImportService.preview(file_path)
            reply = QMessageBox.question(
                self,
                "Potvrda uvoza",
                f"Pronađeno u fajlu:\n"
                f"  • {preview['orders']} ugovora (narudžbi)\n"
                f"  • {preview['customers']} unikatnih kupaca\n\n"
                f"Duplikati (isti br. ugovora) će biti preskočeni.\n\n"
                f"Nastavi s uvozom?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

            result = HistoricalImportService.import_from_excel(file_path)
            orders_proc, inst_created = HistoricalImportService.generate_installments(file_path)

            msg = (
                f"Uvoz završen:\n"
                f"  • Kreirano kupaca: {result.customers_created}\n"
                f"  • Kreirano narudžbi: {result.orders_created}\n"
                f"  • Kreirano rata: {inst_created}\n"
                f"  • Preskočeno (duplikati): {result.orders_skipped}"
            )
            if result.errors:
                msg += f"\n\nUpozorenja:\n" + "\n".join(result.errors[:5])

            if hasattr(self, "_hist_status"):
                self._hist_status.setText(
                    f"Zadnji uvoz: {result.customers_created} kupaca, "
                    f"{result.orders_created} narudžbi."
                )

            QMessageBox.information(self, "Uvoz uspješan", msg)

        except Exception as e:
            QMessageBox.critical(self, "Greška pri uvozu", str(e))

    def _setup_status_bar(self) -> None:
        """Postavlja statusnu traku na dno prozora."""
        status_bar = self.statusBar()
        status_bar.setStyleSheet("background: #111827; color: #9ca3af; font-size: 11px;")
        
        # Lijevo: putanja do baze
        db_path = DATABASE_URL.replace("sqlite:///", "")
        self.status_db_label = QLabel(f"📁 DB: {db_path}")
        status_bar.addPermanentWidget(self.status_db_label, 0)
        
        # Desno: zadnje osvježenje
        self.status_refresh_label = QLabel("Posljednje osvježenje: --:--:--")
        status_bar.addPermanentWidget(self.status_refresh_label, 0)

    def _update_overdue_badge(self) -> None:
        """Ažurira badge broj kasnih rata na Uplate dugmetu."""
        try:
            count = DashboardService.get_overdue_installments_count()
            if count > 0:
                self._overdue_badge.setText(str(count) if count < 100 else "99+")
                self._overdue_badge.show()
            else:
                self._overdue_badge.hide()
        except Exception:
            self._overdue_badge.hide()

    def _update_last_refresh(self) -> None:
        """Ažurira vrijeme zadnjeg osvježenja u statusnoj traci."""
        if hasattr(self, "status_refresh_label"):
            now = datetime.now().strftime("%H:%M:%S")
            self.status_refresh_label.setText(f"Posljednje osvježenje: {now}")
