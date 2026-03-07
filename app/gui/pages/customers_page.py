from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
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

from app.gui.table_helpers import style_table, show_empty_state
from app.services.customer_service import CustomerService


class CustomersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.selected_customer_id: int | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        form_card = QFrame()
        form_card.setProperty("card", True)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(12)

        form_title = QLabel("Kupci — unos / izmjena")
        form_title.setProperty("sectionTitle", True)
        form_layout.addWidget(form_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.full_name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.city_input = QLineEdit()
        self.address_input = QLineEdit()
        self.note_input = QTextEdit()
        self.note_input.setMinimumHeight(110)

        fields = [
            ("Ime i prezime", self.full_name_input),
            ("Telefon", self.phone_input),
            ("Mjesto", self.city_input),
            ("Adresa", self.address_input),
            ("Napomena", self.note_input),
        ]
        for i, (label_text, widget) in enumerate(fields):
            label = QLabel(label_text)
            grid.addWidget(label, i, 0)
            grid.addWidget(widget, i, 1)

        form_layout.addLayout(grid)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton("Sačuvaj")
        self.save_btn.setProperty("primary", True)
        self.save_btn.setToolTip("Spremi izmjene u bazu podataka")
        self.save_btn.clicked.connect(self.save_customer)

        self.new_btn = QPushButton("Novi unos")
        self.new_btn.setProperty("secondary", True)
        self.new_btn.setToolTip("Očisti formu za unos novog kupca (Ctrl+N)")
        self.new_btn.clicked.connect(self.clear_form)

        self.delete_btn = QPushButton("Obriši")
        self.delete_btn.setProperty("secondary", True)
        self.delete_btn.setToolTip("Trajno ukloni odabranog kupca (ne može se poništiti)")
        self.delete_btn.clicked.connect(self.delete_customer)

        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.new_btn)
        button_row.addWidget(self.delete_btn)
        form_layout.addLayout(button_row)
        form_layout.addStretch(1)

        table_card = QFrame()
        table_card.setProperty("card", True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(12)

        header_row = QHBoxLayout()
        table_title = QLabel("Kupci — pregled")
        table_title.setProperty("sectionTitle", True)
        header_row.addWidget(table_title)
        header_row.addStretch(1)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Pretraži po imenu, telefonu ili gradu...")
        self.search_input.textChanged.connect(self.load_customers)
        self.search_input.setMaximumWidth(320)
        header_row.addWidget(self.search_input)
        
        # Ctrl+N prečica za novi unos
        shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        shortcut.activated.connect(self.clear_form)
        table_layout.addLayout(header_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Kupac", "Telefon", "Mjesto", "Adresa"])
        style_table(self.table)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.populate_form_from_selection)
        table_layout.addWidget(self.table)

        root.addWidget(form_card, 1)
        root.addWidget(table_card, 2)

        self.load_customers()

    def on_activate(self) -> None:
        self.load_customers()

    def load_customers(self) -> None:
        customers = CustomerService.list_customers(self.search_input.text())

        # Prazan state
        if not customers:
            show_empty_state(self.table, "Nema kupaca za prikaz")
            return

        self.table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            values = [
                customer.full_name,
                customer.phone or "",
                customer.city or "",
                customer.address or "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, customer.id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def populate_form_from_selection(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        customer_id_item = self.table.item(row, 0)
        if customer_id_item is None:
            return
        customer_id = customer_id_item.data(Qt.UserRole)
        customers = CustomerService.list_customers(self.search_input.text())
        selected = next((c for c in customers if c.id == customer_id), None)
        if selected is None:
            return
        self.selected_customer_id = selected.id
        self.full_name_input.setText(selected.full_name)
        self.phone_input.setText(selected.phone or "")
        self.city_input.setText(selected.city or "")
        self.address_input.setText(selected.address or "")
        self.note_input.setPlainText(selected.note or "")

    def save_customer(self) -> None:
        try:
            payload = dict(
                full_name=self.full_name_input.text(),
                phone=self.phone_input.text(),
                city=self.city_input.text(),
                address=self.address_input.text(),
                note=self.note_input.toPlainText(),
            )
            if self.selected_customer_id is None:
                CustomerService.create_customer(**payload)
            else:
                CustomerService.update_customer(self.selected_customer_id, **payload)
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))
            return

        self.clear_form()
        self.load_customers()

    def delete_customer(self) -> None:
        if self.selected_customer_id is None:
            QMessageBox.information(self, "Brisanje", "Prvo odaberi kupca iz tabele.")
            return
        
        # Dohvati ime kupca za poruku
        customer_name = self.full_name_input.text() or "odabranog kupca"
        
        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            f"Da li sigurno želiš obrisati kupca '{customer_name}'?\n\nOva radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # default = No (sigurniji)
        )
        if reply != QMessageBox.Yes:
            return
        try:
            CustomerService.delete_customer(self.selected_customer_id)
        except Exception as exc:
            QMessageBox.warning(self, "Greška", str(exc))
            return
        self.clear_form()
        self.load_customers()

    def clear_form(self) -> None:
        self.selected_customer_id = None
        self.full_name_input.clear()
        self.phone_input.clear()
        self.city_input.clear()
        self.address_input.clear()
        self.note_input.clear()
        self.table.clearSelection()
