from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, create_numeric_item, show_empty_state
from app.services.report_service import ReportService


class ReportsPage(QWidget):
    MONTHS = [
        (1, "Januar"), (2, "Februar"), (3, "Mart"), (4, "April"),
        (5, "Maj"), (6, "Juni"), (7, "Juli"), (8, "August"),
        (9, "Septembar"), (10, "Oktobar"), (11, "Novembar"), (12, "Decembar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        today = date.today()

        # Glavni layout sa scrollom
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        scroll_widget = QWidget()
        root = QVBoxLayout(scroll_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # Prvi dio: Mjesečne uplate (postojeći)
        monthly_card = self._build_monthly_card(today)
        root.addWidget(monthly_card)

        # Drugi dio: Izvještaj naplate (novi)
        naplata_card = self._build_naplata_card()
        root.addWidget(naplata_card)

        root.addStretch(1)
        scroll.setWidget(scroll_widget)

        # Postavi scroll u glavni layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(scroll)

        self.load_report()

    def on_activate(self) -> None:
        self.load_report()

    def _build_monthly_card(self, today) -> QFrame:
        """Kreira card za mjesečne uplate (postojeći izvještaj)."""
        filters_card = QFrame()
        filters_card.setProperty("card", True)
        filters_layout = QVBoxLayout(filters_card)
        filters_layout.setContentsMargins(18, 18, 18, 18)
        filters_layout.setSpacing(12)

        filters_title = QLabel("Izvještaji — mjesečne uplate")
        filters_title.setProperty("sectionTitle", True)
        filters_layout.addWidget(filters_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.report_type = QComboBox()
        self.report_type.addItems(["Mjesečni iznos uplaćenih sredstava"])

        self.month_combo = QComboBox()
        for month_number, month_name in self.MONTHS:
            self.month_combo.addItem(month_name, month_number)
        self.month_combo.setCurrentIndex(today.month - 1)

        self.year_combo = QComboBox()
        for year in range(today.year - 3, today.year + 2):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(today.year))

        grid.addWidget(QLabel("Tip izvještaja"), 0, 0)
        grid.addWidget(self.report_type, 0, 1)
        grid.addWidget(QLabel("Mjesec"), 1, 0)
        grid.addWidget(self.month_combo, 1, 1)
        grid.addWidget(QLabel("Godina"), 2, 0)
        grid.addWidget(self.year_combo, 2, 1)
        filters_layout.addLayout(grid)

        self.total_label = QLabel("Ukupno uplaćeno: 0.00 KM")
        self.total_label.setProperty("sectionTitle", True)
        filters_layout.addWidget(self.total_label)

        self.count_label = QLabel("Broj evidentiranih uplata: 0")
        self.count_label.setStyleSheet("color: #6b7280;")
        filters_layout.addWidget(self.count_label)

        buttons = QHBoxLayout()
        self.preview_btn = QPushButton("Osvježi pregled")
        self.preview_btn.setProperty("primary", True)
        self.preview_btn.clicked.connect(self.load_report)

        self.export_btn = QPushButton("Eksport u Excel")
        self.export_btn.setProperty("secondary", True)
        self.export_btn.clicked.connect(self.export_report)

        buttons.addWidget(self.preview_btn)
        buttons.addWidget(self.export_btn)
        filters_layout.addLayout(buttons)

        table_card = QFrame()
        table_card.setProperty("card", True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(12)

        table_title = QLabel("Pregled uplata za odabrani mjesec")
        table_title.setProperty("sectionTitle", True)
        table_layout.addWidget(table_title)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Datum", "Kupac", "Artikal", "Kampanja", "Rata", "Iznos", "Napomena"
        ])
        style_table(self.table)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.table)

        filters_layout.addWidget(table_card)

        return filters_card

    def _build_naplata_card(self) -> QFrame:
        """Kreira card za izvještaj naplate (novi Excel izvještaj)."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Izvještaj naplate — Excel")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        desc = QLabel(
            "Generira Excel izvještaj u formatu 'Evidencija o uplatama rata'. "
            "Sadrži sve narudžbe kampanje sa plaćenim i preostalim ratama."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6b7280;")
        layout.addWidget(desc)

        # Odabir kampanje
        kampanja_row = QHBoxLayout()
        kampanja_row.addWidget(QLabel("Kampanja:"))
        self.report_campaign_combo = QComboBox()
        self.report_campaign_combo.setMinimumWidth(220)
        kampanja_row.addWidget(self.report_campaign_combo, 1)
        layout.addLayout(kampanja_row)

        # Agent info
        agent_row = QHBoxLayout()
        agent_row.addWidget(QLabel("Saradnički broj:"))
        self.agent_code_edit = QLineEdit()
        self.agent_code_edit.setPlaceholderText("npr. 4-1-11-2-1-3")
        self.agent_code_edit.setMaximumWidth(160)
        agent_row.addWidget(self.agent_code_edit)
        agent_row.addSpacing(16)
        agent_row.addWidget(QLabel("Ime saradnika:"))
        self.agent_name_edit = QLineEdit()
        self.agent_name_edit.setText("KRUNIĆ STOJANOVIĆ SANJA")
        self.agent_name_edit.setMinimumWidth(240)
        agent_row.addWidget(self.agent_name_edit, 1)
        layout.addLayout(agent_row)

        # Dugme
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("📊  Generiraj Excel izvještaj")
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background: #059669; color: white; border: none;
                border-radius: 10px; padding: 10px 20px;
                font-weight: 700; font-size: 13px;
            }
            QPushButton:hover { background: #047857; }
        """)
        self.btn_generate.clicked.connect(self._generate_naplata_report)
        btn_row.addWidget(self.btn_generate)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Status label
        self.report_status_label = QLabel("")
        self.report_status_label.setWordWrap(True)
        self.report_status_label.setVisible(False)
        layout.addWidget(self.report_status_label)

        # Učitaj kampanje u combo
        self._load_campaigns_combo()

        return card

    def _load_campaigns_combo(self) -> None:
        """Učitava kampanje u dropdown za izvještaj naplate."""
        from app.services.campaign_service import CampaignService
        try:
            campaigns = CampaignService.list_campaigns()
            self.report_campaign_combo.clear()
            for c in campaigns:
                self.report_campaign_combo.addItem(c.name, userData=c.id)
        except Exception:
            pass

    def _generate_naplata_report(self) -> None:
        """Generira Excel izvještaj naplate."""
        from app.reports.naplata_report import generate_naplata_excel

        campaign_id = self.report_campaign_combo.currentData()
        if campaign_id is None:
            QMessageBox.warning(self, "Greška", "Odaberi kampanju.")
            return

        campaign_name = self.report_campaign_combo.currentText()
        safe_name = campaign_name.replace(" ", "_").replace("/", "-")
        default_filename = f"Naplata_{safe_name}.xlsx"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Spremi Excel izvještaj",
            str(Path.home() / default_filename),
            "Excel fajlovi (*.xlsx)"
        )
        if not save_path:
            return

        try:
            self.btn_generate.setEnabled(False)
            self.btn_generate.setText("Generisanje...")

            output = generate_naplata_excel(
                campaign_id=campaign_id,
                output_path=Path(save_path),
                agent_code=self.agent_code_edit.text().strip(),
                agent_name=self.agent_name_edit.text().strip()
                           or "KRUNIĆ STOJANOVIĆ SANJA",
            )

            self.report_status_label.setText(
                f"✅ Izvještaj uspješno generisan:\n{output}"
            )
            self.report_status_label.setStyleSheet(
                "background:#dcfce7;color:#166534;border:1px solid #bbf7d0;"
                "border-radius:8px;padding:10px;"
            )
            self.report_status_label.setVisible(True)

        except Exception as e:
            self.report_status_label.setText(f"❌ Greška: {str(e)}")
            self.report_status_label.setStyleSheet(
                "background:#fee2e2;color:#991b1b;border:1px solid #fecaca;"
                "border-radius:8px;padding:10px;"
            )
            self.report_status_label.setVisible(True)
        finally:
            self.btn_generate.setEnabled(True)
            self.btn_generate.setText("📊  Generiraj Excel izvještaj")

    def selected_period(self) -> tuple[int, int]:
        return int(self.year_combo.currentData()), int(self.month_combo.currentData())

    def load_report(self) -> None:
        year, month = self.selected_period()
        report = ReportService.get_monthly_payments_report(year, month)

        self.total_label.setText(f"Ukupno uplaćeno: {report.total_paid:.2f} KM")
        self.count_label.setText(f"Broj evidentiranih uplata: {report.payments_count}")

        df = report.dataframe
        
        if len(df.index) == 0:
            show_empty_state(self.table, "Nema podataka za odabrani period")
            return
        
        self.table.setRowCount(len(df.index))
        for row_index, (_, row) in enumerate(df.iterrows()):
            values = [
                row.get("Datum uplate", ""),
                row.get("Kupac", ""),
                row.get("Artikal", ""),
                row.get("Kampanja", ""),
                row.get("Rata", ""),
                row.get("Napomena", ""),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_index, column_index, item)
            
            # Numerička kolona
            iznos = row.get("Iznos uplate (KM)", 0)
            self.table.setItem(row_index, 5, create_numeric_item(float(iznos) if iznos else 0, " KM"))
            
        self.table.resizeColumnsToContents()

    def export_report(self) -> None:
        year, month = self.selected_period()
        default_filename = f"uplate_{year}_{month:02d}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj izvještaj",
            str(Path.cwd() / default_filename),
            "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            saved_path = ReportService.export_monthly_payments_report(year, month, path)
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))
            return
        QMessageBox.information(self, "Eksport", f"Izvještaj je sačuvan u fajl:\n{saved_path}")
