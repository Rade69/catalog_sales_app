from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, create_numeric_item, show_empty_state
from app.services.payment_service import PaymentService


class PaymentsPage(QWidget):
    """Stranica za evidenciju uplata."""

    def __init__(self) -> None:
        super().__init__()
        self.selected_installment_id: int | None = None
        self.selected_payment_id: int | None = None
        self._current_remaining: Decimal = Decimal("0.00")

        self._init_ui()
        self._connect_signals()
        self.refresh_all()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- LIJEVI PANEL: Forma i pregled rata ---
        left_card = self._create_left_panel()
        root.addWidget(left_card, 5)

        # --- DESNI PANEL: Pregled uplata ---
        right_card = self._create_right_panel()
        root.addWidget(right_card, 4)

    def _create_left_panel(self) -> QFrame:
        """Kreira lijevi panel sa formom za uplatu."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Title
        title = QLabel("💳 Evidencija uplata")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # 2. Helper text
        helper = QLabel(
            "Prvo odaberi ratu iz pregleda ispod, pa evidentiraj uplatu. "
            "Sistem podržava i djelimične uplate."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #6b7280; font-size: 13px;")
        layout.addWidget(helper)

        # 3. Pretraga rata
        search_group = QGroupBox("🔍 Pretraga rata")
        search_layout = QVBoxLayout(search_group)
        search_layout.setContentsMargins(12, 12, 12, 12)
        
        self.installment_search = QLineEdit()
        self.installment_search.setPlaceholderText("Pretraga po kupcu, artiklu ili kampaniji...")
        self.installment_search.textChanged.connect(self.load_installments)
        search_layout.addWidget(self.installment_search)
        
        layout.addWidget(search_group)

        # 4. Tabela rata
        self.installment_table = QTableWidget(0, 7)
        self.installment_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Rata", "Dospijeće", "Status", "Iznos", "Preostalo"
        ])
        style_table(self.installment_table)
        self.installment_table.itemSelectionChanged.connect(self.populate_installment_details)
        layout.addWidget(self.installment_table, 1)

        # 5. Info o odabranoj rati
        self.selected_info = QLabel("Odabrana rata: ništa nije odabrano")
        self.selected_info.setStyleSheet("color: #374151; font-weight: 600; font-size: 13px;")
        self.selected_info.setWordWrap(True)
        layout.addWidget(self.selected_info)

        # 6. Forma za uplatu (Card unutar card-a)
        payment_form_group = QGroupBox("📝 Nova uplata")
        payment_form_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #059669;
                border: 2px solid #059669;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        payment_form_layout = QVBoxLayout(payment_form_group)
        payment_form_layout.setContentsMargins(16, 16, 16, 16)
        payment_form_layout.setSpacing(12)

        # Grid za polja
        from PySide6.QtWidgets import QGridLayout
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(12)
        form_grid.setVerticalSpacing(10)

        # Iznos uplate
        form_grid.addWidget(QLabel("Iznos uplate (EUR):"), 0, 0)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.01)
        self.amount_input.setMaximum(9999999.99)
        self.amount_input.setSuffix(" EUR")
        self.amount_input.setToolTip("Unesite iznos uplate")
        form_grid.addWidget(self.amount_input, 0, 1)

        # Datum uplate
        form_grid.addWidget(QLabel("Datum uplate:"), 1, 0)
        self.payment_date_input = QDateEdit()
        self.payment_date_input.setCalendarPopup(True)
        self.payment_date_input.setDate(QDate.currentDate())
        self.payment_date_input.setDisplayFormat("dd.MM.yyyy")
        self.payment_date_input.setToolTip("Odaberite datum uplate")
        form_grid.addWidget(self.payment_date_input, 1, 1)

        # Napomena
        form_grid.addWidget(QLabel("Napomena:"), 2, 0)
        self.note_input = QTextEdit()
        self.note_input.setMinimumHeight(70)
        self.note_input.setPlaceholderText("Opciona napomena uz uplatu...")
        form_grid.addWidget(self.note_input, 2, 1)

        payment_form_layout.addLayout(form_grid)

        # Dugmad za brzo popunjavanje
        quick_amount_layout = QHBoxLayout()
        quick_amount_layout.setSpacing(8)

        self.full_amount_btn = QPushButton("💰 Uplati puni iznos")
        self.full_amount_btn.setProperty("secondary", True)
        self.full_amount_btn.setToolTip("Automatski popuni iznos cijele rate")
        self.full_amount_btn.clicked.connect(self._fill_full_amount)
        quick_amount_layout.addWidget(self.full_amount_btn)

        self.remaining_amount_btn = QPushButton("📊 Uplati preostalo")
        self.remaining_amount_btn.setProperty("secondary", True)
        self.remaining_amount_btn.setToolTip("Automatski popuni preostali iznos rate")
        self.remaining_amount_btn.clicked.connect(self._fill_remaining_amount)
        quick_amount_layout.addWidget(self.remaining_amount_btn)

        payment_form_layout.addLayout(quick_amount_layout)

        # Action dugmad
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.save_btn = QPushButton("✅ Evidentiraj uplatu")
        self.save_btn.setProperty("primary", True)
        self.save_btn.setMinimumHeight(44)
        self.save_btn.setToolTip("Sačuvaj uplatu u bazu")
        button_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("🔄 Očisti formu")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.setMinimumHeight(44)
        self.clear_btn.setToolTip("Očisti formu za novi unos")
        button_layout.addWidget(self.clear_btn)

        payment_form_layout.addLayout(button_layout)

        layout.addWidget(payment_form_group)

        return card

    def _create_right_panel(self) -> QFrame:
        """Kreira desni panel sa pregledom uplata."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Title
        title = QLabel("📋 Pregled uplata")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # 2. Pretraga
        search_group = QGroupBox("🔍 Pretraga uplata")
        search_layout = QVBoxLayout(search_group)
        search_layout.setContentsMargins(12, 12, 12, 12)
        
        self.payment_search = QLineEdit()
        self.payment_search.setPlaceholderText("Pretraga po kupcu, artiklu, kampaniji ili napomeni...")
        self.payment_search.textChanged.connect(self.load_payments)
        search_layout.addWidget(self.payment_search)
        
        layout.addWidget(search_group)

        # 3. Tabela uplata
        self.payments_table = QTableWidget(0, 7)
        self.payments_table.setHorizontalHeaderLabels([
            "Datum", "Kupac", "Artikal", "Kampanja", "Rata", "Iznos", "Napomena"
        ])
        style_table(self.payments_table)
        self.payments_table.itemSelectionChanged.connect(self.capture_payment_selection)
        layout.addWidget(self.payments_table, 1)

        # 4. Action dugmad
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.refresh_btn = QPushButton("🔄 Osvježi pregled")
        self.refresh_btn.setProperty("secondary", True)
        self.refresh_btn.clicked.connect(self.refresh_all)
        button_layout.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("🗑️ Obriši odabranu uplatu")
        self.delete_btn.setProperty("secondary", True)
        self.delete_btn.clicked.connect(self.delete_payment)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch(1)
        layout.addLayout(button_layout)

        return card

    def _connect_signals(self) -> None:
        """Povezuje signale sa slotovima."""
        self.save_btn.clicked.connect(self.save_payment)
        self.clear_btn.clicked.connect(self.clear_payment_form)

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self.refresh_all()

    def refresh_all(self) -> None:
        """Osvježava sve podatke na stranici."""
        self.load_installments()
        self.load_payments()

    def load_installments(self) -> None:
        """Učitava rate u tabelu."""
        rows = PaymentService.build_installment_lookup(self.installment_search.text(), only_open=True)

        if not rows:
            show_empty_state(self.installment_table, "Nema rata za prikaz")
            return

        self.installment_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.customer_name,
                row.product_name,
                f"{row.installment_number}/{row.installments_count}",
                row.due_date.strftime("%d.%m.%Y"),
                self.translate_status(row.status),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row.installment_id)
                self.installment_table.setItem(row_index, column_index, item)

            # Numeričke kolone
            self.installment_table.setItem(row_index, 5, create_numeric_item(row.amount, " EUR"))
            self.installment_table.setItem(row_index, 6, create_numeric_item(row.remaining_amount, " EUR"))

        self.installment_table.resizeColumnsToContents()

    def populate_installment_details(self) -> None:
        """Popunjava formu detaljima o odabranoj rati."""
        row = self.installment_table.currentRow()
        if row < 0:
            return
        item = self.installment_table.item(row, 0)
        if item is None:
            return
        installment_id = item.data(Qt.UserRole)
        if installment_id is None:
            return

        installment = PaymentService.get_installment(int(installment_id))
        order = installment.order
        self.selected_installment_id = installment.id
        self._current_remaining = Decimal(str(installment.remaining_amount))
        
        # Automatski popuni preostali iznos
        self.amount_input.setValue(float(self._current_remaining))
        
        # Ažuriraj info label
        self.selected_info.setText(
            f"Odabrana rata: {order.customer.full_name} — {order.product_name_snapshot} — "
            f"rata {installment.installment_number}/{order.installments_count} — "
            f"preostalo {self._current_remaining:.2f} EUR"
        )

    def _fill_full_amount(self) -> None:
        """Popunjava iznos pune rate (ne preostalo, nego originalni iznos)."""
        if self.selected_installment_id is None:
            QMessageBox.information(self, "Informacija", "Prvo odaberi ratu iz pregleda.")
            return
        
        installment = PaymentService.get_installment(self.selected_installment_id)
        full_amount = Decimal(str(installment.amount))
        self.amount_input.setValue(float(full_amount))

    def _fill_remaining_amount(self) -> None:
        """Popunjava iznos preostalog duga na rati."""
        if self.selected_installment_id is None:
            QMessageBox.information(self, "Informacija", "Prvo odaberi ratu iz pregleda.")
            return
        
        self.amount_input.setValue(float(self._current_remaining))

    def save_payment(self) -> None:
        """Evidentira novu uplatu."""
        # Validacija
        if self.selected_installment_id is None:
            QMessageBox.information(self, "Uplate", "Prvo odaberi ratu iz lijevog pregleda.")
            return
        
        amount = self.amount_input.value()
        if amount <= 0:
            QMessageBox.warning(self, "Greška", "Iznos uplate mora biti veći od 0.")
            return
        
        try:
            PaymentService.create_payment(
                installment_id=self.selected_installment_id,
                amount=amount,
                payment_date=self.payment_date_input.date().toPython(),
                note=self.note_input.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))
            return

        # Uspjeh
        QMessageBox.information(
            self,
            "Uspjeh",
            f"Uplata od {amount:.2f} EUR je evidentirana."
        )

        self.clear_payment_form()
        self.refresh_all()

    def clear_payment_form(self) -> None:
        """Čisti formu za uplatu."""
        self.selected_installment_id = None
        self._current_remaining = Decimal("0.00")
        self.selected_info.setText("Odabrana rata: ništa nije odabrano")
        self.amount_input.setValue(0.01)
        self.payment_date_input.setDate(QDate.currentDate())
        self.note_input.clear()
        self.installment_table.clearSelection()

    def load_payments(self) -> None:
        """Učitava uplate u tabelu."""
        payments = PaymentService.list_payments(self.payment_search.text())

        if not payments:
            show_empty_state(self.payments_table, "Nema uplata za prikaz")
            return

        self.payments_table.setRowCount(len(payments))
        for row_index, payment in enumerate(payments):
            installment = payment.installment
            order = installment.order
            values = [
                payment.payment_date.strftime("%d.%m.%Y"),
                order.customer.full_name,
                order.product_name_snapshot,
                order.campaign.name,
                f"{installment.installment_number}/{order.installments_count}",
                payment.note or "",
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, payment.id)
                self.payments_table.setItem(row_index, column_index, item)

            # Numerička kolona
            self.payments_table.setItem(row_index, 5, create_numeric_item(payment.amount, " EUR"))

        self.payments_table.resizeColumnsToContents()

    def capture_payment_selection(self) -> None:
        """Bilježi odabranu uplatu za brisanje."""
        row = self.payments_table.currentRow()
        if row < 0:
            self.selected_payment_id = None
            return
        item = self.payments_table.item(row, 0)
        self.selected_payment_id = item.data(Qt.UserRole) if item else None

    def delete_payment(self) -> None:
        """Briše odabranu uplatu."""
        if self.selected_payment_id is None:
            QMessageBox.information(self, "Brisanje", "Prvo odaberi uplatu iz desne tabele.")
            return
        
        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            "Da li sigurno želiš obrisati odabranu uplatu?\n\nOva radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        
        try:
            PaymentService.delete_payment(int(self.selected_payment_id))
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))
            return
        
        QMessageBox.information(self, "Uspjeh", "Uplata je obrisana.")
        self.selected_payment_id = None
        self.refresh_all()

    @staticmethod
    def translate_status(status: str) -> str:
        """Prevodi status rate na bosanski jezik."""
        mapping = {
            "pending": "Na čekanju",
            "partially_paid": "Djelimično plaćeno",
            "paid": "Plaćeno",
            "overdue": "Kasni",
            "cancelled": "Otkazano",
        }
        return mapping.get(status, status)
