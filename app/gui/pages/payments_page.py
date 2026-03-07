from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
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

from app.services.payment_service import PaymentService


class PaymentsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.selected_installment_id: int | None = None
        self.selected_payment_id: int | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        left_card = QFrame()
        left_card.setProperty('card', True)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)

        title = QLabel('Uplate — evidencija')
        title.setProperty('sectionTitle', True)
        left_layout.addWidget(title)

        helper = QLabel('Prvo odaberi ratu iz pregleda ispod, pa evidentiraj uplatu. Sistem podržava i djelimične uplate.')
        helper.setWordWrap(True)
        helper.setStyleSheet('color: #6b7280;')
        left_layout.addWidget(helper)

        self.installment_search = QLineEdit()
        self.installment_search.setPlaceholderText('Pretraga rata po kupcu, artiklu ili kampanji...')
        self.installment_search.textChanged.connect(self.load_installments)
        left_layout.addWidget(self.installment_search)

        self.installment_table = QTableWidget(0, 7)
        self.installment_table.setHorizontalHeaderLabels([
            'Kupac', 'Artikal', 'Rata', 'Dospijeće', 'Status', 'Iznos', 'Preostalo'
        ])
        self.installment_table.verticalHeader().setVisible(False)
        self.installment_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.installment_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.installment_table.setSelectionMode(QTableWidget.SingleSelection)
        self.installment_table.setShowGrid(False)
        self.installment_table.horizontalHeader().setStretchLastSection(True)
        self.installment_table.itemSelectionChanged.connect(self.populate_installment_details)
        left_layout.addWidget(self.installment_table, 1)

        self.selected_info = QLabel('Odabrana rata: ništa nije odabrano')
        self.selected_info.setStyleSheet('color: #374151; font-weight: 600;')
        self.selected_info.setWordWrap(True)
        left_layout.addWidget(self.selected_info)

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(12)
        form_grid.setVerticalSpacing(10)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMinimum(0.01)
        self.amount_input.setMaximum(9999999.99)
        self.amount_input.setSuffix(' KM')

        self.payment_date_input = QDateEdit()
        self.payment_date_input.setCalendarPopup(True)
        self.payment_date_input.setDate(QDate.currentDate())
        self.payment_date_input.setDisplayFormat('dd.MM.yyyy')

        self.note_input = QTextEdit()
        self.note_input.setMinimumHeight(80)

        form_grid.addWidget(QLabel('Iznos uplate'), 0, 0)
        form_grid.addWidget(self.amount_input, 0, 1)
        form_grid.addWidget(QLabel('Datum uplate'), 1, 0)
        form_grid.addWidget(self.payment_date_input, 1, 1)
        form_grid.addWidget(QLabel('Napomena'), 2, 0)
        form_grid.addWidget(self.note_input, 2, 1)
        left_layout.addLayout(form_grid)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton('Evidentiraj uplatu')
        self.save_btn.setProperty('primary', True)
        self.save_btn.clicked.connect(self.save_payment)

        self.new_btn = QPushButton('Očisti formu')
        self.new_btn.setProperty('secondary', True)
        self.new_btn.clicked.connect(self.clear_payment_form)

        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.new_btn)
        left_layout.addLayout(button_row)

        right_card = QFrame()
        right_card.setProperty('card', True)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        header_row = QHBoxLayout()
        right_title = QLabel('Uplate — pregled')
        right_title.setProperty('sectionTitle', True)
        header_row.addWidget(right_title)
        header_row.addStretch(1)

        self.payment_search = QLineEdit()
        self.payment_search.setPlaceholderText('Pretraga uplata po kupcu, artiklu, kampanji...')
        self.payment_search.textChanged.connect(self.load_payments)
        self.payment_search.setMaximumWidth(320)
        header_row.addWidget(self.payment_search)
        right_layout.addLayout(header_row)

        self.payments_table = QTableWidget(0, 7)
        self.payments_table.setHorizontalHeaderLabels([
            'Datum', 'Kupac', 'Artikal', 'Kampanja', 'Rata', 'Iznos', 'Napomena'
        ])
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.payments_table.setSelectionMode(QTableWidget.SingleSelection)
        self.payments_table.setShowGrid(False)
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        self.payments_table.itemSelectionChanged.connect(self.capture_payment_selection)
        right_layout.addWidget(self.payments_table, 1)

        action_row = QHBoxLayout()
        self.refresh_btn = QPushButton('Osvježi pregled')
        self.refresh_btn.setProperty('secondary', True)
        self.refresh_btn.clicked.connect(self.refresh_all)

        self.delete_btn = QPushButton('Obriši odabranu uplatu')
        self.delete_btn.setProperty('secondary', True)
        self.delete_btn.clicked.connect(self.delete_payment)

        action_row.addWidget(self.refresh_btn)
        action_row.addWidget(self.delete_btn)
        right_layout.addLayout(action_row)

        root.addWidget(left_card, 5)
        root.addWidget(right_card, 4)

        self.refresh_all()

    def on_activate(self) -> None:
        self.refresh_all()

    def refresh_all(self) -> None:
        self.load_installments()
        self.load_payments()

    def load_installments(self) -> None:
        rows = PaymentService.build_installment_lookup(self.installment_search.text(), only_open=True)
        self.installment_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.customer_name,
                row.product_name,
                f'{row.installment_number}/{row.installments_count}',
                row.due_date.strftime('%d.%m.%Y'),
                self.translate_status(row.status),
                f'{row.amount:.2f} KM',
                f'{row.remaining_amount:.2f} KM',
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row.installment_id)
                if column_index in (5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.installment_table.setItem(row_index, column_index, item)
        self.installment_table.resizeColumnsToContents()

    def populate_installment_details(self) -> None:
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
        remaining = Decimal(str(installment.remaining_amount))
        self.amount_input.setValue(float(remaining))
        self.selected_info.setText(
            f'Odabrana rata: {order.customer.full_name} — {order.product_name_snapshot} — '
            f'rata {installment.installment_number}/{order.installments_count} — '
            f'preostalo {remaining:.2f} KM'
        )

    def save_payment(self) -> None:
        if self.selected_installment_id is None:
            QMessageBox.information(self, 'Uplate', 'Prvo odaberi ratu iz lijevog pregleda.')
            return
        try:
            PaymentService.create_payment(
                installment_id=self.selected_installment_id,
                amount=self.amount_input.value(),
                payment_date=self.payment_date_input.date().toPython(),
                note=self.note_input.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Greška', str(exc))
            return

        self.clear_payment_form()
        self.refresh_all()

    def clear_payment_form(self) -> None:
        self.selected_installment_id = None
        self.selected_info.setText('Odabrana rata: ništa nije odabrano')
        self.amount_input.setValue(0.01)
        self.payment_date_input.setDate(QDate.currentDate())
        self.note_input.clear()
        self.installment_table.clearSelection()

    def load_payments(self) -> None:
        payments = PaymentService.list_payments(self.payment_search.text())
        self.payments_table.setRowCount(len(payments))
        for row_index, payment in enumerate(payments):
            installment = payment.installment
            order = installment.order
            values = [
                payment.payment_date.strftime('%d.%m.%Y'),
                order.customer.full_name,
                order.product_name_snapshot,
                order.campaign.name,
                f'{installment.installment_number}/{order.installments_count}',
                f'{Decimal(str(payment.amount)):.2f} KM',
                payment.note or '',
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, payment.id)
                if column_index == 5:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.payments_table.setItem(row_index, column_index, item)
        self.payments_table.resizeColumnsToContents()

    def capture_payment_selection(self) -> None:
        row = self.payments_table.currentRow()
        if row < 0:
            self.selected_payment_id = None
            return
        item = self.payments_table.item(row, 0)
        self.selected_payment_id = item.data(Qt.UserRole) if item else None

    def delete_payment(self) -> None:
        if self.selected_payment_id is None:
            QMessageBox.information(self, 'Brisanje', 'Prvo odaberi uplatu iz desne tabele.')
            return
        reply = QMessageBox.question(
            self,
            'Potvrda',
            'Da li sigurno želiš obrisati odabranu uplatu?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            PaymentService.delete_payment(int(self.selected_payment_id))
        except Exception as exc:
            QMessageBox.warning(self, 'Greška', str(exc))
            return
        self.selected_payment_id = None
        self.refresh_all()

    @staticmethod
    def translate_status(status: str) -> str:
        mapping = {
            'pending': 'Na čekanju',
            'partially_paid': 'Djelimično plaćeno',
            'paid': 'Plaćeno',
            'overdue': 'Kasni',
            'cancelled': 'Otkazano',
        }
        return mapping.get(status, status)
