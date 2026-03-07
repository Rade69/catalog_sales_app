from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

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
        filters_layout.addStretch(1)

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

        root.addWidget(filters_card, 1)
        root.addWidget(table_card, 2)

        self.load_report()

    def on_activate(self) -> None:
        self.load_report()

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
