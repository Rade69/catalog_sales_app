from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table
from app.services.payment_service import PaymentService
from app.services.customer_service import CustomerService
from app.gui.workers import LoadInstallmentsWorker


# Boje po statusu rate
_STATUS_COLOR = {
    "pending":        ("#f59e0b", "#fffbeb"),   # žuta
    "partially_paid": ("#3b82f6", "#eff6ff"),   # plava
    "paid":           ("#10b981", "#f0fdf4"),   # zelena
    "overdue":        ("#ef4444", "#fef2f2"),   # crvena
    "cancelled":      ("#9ca3af", "#f9fafb"),   # siva
}

_STATUS_LABEL = {
    "pending":        "Na čekanju",
    "partially_paid": "Djelimično",
    "paid":           "Plaćeno",
    "overdue":        "Kasni",
    "cancelled":      "Otkazano",
}

_FILTER_TABS = [
    ("overdue",  "⚠ Kasne rate"),
    ("month",    "📅 Ovaj mjesec"),
    ("unpaid",   "💳 Sve neplaćene"),
    ("all",      "☰ Sve rate"),
]


class InstallmentsPage(QWidget):
    """
    Stranica za pregled svih rata.

    Layout:
    - Toolbar: filter po kupcu + search + tab dugmad (Kasne / Ovaj mjesec / Neplaćene / Sve)
    - Lijevo: tabela rata
    - Desno: info panel odabrane rate (read-only)

    Klik na ratu → prikazuje detalje desno i nudi brzi link na PaymentsPage.
    """

    def __init__(self) -> None:
        super().__init__()
        self._active_filter = "overdue"
        self._selected_installment_id: Optional[int] = None
        self._worker: Optional[LoadInstallmentsWorker] = None
        self._loading_label: Optional[QLabel] = None

        self._init_ui()
        self._load_customers()
        self._load_installments()

    # ------------------------------------------------------------------
    # UI izgradnja
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #e5e7eb; }")
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([900, 400])
        splitter.setStretchFactor(0, 1)
        root.addWidget(splitter, 1)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("card", True)
        bar.setFixedHeight(58)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Kupac combo
        self.customer_combo = QComboBox()
        self.customer_combo.setPlaceholderText("Svi kupci")
        self.customer_combo.setMinimumWidth(200)
        self.customer_combo.setMaximumWidth(250)
        self.customer_combo.currentIndexChanged.connect(self._load_installments)
        layout.addWidget(self.customer_combo)

        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Pretraži po kupcu, artiklu ili br. ugovora...")
        self.search_edit.setMaximumWidth(250)
        self.search_edit.textChanged.connect(self._load_installments)
        layout.addWidget(self.search_edit)

        layout.addSpacing(12)

        # Filter tab dugmad
        self._filter_btns: dict[str, QPushButton] = {}
        for key, label in _FILTER_TABS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == self._active_filter)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            self._filter_btns[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        # Refresh
        refresh_btn = QPushButton("↻ Osvježi")
        refresh_btn.setProperty("secondary", True)
        refresh_btn.setFixedHeight(34)
        refresh_btn.clicked.connect(self._load_installments)
        layout.addWidget(refresh_btn)

        return bar

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Naslov + brojač
        header = QHBoxLayout()
        self.table_title = QLabel("Rate")
        self.table_title.setProperty("sectionTitle", True)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        header.addWidget(self.table_title)
        header.addStretch(1)
        header.addWidget(self.count_label)
        layout.addLayout(header)

        # Loading label (skriven dok se ne učitava)
        self._loading_label = QLabel("Učitavanje rata...")
        self._loading_label.setStyleSheet(
            "color: #6b7280; font-size: 13px; font-style: italic; padding: 4px;"
        )
        self._loading_label.hide()
        layout.addWidget(self._loading_label)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Rata", "Dospijeće",
            "Iznos (EUR)", "Plaćeno (EUR)", "Status",
        ])
        style_table(self.table)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

        return panel

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Detalji rate")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # Info blok
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(
            "QFrame { background: #f9fafb; border-radius: 10px; border: 1px solid #e5e7eb; }"
        )
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)

        self.lbl_placeholder = QLabel("← Odaberi ratu iz tabele")
        self.lbl_placeholder.setStyleSheet("color: #9ca3af; font-size: 14px;")
        info_layout.addWidget(self.lbl_placeholder)

        self.lbl_kupac = QLabel("")
        self.lbl_kupac.setStyleSheet("font-size: 15px; font-weight: 700; color: #111827;")
        self.lbl_kupac.setWordWrap(True)
        self.lbl_kupac.hide()

        self.lbl_artikal = QLabel("")
        self.lbl_artikal.setStyleSheet("color: #6b7280; font-size: 13px;")
        self.lbl_artikal.setWordWrap(True)
        self.lbl_artikal.hide()

        self.lbl_rata_broj = QLabel("")
        self.lbl_rata_broj.setStyleSheet("color: #374151; font-size: 13px;")
        self.lbl_rata_broj.hide()

        self.lbl_dospijeće = QLabel("")
        self.lbl_dospijeće.setStyleSheet("color: #374151; font-size: 13px;")
        self.lbl_dospijeće.hide()

        self.lbl_status_badge = QLabel("")
        self.lbl_status_badge.setStyleSheet(
            "font-size: 13px; font-weight: 700; border-radius: 6px; padding: 4px 12px;"
        )
        self.lbl_status_badge.hide()

        # Iznosi
        self.amounts_frame = QFrame()
        self.amounts_frame.hide()
        amounts_layout = QHBoxLayout(self.amounts_frame)
        amounts_layout.setContentsMargins(0, 0, 0, 0)
        amounts_layout.setSpacing(16)

        for attr, lbl_text, color in [
            ("lbl_iznos",     "Rata:",     "#111827"),
            ("lbl_placeno",   "Plaćeno:",  "#059669"),
            ("lbl_preostalo", "Preostalo:", "#dc2626"),
        ]:
            col = QVBoxLayout()
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
            val = QLabel("—")
            val.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {color};")
            setattr(self, attr + "_lbl", lbl)
            setattr(self, attr + "_val", val)
            col.addWidget(lbl)
            col.addWidget(val)
            amounts_layout.addLayout(col)

        amounts_layout.addStretch(1)

        info_layout.addWidget(self.lbl_kupac)
        info_layout.addWidget(self.lbl_artikal)
        info_layout.addWidget(self.lbl_rata_broj)
        info_layout.addWidget(self.lbl_dospijeće)
        info_layout.addWidget(self.lbl_status_badge)
        info_layout.addWidget(self.amounts_frame)

        layout.addWidget(self.info_frame)
        layout.addStretch(1)

        return panel

    # ------------------------------------------------------------------
    # Učitavanje podataka
    # ------------------------------------------------------------------

    def _load_customers(self) -> None:
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("Svi kupci", userData=None)
        for c in CustomerService.list_customers():
            self.customer_combo.addItem(c.full_name, userData=c.id)
        self.customer_combo.blockSignals(False)

    def _load_installments(self) -> None:
        """Učitava rate koristeći background worker."""
        # Zaštita od višestrukog pokretanja
        if self._worker and self._worker.isRunning():
            return

        # Prikaži loading
        self._set_loading_state(True)

        customer_id = self.customer_combo.currentData()
        search = self.search_edit.text().strip()

        self._worker = LoadInstallmentsWorker(
            filter_type=self._active_filter,
            search=search,
            customer_id=customer_id,
        )
        self._worker.finished.connect(self._on_installments_loaded)
        self._worker.error.connect(self._on_installments_error)
        self._worker.start()

    def _set_loading_state(self, loading: bool) -> None:
        """Postavlja UI u loading stanje."""
        if loading:
            self._loading_label.show()
            self.table.setEnabled(False)
        else:
            self._loading_label.hide()
            self.table.setEnabled(True)

    def _on_installments_loaded(self, installments) -> None:
        """Handler za završetak učitavanja rata."""
        self._set_loading_state(False)

        # Ažuriraj naslov i brojač
        filter_labels = dict(_FILTER_TABS)
        self.table_title.setText(filter_labels.get(self._active_filter, "Rate"))
        self.count_label.setText(f"{len(installments)} stavki")

        if not installments:
            self.table.setRowCount(1)
            item = QTableWidgetItem("Nema rata za prikaz.")
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(QColor("#9ca3af"))
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(installments))

        for row, inst in enumerate(installments):
            # Koristi denormalizovane podatke iz DTO-a (izbjegava ORM pristup)
            customer_name = inst.order_customer_name or "N/A"
            product_name = inst.order_product_name or "N/A"
            installments_count = inst.order_installments_count or "?"

            paid = inst.paid_amount
            remaining = inst.amount - paid
            remaining = max(remaining, Decimal("0.00"))
            status = inst.status.value if hasattr(inst.status, "value") else str(inst.status)

            # Podaci
            vals = [
                customer_name,
                product_name,
                f"{inst.installment_number}/{installments_count}",
                inst.due_date.strftime("%d.%m.%Y"),
                f"{inst.amount:.2f}",
                f"{paid:.2f}",
                _STATUS_LABEL.get(status, status),
            ]

            fg_color, bg_color = _STATUS_COLOR.get(status, ("#374151", "#ffffff"))

            for col, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if col >= 4:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                # Boja statusa samo u zadnjoj koloni
                if col == 6:
                    cell.setForeground(QColor(fg_color))
                    font = QFont()
                    font.setBold(True)
                    cell.setFont(font)

                # Alternativna boja reda za kasne/neplaćene
                if status == "overdue":
                    cell.setBackground(QBrush(QColor("#fff5f5")))
                elif status == "partially_paid":
                    cell.setBackground(QBrush(QColor("#eff8ff")))

                self.table.setItem(row, col, cell)

            # Spremi installment_id u UserRole prvog cella
            self.table.item(row, 0).setData(Qt.UserRole, inst.id)

        self.table.resizeColumnsToContents()

    def _on_installments_error(self, error_msg: str) -> None:
        """Handler za grešku prilikom učitavanja rata."""
        self._set_loading_state(False)
        QMessageBox.critical(
            self,
            "Greška pri učitavanju",
            f"Neuspješno učitavanje rata:\n{error_msg}"
        )

    # ------------------------------------------------------------------
    # Akcije
    # ------------------------------------------------------------------

    def _set_filter(self, key: str) -> None:
        self._active_filter = key
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == key)
        self._load_installments()

    def _on_row_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        installment_id = item.data(Qt.UserRole)
        if not installment_id:
            return

        self._selected_installment_id = installment_id
        self._show_installment_details(installment_id)

    def _show_installment_details(self, installment_id: int) -> None:
        inst = PaymentService.get_installment_details(installment_id)
        if not inst:
            return

        # Koristi denormalizovane podatke iz DTO-a
        customer_name = inst.order_customer_name or "N/A"
        product_name = inst.order_product_name or "N/A"
        installments_count = inst.order_installments_count or 0

        paid = inst.paid_amount
        remaining = max(inst.amount - paid, Decimal("0.00"))
        status = inst.status.value if hasattr(inst.status, "value") else str(inst.status)

        # Prikaži widgete
        self.lbl_placeholder.hide()
        for w in [self.lbl_kupac, self.lbl_artikal, self.lbl_rata_broj,
                  self.lbl_dospijeće, self.lbl_status_badge, self.amounts_frame]:
            w.show()

        self.lbl_kupac.setText(customer_name)
        self.lbl_artikal.setText(product_name)
        if installments_count:
            self.lbl_rata_broj.setText(
                f"Rata {inst.installment_number} od {installments_count}"
            )
        self.lbl_dospijeće.setText(f"Dospijeće: {inst.due_date.strftime('%d.%m.%Y.')}")

        fg, bg = _STATUS_COLOR.get(status, ("#374151", "#f9fafb"))
        self.lbl_status_badge.setText(_STATUS_LABEL.get(status, status))
        self.lbl_status_badge.setStyleSheet(
            f"font-size: 13px; font-weight: 700; border-radius: 6px; padding: 4px 12px;"
            f"color: {fg}; background: {bg}; border: 1px solid {fg}40;"
        )

        self.lbl_iznos_val.setText(f"{inst.amount:.2f} EUR")
        self.lbl_placeno_val.setText(f"{paid:.2f} EUR")
        self.lbl_preostalo_val.setText(f"{remaining:.2f} EUR")

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_customers()
        self._load_installments()
