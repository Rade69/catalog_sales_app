from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.models import PriceList, PriceListItem
from app.gui.table_helpers import style_table, create_numeric_item
from app.services.price_list_service import PriceListService
from app.gui.icons import create_icon_label, get_pixmap


class _ImportWorker(QThread):
    """Pozadinski thread za import cjenovnika."""

    finished = Signal(int, int)  # (imported, skipped)
    error = Signal(str)

    def __init__(self, name: str, excel_path: str) -> None:
        super().__init__()
        self._name = name
        self._excel_path = excel_path

    def run(self) -> None:
        try:
            imported, skipped = PriceListService.import_from_excel(
                name=self._name,
                excel_path=self._excel_path,
            )
            self.finished.emit(imported, skipped)
        except Exception as exc:
            self.error.emit(str(exc))


class PriceListPage(QWidget):
    """Stranica za uvoz i pregled cjenovnika."""

    def __init__(self) -> None:
        super().__init__()

        self._price_lists: list[PriceList] = []
        self._all_items: list[PriceListItem] = []
        self._excel_path: Optional[str] = None
        self._import_worker: Optional[_ImportWorker] = None

        self._init_ui()
        self._load_price_lists()

    # ------------------------------------------------------------------
    # UI izgradnja
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_selector_bar())
        root.addWidget(self._build_status_banner())
        root.addWidget(self._build_items_panel(), 1)

    def _build_top_bar(self) -> QFrame:
        """Import traka: naziv + fajl + dugme."""
        bar = QFrame()
        bar.setProperty("card", True)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        lbl_naziv = QLabel("Naziv:")
        lbl_naziv.setFixedWidth(46)
        layout.addWidget(lbl_naziv)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("npr. Cjenovnik Mart 2026")
        self.name_edit.setFixedWidth(200)
        layout.addWidget(self.name_edit)

        lbl_fajl = QLabel("Fajl:")
        lbl_fajl.setFixedWidth(30)
        layout.addWidget(lbl_fajl)

        self.excel_label = QLabel("Nije odabran fajl")
        self.excel_label.setStyleSheet("color: #9ca3af; font-style: italic;")
        layout.addWidget(self.excel_label, 1)

        browse_btn = QPushButton("Odaberi...")
        browse_btn.setProperty("secondary", True)
        browse_btn.setFixedWidth(110)
        browse_btn.clicked.connect(self._browse_excel)
        layout.addWidget(browse_btn)

        self.import_btn = QPushButton("Uvezi cjenovnik")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background: #047857; }
            QPushButton:pressed { background: #065f46; }
            QPushButton:disabled { background: #d1d5db; color: #9ca3af; }
        """)
        self.import_btn.clicked.connect(self._run_import)
        import_pixmap = get_pixmap("import", "#ffffff", 18)
        self.import_btn.setIcon(import_pixmap)
        layout.addWidget(self.import_btn)

        return bar

    def _build_selector_bar(self) -> QFrame:
        """Traka za odabir cjenovnika + brisanje."""
        bar = QFrame()
        bar.setProperty("card", True)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        lbl = QLabel("Cjenovnik:")
        lbl.setFixedWidth(80)
        layout.addWidget(lbl)

        self.price_list_combo = QComboBox()
        self.price_list_combo.setMinimumWidth(280)
        self.price_list_combo.setPlaceholderText("— Odaberi cjenovnik —")
        self.price_list_combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.price_list_combo, 1)

        self.items_count_label = QLabel("")
        self.items_count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(self.items_count_label)

        layout.addStretch(1)

        # Pretraga
        self.items_search = QLineEdit()
        self.items_search.setPlaceholderText("Pretraži po nazivu, šifri ili firmi...")
        self.items_search.setFixedWidth(240)
        self.items_search.textChanged.connect(self._filter_items)
        layout.addWidget(self.items_search)

        # Brisanje
        self.delete_btn = QPushButton("Obriši")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #b91c1c; }
            QPushButton:disabled { background: #d1d5db; color: #9ca3af; }
        """)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._confirm_and_delete)
        layout.addWidget(self.delete_btn)

        return bar

    def _build_status_banner(self) -> QLabel:
        self.status_banner = QLabel("")
        self.status_banner.setWordWrap(True)
        self.status_banner.setVisible(False)
        self.status_banner.setStyleSheet("""
            QLabel {
                background: #dcfce7;
                color: #166534;
                border: 1px solid #bbf7d0;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }
        """)
        return self.status_banner

    def _build_items_panel(self) -> QWidget:
        """Puna tabela stavki cjenovnika."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)
        # Redoslijed: Rb. | Firma | Naziv artikla | Šifra | Cijena (KM) | Bod | Status
        self.items_table.setHorizontalHeaderLabels([
            "Rb.", "Firma", "Naziv artikla", "Šifra", "Cijena (KM)", "Bod", "Status"
        ])

        header = self.items_table.horizontalHeader()
        # Rb.
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.items_table.setColumnWidth(0, 44)
        # Firma: interaktivna — korisnik može resizati
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.items_table.setColumnWidth(1, 150)
        # Naziv: Stretch — uzima ostatak prostora
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setMinimumSectionSize(120)
        # Šifra
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.items_table.setColumnWidth(3, 90)
        # Cijena
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.items_table.setColumnWidth(4, 100)
        # Bod — odmah pored Cijene
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.items_table.setColumnWidth(5, 60)
        # Status
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.items_table.setColumnWidth(6, 80)

        style_table(self.items_table)
        layout.addWidget(self.items_table)
        return container

    # ------------------------------------------------------------------
    # Import logika
    # ------------------------------------------------------------------

    def _browse_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Excel fajl",
            "",
            "Excel fajlovi (*.xlsx *.xls);;Svi fajlovi (*)"
        )
        if not file_path:
            return
        self._excel_path = file_path
        filename = Path(file_path).name
        self.excel_label.setText(filename)
        self.excel_label.setStyleSheet("color: #059669; font-weight: bold;")
        if not self.name_edit.text().strip():
            self.name_edit.setText(Path(file_path).stem)

    def _run_import(self) -> None:
        name = self.name_edit.text().strip()
        if not name and self._excel_path:
            name = Path(self._excel_path).stem
            self.name_edit.setText(name)
        if not name:
            self._show_error("Naziv cjenovnika je obavezan.")
            self.name_edit.setFocus()
            return
        if not self._excel_path:
            self._show_error("Excel fajl nije odabran.")
            return

        self.import_btn.setEnabled(False)
        self.import_btn.setText("Import u toku...")
        self.status_banner.setVisible(False)

        self._import_worker = _ImportWorker(name, self._excel_path)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _on_import_finished(self, imported: int, skipped: int) -> None:
        self._reset_import_btn()
        supplier_note = f" (+ {skipped} redova dobavljača/zaglavlja)" if skipped else ""
        self._show_success(
            f"Import uspješan! Uvezeno <b>{imported}</b> stavki{supplier_note}."
        )
        self.name_edit.clear()
        self._excel_path = None
        self.excel_label.setText("Nije odabran fajl")
        self.excel_label.setStyleSheet("color: #9ca3af; font-style: italic;")
        self._load_price_lists()

    def _on_import_error(self, message: str) -> None:
        self._reset_import_btn()
        self._show_error(message)

    def _reset_import_btn(self) -> None:
        self.import_btn.setEnabled(True)
        self.import_btn.setText("Uvezi cjenovnik")

    def _show_success(self, text: str) -> None:
        self.status_banner.setText(text)
        self.status_banner.setStyleSheet("""
            QLabel {
                background: #dcfce7;
                color: #166534;
                border: 1px solid #bbf7d0;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }
        """)
        self.status_banner.setVisible(True)

    def _show_error(self, text: str) -> None:
        self.status_banner.setText(f"<b>Greška:</b> {text}")
        self.status_banner.setStyleSheet("""
            QLabel {
                background: #fee2e2;
                color: #991b1b;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }
        """)
        self.status_banner.setVisible(True)

    # ------------------------------------------------------------------
    # Lista cjenovnika (combobox)
    # ------------------------------------------------------------------

    def _load_price_lists(self) -> None:
        self._price_lists = PriceListService.list_all()

        self.price_list_combo.blockSignals(True)
        self.price_list_combo.clear()
        for pl in self._price_lists:
            label = f"{pl.name}  ({pl.source_filename or '—'})"
            self.price_list_combo.addItem(label, userData=pl.id)
        self.price_list_combo.blockSignals(False)

        if self._price_lists:
            self.price_list_combo.setCurrentIndex(0)
            self._on_combo_changed(0)
        else:
            self.items_table.setRowCount(0)
            self.items_count_label.setText("")
            self.delete_btn.setEnabled(False)

    def _on_combo_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._price_lists):
            self.delete_btn.setEnabled(False)
            return
        pl = self._price_lists[index]
        self.delete_btn.setEnabled(True)
        items = PriceListService.get_items(pl.id)
        self._all_items = items
        self._populate_items(items)
        self.items_search.clear()

    # ------------------------------------------------------------------
    # Brisanje
    # ------------------------------------------------------------------

    def _confirm_and_delete(self) -> None:
        index = self.price_list_combo.currentIndex()
        if index < 0 or index >= len(self._price_lists):
            return
        pl = self._price_lists[index]
        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            f"Da li sigurno želiš obrisati cjenovnik '{pl.name}' i sve njegove stavke?\n"
            "Ova radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            PriceListService.delete(pl.id)
            self._load_price_lists()
        except Exception as e:
            self._show_error(str(e))

    # ------------------------------------------------------------------
    # Stavke cjenovnika
    # ------------------------------------------------------------------

    def _populate_items(self, items: list[PriceListItem]) -> None:
        self.items_table.setRowCount(0)
        self.items_table.setRowCount(len(items))

        for i, item in enumerate(items):
            # Rb. — sekvencijalni broj (1, 2, 3...) — ne iz Excela
            rb = QTableWidgetItem(str(i + 1))
            rb.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 0, rb)

            # Firma
            supplier_item = QTableWidgetItem(item.supplier or "")
            supplier_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.items_table.setItem(i, 1, supplier_item)

            # Naziv artikla
            self.items_table.setItem(i, 2, QTableWidgetItem(item.name))

            # Šifra
            code_item = QTableWidgetItem(item.supplier_code or "")
            code_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 3, code_item)

            # Cijena (KM)
            self.items_table.setItem(i, 4, create_numeric_item(item.regular_price))

            # Bod — odmah pored Cijene
            self.items_table.setItem(i, 5, create_numeric_item(item.points))

            # Status — vrijednost iz Excel kolone STATUS (npr. "aktuelno")
            status_text = item.status or ""
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 6, status_item)

        self.items_count_label.setText(f"{len(items)} stavki")

    def _filter_items(self, text: str) -> None:
        """Filtrira redove tabele bez DB upita."""
        query = text.lower().strip()
        visible = 0
        for row in range(self.items_table.rowCount()):
            name_item = self.items_table.item(row, 2)
            code_item = self.items_table.item(row, 3)
            supplier_item = self.items_table.item(row, 1)
            match = (
                not query
                or (name_item and query in name_item.text().lower())
                or (code_item and query in code_item.text().lower())
                or (supplier_item and query in supplier_item.text().lower())
            )
            self.items_table.setRowHidden(row, not match)
            if match:
                visible += 1
        self.items_count_label.setText(f"{visible} stavki")

    # ------------------------------------------------------------------
    # Aktivacija stranice
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        self._load_price_lists()
