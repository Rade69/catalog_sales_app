from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.models import PriceList, PriceListItem
from app.services.price_list_service import PriceListService


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

        self._selected_price_list_id: Optional[int] = None
        self._selected_price_list_name: Optional[str] = None
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
        root.setSpacing(12)

        root.addWidget(self._build_import_bar())
        root.addWidget(self._build_status_banner())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_lists_panel())
        splitter.addWidget(self._build_items_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter, 1)

    def _build_import_bar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("card", True)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Naziv:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("npr. Cjenovnik Mart 2026")
        self.name_edit.setMaximumWidth(220)
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Excel fajl:"))
        self.excel_label = QLabel("Nije odabran fajl")
        self.excel_label.setStyleSheet("color: #9ca3af; font-style: italic;")
        self.excel_label.setMinimumWidth(180)
        layout.addWidget(self.excel_label, 1)

        browse_btn = QPushButton("Odaberi fajl...")
        browse_btn.setProperty("secondary", True)
        browse_btn.clicked.connect(self._browse_excel)
        layout.addWidget(browse_btn)

        self.import_btn = QPushButton("Importuj cjenovnik")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover { background: #047857; }
            QPushButton:pressed { background: #065f46; }
            QPushButton:disabled { background: #d1d5db; color: #9ca3af; }
        """)
        self.import_btn.clicked.connect(self._run_import)
        layout.addWidget(self.import_btn)

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
                padding: 10px 14px;
                font-size: 13px;
            }
        """)
        return self.status_banner

    def _build_lists_panel(self) -> QGroupBox:
        group = QGroupBox("Uvezeni cjenovnici")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.lists_table = QTableWidget()
        self.lists_table.setColumnCount(3)
        self.lists_table.setHorizontalHeaderLabels(["ID", "Naziv", "Fajl"])
        lh = self.lists_table.horizontalHeader()
        lh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        lh.setSectionResizeMode(1, QHeaderView.Stretch)
        lh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.lists_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lists_table.setSelectionMode(QTableWidget.SingleSelection)
        self.lists_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lists_table.setAlternatingRowColors(True)
        self.lists_table.verticalHeader().setVisible(False)
        self.lists_table.itemSelectionChanged.connect(self._on_list_selected)

        # Kontekstualni meni za brisanje (desni klik)
        self.lists_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lists_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.lists_table)
        return group

    def _build_items_panel(self) -> QGroupBox:
        group = QGroupBox("Stavke cjenovnika")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Header red: naziv + broj stavki
        header_row = QHBoxLayout()
        self.items_title = QLabel("Odaberi cjenovnik iz liste")
        self.items_title.setStyleSheet("color: #6b7280; font-style: italic;")
        header_row.addWidget(self.items_title)
        header_row.addStretch(1)
        self.items_count_label = QLabel("")
        self.items_count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        header_row.addWidget(self.items_count_label)
        layout.addLayout(header_row)

        # Pretraga
        self.items_search = QLineEdit()
        self.items_search.setPlaceholderText("Pretraži po nazivu ili šifri...")
        self.items_search.textChanged.connect(self._filter_items)
        self.items_search.setVisible(False)
        layout.addWidget(self.items_search)

        # Tabela stavki
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(6)
        self.items_table.setHorizontalHeaderLabels([
            "Rb.", "Naziv", "Šifra", "Cijena (KM)", "Akcija (KM)", "Bod"
        ])

        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setMaximumSectionSize(420)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.items_table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.items_table.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.items_table.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.items_table.setColumnWidth(5, 70)

        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.verticalHeader().setVisible(False)

        layout.addWidget(self.items_table, 1)
        return group

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
        # Auto-popuni naziv ako je prazan
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
        skip_text = f", preskočeno {skipped}" if skipped else ""
        self._show_success(
            f"Import uspješan! Uvezeno <b>{imported}</b> stavki{skip_text}."
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
        self.import_btn.setText("Importuj cjenovnik")

    def _show_success(self, text: str) -> None:
        self.status_banner.setText(text)
        self.status_banner.setStyleSheet("""
            QLabel {
                background: #dcfce7;
                color: #166534;
                border: 1px solid #bbf7d0;
                border-radius: 8px;
                padding: 10px 14px;
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
                padding: 10px 14px;
                font-size: 13px;
            }
        """)
        self.status_banner.setVisible(True)

    # ------------------------------------------------------------------
    # Lista cjenovnika
    # ------------------------------------------------------------------

    def _load_price_lists(self) -> None:
        price_lists = PriceListService.list_all()
        self.lists_table.setRowCount(0)
        self.lists_table.setRowCount(len(price_lists))
        for row, pl in enumerate(price_lists):
            id_item = QTableWidgetItem(str(pl.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.lists_table.setItem(row, 0, id_item)

            self.lists_table.setItem(row, 1, QTableWidgetItem(pl.name))

            # Skraćeni naziv fajla s tooltipom
            filename = pl.source_filename or ""
            short = filename if len(filename) <= 30 else filename[:27] + "..."
            fajl_item = QTableWidgetItem(short)
            fajl_item.setToolTip(filename)
            self.lists_table.setItem(row, 2, fajl_item)

        self.lists_table.resizeColumnsToContents()

    def _on_list_selected(self) -> None:
        row = self.lists_table.currentRow()
        if row < 0:
            self._selected_price_list_id = None
            self._selected_price_list_name = None
            return

        id_item = self.lists_table.item(row, 0)
        name_item = self.lists_table.item(row, 1)
        if not id_item:
            return

        try:
            self._selected_price_list_id = int(id_item.text())
        except ValueError:
            return

        self._selected_price_list_name = name_item.text() if name_item else ""
        self._load_items(self._selected_price_list_id, self._selected_price_list_name)

    # ------------------------------------------------------------------
    # Kontekstualni meni (desni klik → brisanje)
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        if self._selected_price_list_id is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("Obriši odabrani cjenovnik")
        delete_action.setToolTip("Trajno briše cjenovnik i sve stavke")
        action = menu.exec(self.lists_table.viewport().mapToGlobal(pos))
        if action == delete_action:
            self._confirm_and_delete()

    def _confirm_and_delete(self) -> None:
        name = self._selected_price_list_name or f"ID={self._selected_price_list_id}"
        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            f"Da li sigurno želiš obrisati cjenovnik '{name}' i sve njegove stavke?\n"
            "Ova radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            PriceListService.delete(self._selected_price_list_id)
            self._selected_price_list_id = None
            self._selected_price_list_name = None
            self._load_price_lists()
            self._clear_items_panel()
        except Exception as e:
            self._show_error(str(e))

    # ------------------------------------------------------------------
    # Stavke cjenovnika
    # ------------------------------------------------------------------

    def _load_items(self, price_list_id: int, name: str) -> None:
        items = PriceListService.get_items(price_list_id)
        self._populate_items(items)
        self.items_title.setText(f"Stavke — {name}")
        self.items_title.setStyleSheet("")
        self.items_count_label.setText(f"{len(items)} stavki")
        self.items_search.setVisible(True)
        self.items_search.clear()

    def _populate_items(self, items: list[PriceListItem]) -> None:
        self.items_table.setRowCount(0)
        self.items_table.setRowCount(len(items))

        for i, item in enumerate(items):
            # Rb.
            rb = QTableWidgetItem(str(item.row_number) if item.row_number else str(i + 1))
            rb.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(i, 0, rb)

            # Naziv
            self.items_table.setItem(i, 1, QTableWidgetItem(item.name))

            # Šifra
            self.items_table.setItem(i, 2, QTableWidgetItem(item.supplier_code or ""))

            # Cijena
            price_item = QTableWidgetItem(
                f"{item.regular_price:.2f}" if item.regular_price is not None else "—"
            )
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(i, 3, price_item)

            # Akcija — zelena boja ako postoji
            disc_item = QTableWidgetItem(
                f"{item.discount_price:.2f}" if item.discount_price is not None else ""
            )
            disc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if item.discount_price is not None:
                disc_item.setForeground(QColor("#059669"))
            self.items_table.setItem(i, 4, disc_item)

            # Bod
            bod_item = QTableWidgetItem(str(item.points) if item.points is not None else "")
            bod_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(i, 5, bod_item)

    def _filter_items(self, text: str) -> None:
        """Filtrira redove tabele bez DB upita — samo sakriva/prikazuje."""
        query = text.lower().strip()
        for row in range(self.items_table.rowCount()):
            name_item = self.items_table.item(row, 1)
            code_item = self.items_table.item(row, 2)
            visible = (
                not query
                or (name_item and query in name_item.text().lower())
                or (code_item and query in code_item.text().lower())
            )
            self.items_table.setRowHidden(row, not visible)

        visible_count = sum(
            1 for r in range(self.items_table.rowCount())
            if not self.items_table.isRowHidden(r)
        )
        self.items_count_label.setText(f"{visible_count} stavki")

    def _clear_items_panel(self) -> None:
        self.items_table.setRowCount(0)
        self.items_title.setText("Odaberi cjenovnik iz liste")
        self.items_title.setStyleSheet("color: #6b7280; font-style: italic;")
        self.items_count_label.setText("")
        self.items_search.setVisible(False)
        self.items_search.clear()

    # ------------------------------------------------------------------
    # Aktivacija stranice
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        self._load_price_lists()
