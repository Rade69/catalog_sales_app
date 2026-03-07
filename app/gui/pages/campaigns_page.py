from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.campaign_service import CampaignService


class _ImportWorker(QThread):
    """Pozadinski thread za import kampanje iz Excel fajla."""

    finished = Signal(object)  # emits ImportResult
    error = Signal(str)        # emits error message

    def __init__(
        self,
        campaign_service: CampaignService,
        excel_path: Path,
        campaign_name: str,
        start_date: date,
        end_date: date,
    ) -> None:
        super().__init__()
        self._service = campaign_service
        self._excel_path = excel_path
        self._campaign_name = campaign_name
        self._start_date = start_date
        self._end_date = end_date

    def run(self) -> None:
        try:
            result = self._service.import_campaign_from_excel(
                excel_path=self._excel_path,
                campaign_name=self._campaign_name,
                start_date=self._start_date,
                end_date=self._end_date,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class CampaignsPage(QWidget):
    """Stranica za upravljanje kampanjama i import iz Excel-a."""

    def __init__(self) -> None:
        super().__init__()

        self.campaign_service = CampaignService()
        self.selected_excel_path: Optional[Path] = None
        self._import_worker: Optional[_ImportWorker] = None

        self._init_ui()
        self._connect_signals()
        self._load_campaigns()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- Import sekcija (gore) ---
        import_card = self._create_import_card()
        root.addWidget(import_card)

        # --- Horizontalni splitter: kampanje (lijevo) | proizvodi (desno) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        table_card = self._create_table_card()
        splitter.addWidget(table_card)

        products_card = self._create_products_card()
        splitter.addWidget(products_card)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter, 1)

    def _create_import_card(self) -> QFrame:
        """Kreira karticu sa formom za import kampanje."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Naslov
        title = QLabel("Import kampanje iz Excel-a")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # Grid layout za formu
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        # Naziv kampanje
        grid.addWidget(QLabel("Naziv kampanje:"), 0, 0)
        self.campaign_name_input = QLineEdit()
        self.campaign_name_input.setPlaceholderText("npr. Mart 2026")
        grid.addWidget(self.campaign_name_input, 0, 1)

        # Datum početka
        grid.addWidget(QLabel("Datum početka:"), 1, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(date.today())
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy.")
        grid.addWidget(self.start_date_edit, 1, 1)

        # Datum završetka
        grid.addWidget(QLabel("Datum završetka:"), 2, 0)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(date.today().replace(day=28) if date.today().day > 28 else date.today())
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy.")
        grid.addWidget(self.end_date_edit, 2, 1)

        # Excel fajl
        grid.addWidget(QLabel("Excel fajl:"), 3, 0)
        file_row = QHBoxLayout()
        self.file_path_label = QLabel("Nije odabran fajl")
        self.file_path_label.setStyleSheet("color: #6b7280; font-style: italic;")
        file_row.addWidget(self.file_path_label, 1)
        
        self.select_file_btn = QPushButton("Odaberi fajl...")
        self.select_file_btn.setProperty("secondary", True)
        file_row.addWidget(self.select_file_btn)
        
        grid.addLayout(file_row, 3, 1)

        layout.addLayout(grid)

        # Dugme za import
        button_row = QHBoxLayout()
        self.import_btn = QPushButton("Importuj kampanju")
        self.import_btn.setProperty("primary", True)
        self.import_btn.setMinimumHeight(44)
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
        """)
        button_row.addWidget(self.import_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        # Rezime importa (skriveno dok se ne desi import)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("""
            QLabel {
                background-color: #f0fdf4;
                color: #059669;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        self.summary_label.hide()
        layout.addWidget(self.summary_label)

        return card

    def _create_table_card(self) -> QFrame:
        """Kreira karticu sa tabelom kampanja."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        header_row = QHBoxLayout()
        table_title = QLabel("Postojeće kampanje")
        table_title.setProperty("sectionTitle", True)
        header_row.addWidget(table_title)
        header_row.addStretch(1)

        self.refresh_btn = QPushButton("Osvježi")
        self.refresh_btn.setProperty("secondary", True)
        header_row.addWidget(self.refresh_btn)

        layout.addLayout(header_row)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Naziv", "Datum početka", "Datum završetka", "Datum kreiranja"
        ])

        # Konfiguracija tabele
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # type: ignore[arg-type]  # Naziv
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Start
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # End
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Created

        self.table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[arg-type]
        self.table.setSelectionMode(QTableWidget.SingleSelection)  # type: ignore[arg-type]
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[arg-type]
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        return card

    def _create_products_card(self) -> QFrame:
        """Kreira karticu sa tabelom proizvoda za odabranu kampanju."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        header_row = QHBoxLayout()
        self.products_title = QLabel("Proizvodi u kampanji")
        self.products_title.setProperty("sectionTitle", True)
        header_row.addWidget(self.products_title)
        header_row.addStretch(1)

        self.products_count_label = QLabel("")
        self.products_count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        header_row.addWidget(self.products_count_label)

        layout.addLayout(header_row)

        # Hint label
        self.products_hint = QLabel("← Odaberi kampanju iz liste da vidiš proizvode")
        self.products_hint.setStyleSheet("color: #9ca3af; font-style: italic; padding: 8px 0;")
        layout.addWidget(self.products_hint)

        # Pretraga
        self.products_search = QLineEdit()
        self.products_search.setPlaceholderText("🔍 Pretraži po nazivu ili brendu...")
        self.products_search.textChanged.connect(self._filter_products_table)
        self.products_search.hide()
        layout.addWidget(self.products_search)

        # Tabela proizvoda
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(6)
        self.products_table.setHorizontalHeaderLabels([
            "Naziv proizvoda", "Brend", "Model", "Cijena (KM)", "Akcija (KM)", "Bod"
        ])
        ph = self.products_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.Stretch)  # type: ignore[arg-type]
        ph.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # type: ignore[arg-type]
        ph.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # type: ignore[arg-type]
        ph.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # type: ignore[arg-type]
        ph.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # type: ignore[arg-type]
        ph.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # type: ignore[arg-type]
        self.products_table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[arg-type]
        self.products_table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[arg-type]
        self.products_table.setAlternatingRowColors(True)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.hide()

        layout.addWidget(self.products_table, 1)

        # Čuvamo sve učitane redove za filtering
        self._all_product_rows: list = []

        return card

    def _connect_signals(self) -> None:
        """Povezuje signale sa slotovima."""
        self.select_file_btn.clicked.connect(self.select_excel_file)
        self.import_btn.clicked.connect(self.import_campaign)
        self.refresh_btn.clicked.connect(self._load_campaigns)
        self.table.itemSelectionChanged.connect(self._on_campaign_selected)

    def select_excel_file(self) -> None:
        """Otvara dijalog za izbor Excel fajla."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Excel fajl",
            "",
            "Excel fajlovi (*.xlsx *.xls);;Svi fajlovi (*)"
        )

        if file_path:
            self.selected_excel_path = Path(file_path)
            self.file_path_label.setText(self.selected_excel_path.name)
            self.file_path_label.setStyleSheet("color: #059669; font-weight: bold;")

    def import_campaign(self) -> None:
        """Pokreće import kampanje u pozadinskom threadu."""
        # Validacija
        campaign_name = self.campaign_name_input.text().strip()
        if not campaign_name:
            QMessageBox.warning(self, "Greška", "Naziv kampanje je obavezan.")
            self.campaign_name_input.setFocus()
            return

        if not self.selected_excel_path:
            QMessageBox.warning(self, "Greška", "Excel fajl nije odabran.")
            return

        start_date: date = self.start_date_edit.date().toPython()  # type: ignore[assignment]
        end_date: date = self.end_date_edit.date().toPython()  # type: ignore[assignment]

        if start_date > end_date:
            QMessageBox.warning(
                self, "Greška",
                "Datum početka mora biti prije datuma završetka."
            )
            return

        # Onemogući dugme i pokaži da je import u toku
        self.import_btn.setEnabled(False)
        self.import_btn.setText("Import u toku...")
        self.summary_label.hide()

        # Pokreni import u pozadinskom threadu
        self._import_worker = _ImportWorker(
            campaign_service=self.campaign_service,
            excel_path=self.selected_excel_path,
            campaign_name=campaign_name,
            start_date=start_date,
            end_date=end_date,
        )
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _on_import_finished(self, result: object) -> None:
        """Poziva se kad import uspješno završi."""
        self._reset_import_button()

        self._show_import_summary(result)

        # Očisti formu
        self.campaign_name_input.clear()
        self.selected_excel_path = None
        self.file_path_label.setText("Nije odabran fajl")
        self.file_path_label.setStyleSheet("color: #6b7280; font-style: italic;")

        self._load_campaigns()

    def _on_import_error(self, message: str) -> None:
        """Poziva se kad import završi greškom."""
        self._reset_import_button()

        if "već postoji" in message:
            QMessageBox.warning(self, "Greška", message)
        elif "nije pronađen" in message.lower():
            QMessageBox.critical(self, "Greška", f"Excel fajl nije pronađen:\n{message}")
        else:
            QMessageBox.critical(self, "Greška", f"Neočekivana greška pri importu:\n{message}")

    def _reset_import_button(self) -> None:
        """Vraća dugme za import u početno stanje."""
        self.import_btn.setEnabled(True)
        self.import_btn.setText("Importuj kampanju")

    def _show_import_summary(self, result) -> None:
        """Prikazuje rezime importa."""
        summary_text = f"""
        <b>Import uspješan!</b><br/>
        <table style="margin-top: 8px;">
            <tr><td>Ukupno redova:</td><td><b>{result.total_rows}</b></td></tr>
            <tr><td>Novih proizvoda:</td><td><b>{result.new_products}</b></td></tr>
            <tr><td>Matchovanih proizvoda:</td><td><b>{result.matched_products}</b></td></tr>
            <tr><td>Preskočenih redova:</td><td><b>{result.skipped_rows}</b></td></tr>
        </table>
        """

        if result.skipped_rows > 0:
            summary_text += f"""
            <p style="color: #d97706; margin-top: 8px;">
                ⚠ {result.skipped_rows} redova je preskočeno zbog grešaka.
            </p>
            """

        self.summary_label.setText(summary_text)
        self.summary_label.show()

    def _load_campaigns(self) -> None:
        """Učitava kampanje u tabelu."""
        campaigns = self.campaign_service.list_campaigns()

        self.table.setRowCount(0)
        self.table.setRowCount(len(campaigns))

        for row, campaign in enumerate(campaigns):
            # ID
            id_item = QTableWidgetItem(str(campaign.id))
            id_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 0, id_item)

            # Naziv
            self.table.setItem(row, 1, QTableWidgetItem(campaign.name))

            # Datum početka
            start_item = QTableWidgetItem(campaign.start_date.strftime("%d.%m.%Y."))
            start_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 2, start_item)

            # Datum završetka
            end_item = QTableWidgetItem(campaign.end_date.strftime("%d.%m.%Y."))
            end_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 3, end_item)

            # Datum kreiranja
            created_item = QTableWidgetItem(campaign.created_at.strftime("%d.%m.%Y. %H:%M"))
            created_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 4, created_item)

        self.table.resizeColumnsToContents()

    def _on_campaign_selected(self) -> None:
        """Poziva se kad se odabere red u tabeli kampanja."""
        row = self.table.currentRow()
        if row < 0:
            return
        id_item = self.table.item(row, 0)
        if id_item is None:
            return
        try:
            campaign_id = int(id_item.text())
        except ValueError:
            return
        name_item = self.table.item(row, 1)
        campaign_name = name_item.text() if name_item else f"Kampanja #{campaign_id}"
        self._load_campaign_products(campaign_id, campaign_name)

    def _load_campaign_products(self, campaign_id: int, campaign_name: str) -> None:
        """Učitava proizvode za odabranu kampanju u desni panel."""
        prices = self.campaign_service.list_campaign_products(campaign_id)

        self._all_product_rows = prices
        self.products_hint.hide()
        self.products_search.show()
        self.products_table.show()
        self.products_title.setText(f"Proizvodi — {campaign_name}")
        self.products_count_label.setText(f"{len(prices)} proizvoda")
        self.products_search.clear()
        self._populate_products_table(prices)

    def _populate_products_table(self, prices: list) -> None:
        """Puni tabelu proizvoda sa listom CampaignPrice objekata."""
        self.products_table.setRowCount(0)
        self.products_table.setRowCount(len(prices))

        for row, cp in enumerate(prices):
            product = cp.product

            # Naziv
            self.products_table.setItem(row, 0, QTableWidgetItem(
                product.name if product else "—"
            ))

            # Brend
            self.products_table.setItem(row, 1, QTableWidgetItem(
                product.brand or "" if product else ""
            ))

            # Model
            self.products_table.setItem(row, 2, QTableWidgetItem(
                product.model or "" if product else ""
            ))

            # Cijena
            price_item = QTableWidgetItem(f"{cp.regular_price:.2f}")
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[arg-type]
            self.products_table.setItem(row, 3, price_item)

            # Akcijska cijena
            if cp.discount_price is not None:
                disc_item = QTableWidgetItem(f"{cp.discount_price:.2f}")
                disc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[arg-type]
                self.products_table.setItem(row, 4, disc_item)
            else:
                self.products_table.setItem(row, 4, QTableWidgetItem(""))

            # Bod
            if cp.points is not None:
                bod_item = QTableWidgetItem(str(cp.points))
                bod_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[arg-type]
                self.products_table.setItem(row, 5, bod_item)
            else:
                self.products_table.setItem(row, 5, QTableWidgetItem(""))

        self.products_table.resizeColumnsToContents()

    def _filter_products_table(self, text: str) -> None:
        """Filtrira tabelu proizvoda prema tekstu pretrage."""
        if not text.strip():
            self._populate_products_table(self._all_product_rows)
            return

        query = text.strip().lower()
        filtered = [
            cp for cp in self._all_product_rows
            if cp.product and (
                query in (cp.product.name or "").lower()
                or query in (cp.product.brand or "").lower()
                or query in (cp.product.model or "").lower()
            )
        ]
        self._populate_products_table(filtered)

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_campaigns()
