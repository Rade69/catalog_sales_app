from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
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
        self.selected_excel_path: Optional[Path] = None

        self._init_ui()
        self._connect_signals()
        self._load_campaigns()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- Import sekcija ---
        import_card = self._create_import_card()
        root.addWidget(import_card)

        # --- Tabela kampanja ---
        table_card = self._create_table_card()
        root.addWidget(table_card)

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

    def _connect_signals(self) -> None:
        """Povezuje signale sa slotovima."""
        self.select_file_btn.clicked.connect(self.select_excel_file)
        self.import_btn.clicked.connect(self.import_campaign)
        self.refresh_btn.clicked.connect(self._load_campaigns)

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
        """Pokreće import kampanje."""
        # Validacija
        campaign_name = self.campaign_name_input.text().strip()
        if not campaign_name:
            QMessageBox.warning(self, "Greška", "Naziv kampanje je obavezan.")
            self.campaign_name_input.setFocus()
            return

        if not self.selected_excel_path:
            QMessageBox.warning(self, "Greška", "Excel fajl nije odabran.")
            return

        start_date = self.start_date_edit.date().toPython()
        end_date = self.end_date_edit.date().toPython()

        if start_date > end_date:
            QMessageBox.warning(
                self, "Greška",
                "Datum početka mora biti prije datuma završetka."
            )
            return

        # Pokreni import
        try:
            result = self.campaign_service.import_campaign_from_excel(
                excel_path=self.selected_excel_path,
                campaign_name=campaign_name,
                start_date=start_date,
                end_date=end_date
            )

            # Prikaži rezultat
            self._show_import_summary(result)

            # Očisti formu
            self.campaign_name_input.clear()
            self.selected_excel_path = None
            self.file_path_label.setText("Nije odabran fajl")
            self.file_path_label.setStyleSheet("color: #6b7280; font-style: italic;")

            # Osvježi tabelu
            self._load_campaigns()

        except FileNotFoundError:
            QMessageBox.critical(
                self, "Greška",
                f"Excel fajl nije pronađen:\n{self.selected_excel_path}"
            )
        except ValueError as e:
            QMessageBox.warning(self, "Greška", str(e))
        except Exception as e:
            QMessageBox.critical(
                self, "Greška",
                f"Neočekivana greška pri importu:\n{str(e)}"
            )

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

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_campaigns()
