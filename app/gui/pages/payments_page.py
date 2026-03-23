from __future__ import annotations

from datetime import date
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

from app.services.payment_service import PaymentService
from app.gui.icons import create_icon_label, get_pixmap


class PaymentsPage(QWidget):
    """
    Stranica za evidenciju uplata.

    Layout:
    - Lijevo: tabela svih neplaćenih/djelimičnih rata sa filterima
    - Desno: panel za uplatu odabrane rate
    """

    def __init__(self) -> None:
        super().__init__()
        self._selected_installment_id: Optional[int] = None
        self._selected_installment_data: Optional[dict] = None
        self._active_filter = "overdue"
        self._selected_customer_id: Optional[int] = None
        self._init_ui()
        self._load_customers()
        self._load_installments()

    # ------------------------------------------------------------------
    # Izgradnja UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Toolbar — filter dugmad
        root.addWidget(self._build_toolbar())

        # Split panel
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #e5e7eb; }")
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([820, 460])
        splitter.setStretchFactor(0, 1)
        root.addWidget(splitter, 1)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setProperty("card", True)
        bar.setFixedHeight(58)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Padajući meni za kupce
        self.customer_combo = QComboBox()
        self.customer_combo.setPlaceholderText("Svi kupci")
        self.customer_combo.setFixedSize(160, 34)
        self.customer_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 0px 10px;
                background: white;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
            }
            QComboBox:hover { background: #f3f4f6; }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #6b7280;
                width: 0;
                height: 0;
                margin-right: 6px;
            }
        """)
        self.customer_combo.currentIndexChanged.connect(self._load_installments)
        layout.addWidget(self.customer_combo)

        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Pretraži po kupcu...")
        self.search_edit.setFixedSize(180, 34)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 0px 10px;
                background: white;
                color: #374151;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2563eb; }
        """)
        self.search_edit.textChanged.connect(self._load_installments)
        layout.addWidget(self.search_edit)

        layout.addSpacing(12)

        # Filter gumbi
        filter_label = QLabel("Prikaži:")
        filter_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(filter_label)

        FILTER_BTN_STYLE = """
            QPushButton {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 0px 10px;
                background: white;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:checked {
                background: #2563eb;
                color: white;
                border-color: #2563eb;
            }
            QPushButton:hover:!checked { background: #f3f4f6; }
        """

        self.filter_buttons: dict[str, QPushButton] = {}
        self._filter_icons: dict[str, str] = {
            "all":     "refresh",
            "overdue": "alert",
            "month":   "calendar",
            "unpaid":  "refresh",
        }
        filters = [
            ("all",     "Sve rate"),
            ("overdue", "Kasne"),
            ("month",   "Ovaj mjesec"),
            ("unpaid",  "Neplaćene"),
        ]
        for key, label in filters:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("secondary", True)
            btn.setFixedSize(130, 34)
            btn.setStyleSheet(FILTER_BTN_STYLE)
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            btn.setIcon(get_pixmap(self._filter_icons[key], "#374151", 16))
            layout.addWidget(btn)
            self.filter_buttons[key] = btn

        self.filter_buttons["overdue"].setChecked(True)
        self.filter_buttons["overdue"].setIcon(
            get_pixmap(self._filter_icons["overdue"], "white", 16)
        )
        self._active_filter = "overdue"

        layout.addStretch(1)

        # Broj vidljivih rata
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(self.count_label)

        return bar

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Rate za naplatu")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # Tabela rata
        self.installments_table = QTableWidget()
        self.installments_table.setColumnCount(8)
        self.installments_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Vrijednost", "Plaćeno", "Preostalo",
            "Rata", "Dospijeće", "Status"
        ])

        h = self.installments_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)        # Kupac
        h.setSectionResizeMode(1, QHeaderView.Stretch)        # Artikal
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Vrijednost
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Plaćeno
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Preostalo
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Rata
        h.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Dospijeće
        h.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status

        self.installments_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.installments_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.installments_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.installments_table.setAlternatingRowColors(True)
        self.installments_table.verticalHeader().setVisible(False)
        self.installments_table.itemSelectionChanged.connect(
            self._on_installment_selected
        )

        layout.addWidget(self.installments_table, 1)
        return panel

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # --- Info o odabranoj rati ---
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(
            "QFrame { background: #f9fafb; border-radius: 10px; }"
        )
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(6)

        self.info_kupac = QLabel("← Odaberi ratu iz tabele")
        self.info_kupac.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #111827;"
        )
        self.info_artikal = QLabel("")
        self.info_artikal.setStyleSheet("color: #6b7280; font-size: 13px;")

        # Iznos rate (pojednostavljeno - samo iznos)
        amounts_row = QHBoxLayout()
        self.info_iznos_lbl = QLabel("Iznos rate:")
        self.info_iznos_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.info_iznos_val = QLabel("")
        self.info_iznos_val.setStyleSheet(
            "font-size: 16px; font-weight: 800; color: #111827;"
        )
        amounts_row.addWidget(self.info_iznos_lbl)
        amounts_row.addWidget(self.info_iznos_val)
        amounts_row.addStretch(1)

        info_layout.addWidget(self.info_kupac)
        info_layout.addWidget(self.info_artikal)
        info_layout.addLayout(amounts_row)
        layout.addWidget(self.info_frame)

        # --- Forma za uplatu ---
        self.form_frame = QFrame()
        self.form_frame.setEnabled(False)  # disabled dok nije rata odabrana
        form_layout = QVBoxLayout(self.form_frame)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        form_title = QLabel("Nova uplata")
        form_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #374151;")
        form_layout.addWidget(form_title)

        # Iznos
        iznos_row = QHBoxLayout()
        iznos_lbl = QLabel("Iznos uplate (EUR):")
        iznos_lbl.setFixedWidth(110)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setMinimum(0.01)
        self.amount_spin.setMaximum(99999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(1.0)
        self.amount_spin.setMinimumHeight(38)
        iznos_row.addWidget(iznos_lbl)
        iznos_row.addWidget(self.amount_spin, 1)
        form_layout.addLayout(iznos_row)

        # Datum
        datum_row = QHBoxLayout()
        datum_lbl = QLabel("Datum uplate:")
        datum_lbl.setFixedWidth(110)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy.")
        self.date_edit.setMinimumHeight(38)
        datum_row.addWidget(datum_lbl)
        datum_row.addWidget(self.date_edit, 1)
        form_layout.addLayout(datum_row)

        # Napomena
        napomena_row = QHBoxLayout()
        napomena_lbl = QLabel("Napomena:")
        napomena_lbl.setFixedWidth(110)
        napomena_lbl.setAlignment(Qt.AlignTop)
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Opciona napomena uz uplatu...")
        self.note_edit.setMaximumHeight(80)
        napomena_row.addWidget(napomena_lbl)
        napomena_row.addWidget(self.note_edit, 1)
        form_layout.addLayout(napomena_row)

        # Akcijska dugmad
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_evidentiraj = QPushButton("Evidentiraj uplatu")
        self.btn_evidentiraj.setMinimumHeight(44)
        self.btn_evidentiraj.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 20px;
                font-weight: 700;
                font-size: 14px;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #d1d5db; color: #9ca3af; }
        """)
        cc_pixmap = get_pixmap("credit-card", "#ffffff", 18)
        self.btn_evidentiraj.setIcon(cc_pixmap)
        self.btn_evidentiraj.clicked.connect(self._evidentiraj_uplatu)

        self.btn_ocisti = QPushButton("Očisti")
        self.btn_ocisti.setProperty("secondary", True)
        self.btn_ocisti.setMinimumHeight(44)
        self.btn_ocisti.clicked.connect(self._ocisti_formu)

        action_row.addWidget(self.btn_evidentiraj, 1)
        action_row.addWidget(self.btn_ocisti)
        form_layout.addLayout(action_row)

        layout.addWidget(self.form_frame)
        layout.addStretch(1)

        # --- Historija uplata odabrane rate ---
        self.history_frame = QFrame()
        history_layout = QVBoxLayout(self.history_frame)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(6)

        history_title = QLabel("Historija uplata ove rate")
        history_title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #374151;"
        )
        history_layout.addWidget(history_title)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Datum", "Iznos (EUR)", "Napomena", ""])
        hh = self.history_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setMaximumHeight(160)
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)

        self.history_frame.setVisible(False)
        layout.addWidget(self.history_frame)

        return panel

    # ------------------------------------------------------------------
    # Učitavanje i filtriranje
    # ------------------------------------------------------------------

    def _load_customers(self) -> None:
        """Učitava kupce u padajući meni."""
        from app.services.customer_service import CustomerService
        
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("Svi kupci", userData=None)
        
        customers = CustomerService.list_customers()
        for customer in customers:
            self.customer_combo.addItem(
                customer.full_name,
                userData=customer.id
            )
        
        self.customer_combo.blockSignals(False)

    def _load_installments(self) -> None:
        """Učitava rate sa filtrima - filteri rade i kad je kupac odabran.
        
        Ako je kupac odabran, automatski filtrira samo NEPLAĆENE rate.
        """
        customer_id = self.customer_combo.currentData()
        search_text = self.search_edit.text().strip()
        
        filter_to_use = self._active_filter

        try:
            installments = PaymentService.get_installments_for_payment(
                filter_type=filter_to_use,
                search=search_text,
                customer_id=customer_id
            )
        except Exception:
            installments = []

        self._populate_table(installments)

    def _populate_table(self, installments: list) -> None:
        self.installments_table.setRowCount(0)
        self.installments_table.setRowCount(len(installments))

        STATUS_STYLE = {
            "overdue":        ("KASNI",      "#fee2e2", "#991b1b"),
            "partially_paid": ("DJELIMIČNO", "#fef3c7", "#92400e"),
            "pending":        ("ČEKA",       "#f3f4f6", "#6b7280"),
            "paid":           ("PLAĆENO",    "#dcfce7", "#166534"),
        }

        today = date.today()

        for i, inst in enumerate(installments):
            # Koristi denormalizovane podatke iz DTO-a (izbjegava ORM pristup)
            kupac = inst.order_customer_name or ""
            self.installments_table.setItem(i, 0, QTableWidgetItem(kupac))

            # Artikal
            artikal = inst.order_product_name or ""
            self.installments_table.setItem(i, 1, QTableWidgetItem(artikal))

            # Vrijednost (ukupna cijena narudžbe)
            order_value = inst.order_total_price
            value_item = QTableWidgetItem(f"{order_value:.2f}")
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.installments_table.setItem(i, 2, value_item)

            # Plaćeno (ukupno uplaćeno za ovu ratu)
            paid_total = inst.paid_amount
            paid_item = QTableWidgetItem(f"{paid_total:.2f}")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if paid_total > 0:
                paid_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(i, 3, paid_item)

            # Preostalo (Vrijednost - Plaćeno)
            remaining = order_value - paid_total
            remaining_item = QTableWidgetItem(f"{remaining:.2f}")
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if remaining > Decimal("0.01"):
                remaining_item.setForeground(QBrush(QColor("#dc2626")))
            else:
                remaining_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(i, 4, remaining_item)

            # Rata N/M
            total = inst.order_installments_count or "?"
            rata_item = QTableWidgetItem(f"{inst.installment_number}/{total}")
            rata_item.setTextAlignment(Qt.AlignCenter)
            rata_item.setData(Qt.UserRole, inst.id)
            self.installments_table.setItem(i, 5, rata_item)

            # Dospijeće — crveno ako kasni
            due_item = QTableWidgetItem(inst.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)
            if inst.due_date < today:
                due_item.setForeground(QBrush(QColor("#dc2626")))
            self.installments_table.setItem(i, 6, due_item)

            # [UKLONJENO: Iznos rate]

            # [UKLONJENO: Staro Plaćeno]

            # Status badge
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            label, bg, fg = STATUS_STYLE.get(status_val, ("?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 7, status_item)

            # Blago crveni red za kasne rate
            if status_val == "overdue":
                for col in range(self.installments_table.columnCount()):
                    item = self.installments_table.item(i, col)
                    if item and col != 6:
                        item.setBackground(QBrush(QColor("#fff8f8")))

        self.count_label.setText(f"{len(installments)} rata")

    def _set_filter(self, key: str) -> None:
        """Postavlja aktivni filter i učitava rate."""
        for k, btn in self.filter_buttons.items():
            checked = (k == key)
            btn.setChecked(checked)
            color = "white" if checked else "#374151"
            btn.setIcon(get_pixmap(self._filter_icons[k], color, 16))
        self._active_filter = key
        
        # AKO JE KUPEC ODABRAN → filteri se ignorišu (prikazuju se SVE rate)
        # Samo osvježi tabelu
        self._selected_customer_id = self.customer_combo.currentData()
        self._load_installments()

    def _apply_filters(self) -> None:
        self._load_installments()

    # ------------------------------------------------------------------
    # Odabir rate
    # ------------------------------------------------------------------

    def _on_installment_selected(self) -> None:
        selected = self.installments_table.selectedItems()
        if not selected:
            self._clear_selection()
            return

        row = self.installments_table.currentRow()
        rata_item = self.installments_table.item(row, 5)
        if rata_item is None:
            return

        installment_id = rata_item.data(Qt.UserRole)
        self._selected_installment_id = installment_id

        # Dohvati detalje iz servisa
        try:
            details = PaymentService.get_installment_details(installment_id)
        except Exception:
            details = None

        if details is None:
            return

        # Popuni info panel - samo iznos rate
        kupac = self.installments_table.item(row, 0)
        artikal = self.installments_table.item(row, 1)
        self.info_kupac.setText(kupac.text() if kupac else "")
        rata_txt = self.installments_table.item(row, 2)
        self.info_artikal.setText(
            f"{artikal.text() if artikal else ''} — Rata {rata_txt.text() if rata_txt else ''}"
        )

        amount = Decimal(str(details.amount))
        self.info_iznos_val.setText(f"{amount:.2f} EUR")

        self._selected_installment_data = {
            "amount": amount,
        }

        # Postavi default iznos = iznos rate
        self.amount_spin.setValue(float(amount))
        self.date_edit.setDate(QDate.currentDate())
        self.note_edit.clear()

        # Aktiviraj formu
        self.form_frame.setEnabled(True)
        self.btn_evidentiraj.setEnabled(True)

        # Prikaži historiju uplata
        self._load_payment_history(installment_id)

    def _clear_selection(self) -> None:
        self._selected_installment_id = None
        self._selected_installment_data = None
        self.info_kupac.setText("← Odaberi ratu iz tabele")
        self.info_artikal.setText("")
        self.info_iznos_val.setText("")
        self.form_frame.setEnabled(False)
        self.history_frame.setVisible(False)

    # ------------------------------------------------------------------
    # Akcije forme
    # ------------------------------------------------------------------

    def _evidentiraj_uplatu(self) -> None:
        if self._selected_installment_id is None:
            return

        amount = Decimal(str(self.amount_spin.value())).quantize(Decimal("0.01"))

        payment_date = self.date_edit.date().toPython()
        note = self.note_edit.toPlainText().strip() or None

        try:
            PaymentService.create_payment(
                installment_id=self._selected_installment_id,
                amount=amount,
                payment_date=payment_date,
                note=note,
            )
            QMessageBox.information(
                self, "Uspješno",
                f"Uplata od {amount:.2f} EUR je evidentirana."
            )
            self._ocisti_formu()
            self._load_installments()
        except ValueError as e:
            QMessageBox.warning(self, "Greška", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Greška", str(e))

    def _ocisti_formu(self) -> None:
        self.amount_spin.setValue(0.01)
        self.date_edit.setDate(QDate.currentDate())
        self.note_edit.clear()
        self.installments_table.clearSelection()
        self._clear_selection()

    # ------------------------------------------------------------------
    # Historija uplata
    # ------------------------------------------------------------------

    def _load_payment_history(self, installment_id: int) -> None:
        try:
            payments = PaymentService.get_payments_for_installment(installment_id)
        except Exception:
            payments = []

        if not payments:
            self.history_frame.setVisible(False)
            return

        self.history_table.setRowCount(0)
        self.history_table.setRowCount(len(payments))

        for i, payment in enumerate(payments):
            date_item = QTableWidgetItem(
                payment.payment_date.strftime("%d.%m.%Y.")
            )
            date_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(i, 0, date_item)

            amt_item = QTableWidgetItem(f"{Decimal(str(payment.amount)):.2f}")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amt_item.setForeground(QBrush(QColor("#059669")))
            self.history_table.setItem(i, 1, amt_item)

            self.history_table.setItem(
                i, 2, QTableWidgetItem(payment.note or "")
            )

            # Dugme za brisanje uplate
            delete_btn = QPushButton("🗑")
            delete_btn.setToolTip("Obriši ovu uplatu")
            delete_btn.setFixedSize(28, 28)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #dc2626;
                    border: 1px solid #fca5a5;
                    border-radius: 6px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #fef2f2;
                }
            """)
            payment_id = payment.id
            iznos_str = f"{payment.amount:.2f}"
            delete_btn.clicked.connect(
                lambda checked=False, pid=payment_id, izn=iznos_str:
                self._delete_payment(pid, izn)
            )
            self.history_table.setCellWidget(i, 3, delete_btn)

        self.history_frame.setVisible(True)

    def _delete_payment(self, payment_id: int, iznos: str) -> None:
        """Briše uplatu nakon potvrde."""
        reply = QMessageBox.question(
            self,
            "Potvrda brisanja uplate",
            f"Da li sigurno želiš obrisati uplatu od {iznos} EUR?\n\n"
            "Status rate i narudžbe će biti automatski ažurirani.\n"
            "Ova radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            PaymentService.delete_payment(payment_id)
            # Osvježi panel i tabelu
            if self._selected_installment_id:
                self._show_installment_details(self._selected_installment_id)
            self._load_installments()
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        self._load_installments()
