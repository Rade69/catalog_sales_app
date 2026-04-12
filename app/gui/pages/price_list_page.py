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

from app.gui.base_page import BasePage
from app.database.models import PriceList, PriceListItem
from app.gui.table_helpers import style_table, create_numeric_item
from app.services.price_list_service import PriceListService
from app.gui.icons import create_icon_label, get_pixmap
from app.gui.pagination import PaginationWidget


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


class PriceListPage(BasePage):
    """Stranica za uvoz i pregled cjenovnika."""

    def __init__(self) -> None:
        super().__init__()

        self._price_lists: list[PriceList] = []
        self._current_price_list_id: Optional[int] = None
        self._current_filter_text: str = ""
        self._all_items: list[PriceListItem] = []
        self._excel_path: Optional[str] = None
        self._import_worker: Optional[_ImportWorker] = None

        self._init_ui()

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
        self.excel_label.setProperty("excelFile", True)
        layout.addWidget(self.excel_label, 1)

        browse_btn = QPushButton("Odaberi...")
        browse_btn.setProperty("secondary", True)
        browse_btn.setFixedWidth(110)
        browse_btn.clicked.connect(self._browse_excel)
        layout.addWidget(browse_btn)

        self.import_btn = QPushButton("Uvezi cjenovnik")
        self.import_btn.setProperty("importBtn", True)
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
        self.items_count_label.setProperty("countLabel", True)
        layout.addWidget(self.items_count_label)

        layout.addStretch(1)

        # Pretraga
        self.items_search = QLineEdit()
        self.items_search.setPlaceholderText("Pretraži po nazivu, šifri ili firmi...")
        self.items_search.setFixedWidth(240)
        self.items_search.textChanged.connect(self._filter_items)
        layout.addWidget(self.items_search)

        # Edit
        self.edit_btn = QPushButton("Izmeni")
        self.edit_btn.setProperty("secondary", True)
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._edit_price_list)
        layout.addWidget(self.edit_btn)

        # Dupliciraj
        self.duplicate_btn = QPushButton("Dupliciraj")
        self.duplicate_btn.setProperty("secondary", True)
        self.duplicate_btn.setEnabled(False)
        self.duplicate_btn.clicked.connect(self._duplicate_price_list)
        layout.addWidget(self.duplicate_btn)

        # Export
        self.export_btn = QPushButton("Izvezi")
        self.export_btn.setProperty("secondary", True)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_price_list)
        layout.addWidget(self.export_btn)

        # Brisanje
        self.delete_btn = QPushButton("Obriši")
        self.delete_btn.setProperty("deleteBtn", True)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._confirm_and_delete)
        layout.addWidget(self.delete_btn)

        return bar

    def _build_status_banner(self) -> QLabel:
        self.status_banner = QLabel("")
        self.status_banner.setWordWrap(True)
        self.status_banner.setVisible(False)
        self.status_banner.setProperty("statusBanner", "success")
        return self.status_banner

    def _build_items_panel(self) -> QWidget:
        """Puna tabela stavki cjenovnika."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)
        # Redoslijed: Rb. | Firma | Naziv artikla | Šifra | Cijena (EUR) | Bod | Status
        self.items_table.setHorizontalHeaderLabels([
            "Rb.", "Firma", "Naziv artikla", "Šifra", "Cijena (EUR)", "Bod", "Status"
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
        
        # Paginacioni widget
        self.pagination_widget = PaginationWidget()
        self.pagination_widget.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.pagination_widget)
        
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
        self.excel_label.setProperty("excelFileSelected", True)
        self.excel_label.style().unpolish(self.excel_label)
        self.excel_label.style().polish(self.excel_label)
        if not self.name_edit.text().strip():
            self.name_edit.setText(Path(file_path).stem)

    def _run_import(self) -> None:
        name = self.name_edit.text().strip()
        if not name and self._excel_path:
            name = Path(self._excel_path).stem
            self.name_edit.setText(name)
        if not name:
            self._show_error_message("Greška", "Naziv cjenovnika je obavezan.", use_banner=True)
            self.name_edit.setFocus()
            return
        if not self._excel_path:
            self._show_error_message("Greška", "Excel fajl nije odabran.", use_banner=True)
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
        self.excel_label.setProperty("excelFileSelected", False)
        self.excel_label.style().unpolish(self.excel_label)
        self.excel_label.style().polish(self.excel_label)
        self._load_price_lists()

    def _on_import_error(self, message: str) -> None:
        self._reset_import_btn()
        self._show_error(message)

    def _reset_import_btn(self) -> None:
        self.import_btn.setEnabled(True)
        self.import_btn.setText("Uvezi cjenovnik")
        # Reset excel label
        if hasattr(self, 'excel_label'):
            self.excel_label.setProperty("excelFileSelected", False)
            self.excel_label.style().unpolish(self.excel_label)
            self.excel_label.style().polish(self.excel_label)

    def _show_success(self, text: str) -> None:
        self._show_status_banner(text, "success")

    def _show_error(self, text: str) -> None:
        self._show_status_banner(f"<b>Greška:</b> {text}", "error")

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
            self.edit_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self._current_price_list_id = None
            self.items_table.setRowCount(0)
            self.items_count_label.setText("")
            self.pagination_widget.reset()
            return
        
        pl = self._price_lists[index]
        self.edit_btn.setEnabled(True)
        self.duplicate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self._current_price_list_id = pl.id
        
        # Resetuj filter i paginaciju
        self._current_filter_text = ""
        self.items_search.clear()
        self.pagination_widget.reset()
        
        # Učitaj prvu stranicu
        self._load_current_page()

    # ------------------------------------------------------------------
    # Brisanje
    # ------------------------------------------------------------------

    def _confirm_and_delete(self) -> None:
        index = self.price_list_combo.currentIndex()
        if index < 0 or index >= len(self._price_lists):
            return
        pl = self._price_lists[index]
        
        confirm = self._confirm_action(
            "Potvrda brisanja",
            f"Da li sigurno želiš obrisati cjenovnik '{pl.name}' i sve njegove stavke?\n"
            "Ova radnja se ne može poništiti."
        )
        
        if not confirm:
            return
        try:
            PriceListService.delete(pl.id)
            self._load_price_lists()
        except Exception as e:
            self._show_error_message("Greška", str(e), use_banner=True)

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

            # Cijena (EUR)
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
        self._current_filter_text = text.lower().strip()
        
        # Ako imamo filter tekst, učitaj ponovo podatke sa filterom
        if self._current_filter_text:
            self._load_current_page()
        else:
            # Ako je filter prazan, samo prikaži sve redove
            for row in range(self.items_table.rowCount()):
                self.items_table.setRowHidden(row, False)
            self.items_count_label.setText(f"{self.items_table.rowCount()} stavki")

    # ------------------------------------------------------------------
    # Paginacija
    # ------------------------------------------------------------------

    def _on_page_changed(self, page: int, page_size: int) -> None:
        """Rukuje promjenom stranice u paginacionom widgetu."""
        self._load_current_page()

    def _load_current_page(self) -> None:
        """Učitava trenutnu stranicu stavki."""
        if not self._current_price_list_id:
            return
        
        self._set_loading_state(True)
        
        try:
            # Dohvati podatke sa paginacijom
            limit = self.pagination_widget.get_limit()
            offset = self.pagination_widget.get_offset()
            
            items, total_count = PriceListService.get_items(
                self._current_price_list_id,
                limit=limit,
                offset=offset
            )
            
            # Ako imamo filter tekst, primijeni ga lokalno
            if self._current_filter_text:
                filtered_items = []
                for item in items:
                    if (self._current_filter_text in item.name.lower() or
                        (item.supplier_code and self._current_filter_text in item.supplier_code.lower()) or
                        (item.supplier and self._current_filter_text in item.supplier.lower())):
                        filtered_items.append(item)
                items = filtered_items
            
            # Popuni tabelu
            self._populate_items(items)
            
            # Ažuriraj paginaciju sa ukupnim brojem stavki
            self.pagination_widget.set_total_items(total_count)
            
            # Ažuriraj label sa brojem prikazanih stavki
            if self._current_filter_text:
                self.items_count_label.setText(f"{len(items)} stavki (filtrirano)")
            else:
                self.items_count_label.setText(f"{len(items)} stavki")
                
        except Exception as e:
            self._show_error_message("Greška", f"Greška pri učitavanju stavki: {e}", use_banner=True)
        finally:
            self._set_loading_state(False)

    # ------------------------------------------------------------------
    # Aktivacija stranice
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        super().on_activate()
        self._load_price_lists()
    
    def on_deactivate(self) -> None:
        """Resetuj stanje kada se stranica deaktivira."""
        super().on_deactivate()
        self._current_price_list_id = None
        self._current_filter_text = ""
        self.pagination_widget.reset()

    # ------------------------------------------------------------------
    # Izmena cenovnika
    # ------------------------------------------------------------------

    def _edit_price_list(self) -> None:
        """Otvara dijalog za izmenu naziva cenovnika."""
        index = self.price_list_combo.currentIndex()
        if index < 0 or index >= len(self._price_lists):
            return
        
        pl = self._price_lists[index]
        current_name = pl.name
        
        # Otvori edit dijalog
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QVBoxLayout,
            QFrame,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Izmeni cenovnik")
        dialog.setMinimumWidth(400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Naziv
        r1 = QHBoxLayout()
        lbl1 = QLabel("Naziv cenovnika:")
        lbl1.setFixedWidth(130)
        name_edit = QLineEdit(current_name)
        name_edit.setPlaceholderText("npr. Cenovnik Mart 2026")
        r1.addWidget(lbl1)
        r1.addWidget(name_edit, 1)
        layout.addLayout(r1)
        
        # Info o izvornom fajlu
        if pl.source_filename:
            r2 = QHBoxLayout()
            lbl2 = QLabel("Izvor:")
            lbl2.setFixedWidth(130)
            source_label = QLabel(pl.source_filename)
            source_label.setStyleSheet("color: #6b7280; font-style: italic;")
            r2.addWidget(lbl2)
            r2.addWidget(source_label, 1)
            layout.addLayout(r2)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep)
        
        # Gumbi
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setText("Sačuvaj izmene")
        ok_btn.setStyleSheet(
            "background:#3b82f6;color:white;border:none;"
            "border-radius:8px;padding:8px 16px;font-weight:700;"
        )
        buttons.button(QDialogButtonBox.Cancel).setText("Odustani")
        layout.addWidget(buttons)
        
        def on_accept():
            new_name = name_edit.text().strip()
            if not new_name:
                self._show_error_message("Greška", "Naziv cenovnika je obavezan.", parent=dialog)
                return
            if new_name == current_name:
                dialog.reject()
                return
            dialog.accept()
        
        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Ažuriraj cenovnik
        try:
            PriceListService.update_price_list(
                price_list_id=pl.id,
                name=name_edit.text().strip()
            )
            self._show_success(f"Cenovnik '{name_edit.text().strip()}' je ažuriran.")
            self._load_price_lists()
        except ValueError as e:
            self._show_error_message("Greška", str(e), use_banner=True)
        except Exception as e:
            self._show_error_message("Greška pri izmeni", str(e), use_banner=True)

    # ------------------------------------------------------------------
    # Duplikacija cenovnika
    # ------------------------------------------------------------------

    def _duplicate_price_list(self) -> None:
        """Otvara dijalog za duplikaciju cenovnika."""
        index = self.price_list_combo.currentIndex()
        if index < 0 or index >= len(self._price_lists):
            return
        
        pl = self._price_lists[index]
        current_name = pl.name
        
        # Otvori duplicate dijalog
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QVBoxLayout,
            QFrame,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Dupliciraj cenovnik")
        dialog.setMinimumWidth(400)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Naziv
        r1 = QHBoxLayout()
        lbl1 = QLabel("Naziv kopije:")
        lbl1.setFixedWidth(130)
        name_edit = QLineEdit(f"Kopija - {current_name}")
        name_edit.setPlaceholderText("npr. Kopija - Cenovnik Mart 2026")
        r1.addWidget(lbl1)
        r1.addWidget(name_edit, 1)
        layout.addLayout(r1)
        
        # Info o originalu
        r2 = QHBoxLayout()
        lbl2 = QLabel("Original:")
        lbl2.setFixedWidth(130)
        original_label = QLabel(current_name)
        original_label.setStyleSheet("color: #6b7280; font-style: italic;")
        r2.addWidget(lbl2)
        r2.addWidget(original_label, 1)
        layout.addLayout(r2)
        
        if pl.source_filename:
            r3 = QHBoxLayout()
            lbl3 = QLabel("Izvor:")
            lbl3.setFixedWidth(130)
            source_label = QLabel(pl.source_filename)
            source_label.setStyleSheet("color: #6b7280; font-style: italic;")
            r3.addWidget(lbl3)
            r3.addWidget(source_label, 1)
            layout.addLayout(r3)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        layout.addWidget(sep)
        
        # Gumbi
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        ok_btn.setText("Kreiraj kopiju")
        ok_btn.setStyleSheet(
            "background:#3b82f6;color:white;border:none;"
            "border-radius:8px;padding:8px 16px;font-weight:700;"
        )
        buttons.button(QDialogButtonBox.Cancel).setText("Odustani")
        layout.addWidget(buttons)
        
        def on_accept():
            new_name = name_edit.text().strip()
            if not new_name:
                self._show_error_message("Greška", "Naziv kopije je obavezan.", parent=dialog)
                return
            dialog.accept()
        
        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Kreiraj kopiju
        try:
            new_id = PriceListService.duplicate_price_list(
                price_list_id=pl.id,
                new_name=name_edit.text().strip()
            )
            self._show_success(f"Cenovnik '{name_edit.text().strip()}' je kreiran kao kopija.")
            self._load_price_lists()
            # Selektuj novi cenovnik
            for i in range(self.price_list_combo.count()):
                if self.price_list_combo.itemData(i) == new_id:
                    self.price_list_combo.setCurrentIndex(i)
                    break
        except ValueError as e:
            self._show_error_message("Greška", str(e), use_banner=True)
        except Exception as e:
            self._show_error_message("Greška pri duplikaciji", str(e), use_banner=True)

    # ------------------------------------------------------------------
    # Export cenovnika
    # ------------------------------------------------------------------

    def _export_price_list(self) -> None:
        """Otvara dijalog za export cenovnika u Excel fajl."""
        index = self.price_list_combo.currentIndex()
        if index < 0 or index >= len(self._price_lists):
            return
        
        pl = self._price_lists[index]
        
        # Otvori file dialog za odabir lokacije
        from PySide6.QtWidgets import QFileDialog
        
        # Predloženi naziv fajla
        suggested_name = f"cenovnik_{pl.name.replace(' ', '_').lower()}.xlsx"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj cenovnik kao Excel",
            suggested_name,
            "Excel fajlovi (*.xlsx);;Svi fajlovi (*)"
        )
        
        if not file_path:
            return  # Korisnik je otkazao
        
        # Dodaj .xlsx ekstenziju ako nedostaje
        if not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'
        
        # Pokreni export
        try:
            output_path = PriceListService.export_price_list(pl.id, file_path)
            self._show_success(f"Cenovnik '{pl.name}' je uspešno izvežen u: {output_path.name}")
        except ValueError as e:
            self._show_error_message("Greška", str(e), use_banner=True)
        except Exception as e:
            self._show_error_message("Greška pri exportu", str(e), use_banner=True)
