from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QFrame,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.campaign_service import CampaignService


class CampaignsPage(QWidget):
    """Stranica za upravljanje kampanjama i import iz Excel-a."""

    def __init__(self) -> None:
        super().__init__()

        self.campaign_service = CampaignService()

        self._init_ui()
        self._connect_signals()
        self._load_campaigns()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- Horizontalni splitter: kampanje (lijevo) | proizvodi (desno) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        table_card = self._create_table_card()
        splitter.addWidget(table_card)

        products_card = self._create_products_card()
        splitter.addWidget(products_card)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter, 1)

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

        self.import_btn = QPushButton("📥  Import iz Excel-a")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.import_btn.clicked.connect(self._open_import_dialog)
        header_row.addWidget(self.import_btn)

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
        self.refresh_btn.clicked.connect(self._load_campaigns)
        self.table.itemSelectionChanged.connect(self._on_campaign_selected)

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

    def _open_import_dialog(self) -> None:
        """Otvara modalni dijalog za import kampanje."""
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QDateEdit,
            QVBoxLayout,
            QFrame,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Import kampanje iz Excel-a")
        dialog.setMinimumWidth(480)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Naziv
        r1 = QHBoxLayout()
        lbl1 = QLabel("Naziv kampanje:")
        lbl1.setFixedWidth(130)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("npr. April 2026")
        r1.addWidget(lbl1)
        r1.addWidget(name_edit, 1)
        layout.addLayout(r1)

        # Datum početka
        r2 = QHBoxLayout()
        lbl2 = QLabel("Datum početka:")
        lbl2.setFixedWidth(130)
        start_date = QDateEdit(QDate.currentDate())
        start_date.setCalendarPopup(True)
        start_date.setDisplayFormat("dd.MM.yyyy.")
        r2.addWidget(lbl2)
        r2.addWidget(start_date, 1)
        layout.addLayout(r2)

        # Datum završetka
        r3 = QHBoxLayout()
        lbl3 = QLabel("Datum završetka:")
        lbl3.setFixedWidth(130)
        end_date = QDateEdit(QDate.currentDate().addDays(30))
        end_date.setCalendarPopup(True)
        end_date.setDisplayFormat("dd.MM.yyyy.")
        r3.addWidget(lbl3)
        r3.addWidget(end_date, 1)
        layout.addLayout(r3)

        # Excel fajl
        r4 = QHBoxLayout()
        lbl4 = QLabel("Excel fajl:")
        lbl4.setFixedWidth(130)
        file_label = QLabel("Nije odabran fajl")
        file_label.setStyleSheet("color: #9ca3af; font-style: italic;")
        selected_path = {"value": None}

        def browse():
            from pathlib import Path
            path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Odaberi Excel fajl",
                "",
                "Excel fajlovi (*.xlsx *.xls);;Svi fajlovi (*)",
            )
            if path:
                selected_path["value"] = Path(path)
                file_label.setText(Path(path).name)
                file_label.setStyleSheet("color: #059669; font-weight: bold;")

        browse_btn = QPushButton("Odaberi fajl...")
        browse_btn.setProperty("secondary", True)
        browse_btn.clicked.connect(browse)
        r4.addWidget(lbl4)
        r4.addWidget(file_label, 1)
        r4.addWidget(browse_btn)
        layout.addLayout(r4)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep)

        # Gumbi
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setText("Importuj kampanju")
        ok_btn.setStyleSheet(
            "background:#059669;color:white;border:none;"
            "border-radius:8px;padding:8px 16px;font-weight:700;"
        )
        buttons.button(QDialogButtonBox.Cancel).setText("Odustani")
        layout.addWidget(buttons)

        def on_accept():
            name = name_edit.text().strip()
            if not name:
                QMessageBox.warning(dialog, "Greška", "Naziv kampanje je obavezan.")
                return
            if not selected_path["value"]:
                QMessageBox.warning(dialog, "Greška", "Odaberi Excel fajl.")
                return
            start = start_date.date().toPython()
            end = end_date.date().toPython()
            if start > end:
                QMessageBox.warning(
                    dialog,
                    "Greška",
                    "Datum početka mora biti prije datuma završetka.",
                )
                return
            dialog.accept()

        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.Accepted:
            return

        # Pokreni import
        try:
            result = self.campaign_service.import_campaign_from_excel(
                excel_path=selected_path["value"],
                campaign_name=name_edit.text().strip(),
                start_date=start_date.date().toPython(),
                end_date=end_date.date().toPython(),
            )
            QMessageBox.information(
                self,
                "Import uspješan",
                f"Uvezeno {result.total_rows} redova.\n"
                f"Novih proizvoda: {result.new_products}\n"
                f"Matchovanih: {result.matched_products}\n"
                f"Preskočeno: {result.skipped_rows}",
            )
            self._load_campaigns()
        except Exception as e:
            QMessageBox.critical(self, "Greška pri importu", str(e))

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_campaigns()
