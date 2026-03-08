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
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.database.database import DATABASE_URL
from app.gui.icons import get_pixmap
from app.gui.pages.campaigns_page import CampaignsPage
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

        # Statusna traka
        self._setup_status_bar()

        self.switch_page(0, self.nav_buttons[0])

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
            ("Kampanje", CampaignsPage()),
            ("Cjenovnik", PriceListPage()),
            ("Uplate", PaymentsPage()),
            ("Izvještaji", ReportsPage()),
            ("Postavke", self._create_settings_page()),
        ]
        self.page_names = [
            "Kontrolna ploča", "Kupci", "Narudžbe", "Kampanje", "Cjenovnik",
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

            # Dodaj stranicu u stack (osim Postavke koji je inline widget)
            if index < 7:
                self.stack.addWidget(page)
            else:
                self.stack.addWidget(self._create_settings_page())

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

        # Cloud ikonica
        icon_label = QLabel("☁️")
        icon_label.setStyleSheet("font-size: 18px;")
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
        """Kreira stranicu Postavke (dummy za sada)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("Postavke")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)
        
        # Backup sekcija
        backup_card = QFrame()
        backup_card.setProperty("card", True)
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(18, 18, 18, 18)
        
        backup_title = QLabel("Backup baze podataka")
        backup_title.setProperty("sectionTitle", True)
        backup_layout.addWidget(backup_title)
        
        backup_desc = QLabel("Kreiraj sigurnosnu kopiju baze podataka.")
        backup_desc.setStyleSheet("color: #6b7280;")
        backup_layout.addWidget(backup_desc)
        
        backup_btn = QPushButton("💾 Kreiraj backup sada")
        backup_btn.setProperty("primary", True)
        backup_btn.setFixedWidth(200)
        backup_btn.clicked.connect(self._do_backup)
        backup_layout.addWidget(backup_btn)
        
        layout.addWidget(backup_card)

        # Historijski uvoz
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

        return page

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
        self.page_title.setText(self.page_names[index])
        subtitles = {
            "Kontrolna ploča": "Pregled ključnih pokazatelja poslovanja.",
            "Kupci": "Baza kupaca, pretraga i unos u SQLite bazu.",
            "Narudžbe": "Kupovina sa snapshot cijenom i automatskim ratama.",
            "Kampanje": "Mjesečni katalog i import cijena iz Excel fajla.",
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
        self._update_nav_button_style(button, is_active=True)
        
        # Resetuj ostala dugmad
        for btn in self.nav_buttons:
            if btn is not button:
                self._update_nav_button_style(btn, is_active=False)

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

    def _update_last_refresh(self) -> None:
        """Ažurira vrijeme zadnjeg osvježenja u statusnoj traci."""
        if hasattr(self, "status_refresh_label"):
            now = datetime.now().strftime("%H:%M:%S")
            self.status_refresh_label.setText(f"Posljednje osvježenje: {now}")
