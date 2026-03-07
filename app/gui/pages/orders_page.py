from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QComboBox, QMessageBox, QHeaderView,
    QFrame, QSplitter, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.gui.table_helpers import style_table, create_numeric_item
from app.services.campaign_service import CampaignService
from app.services.order_service import OrderService


class OrdersPage(QWidget):
    """Stranica za upravljanje narudžbama."""

    def __init__(self):
        super().__init__()

        self.order_service = OrderService()
        self.campaign_service = CampaignService()
        # Mapa: display label -> CampaignPrice (za auto-fill cijene)
        self._product_price_map: dict = {}

        self._init_ui()
        self._connect_signals()
        self._load_campaigns_for_combo()
        self._load_customers()
        self._load_orders()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        # Warning banner (prikazuje se ako nema aktivne kampanje)
        self.campaign_warning = QLabel(
            "⚠  Nema aktivne kampanje. Narudžba će biti vezana za prvu dostupnu kampanju "
            "(draft/archived). Preporučuje se aktivirati kampanju prije unosa narudžbi."
        )
        self.campaign_warning.setWordWrap(True)
        self.campaign_warning.setStyleSheet("""
            QLabel {
                background-color: #fffbeb;
                color: #92400e;
                border: 1px solid #fcd34d;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 13px;
            }
        """)
        self.campaign_warning.hide()
        main_layout.addWidget(self.campaign_warning)

        # Splitter za formu i tabelu
        splitter = QSplitter(Qt.Vertical)

        # --- Gornji dio: Forma za unos ---
        form_group = self._create_form_group()
        splitter.addWidget(form_group)

        # --- Donji dio: Tabela narudžbi ---
        table_group = self._create_table_group()
        splitter.addWidget(table_group)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _create_form_group(self) -> QGroupBox:
        """Kreira grupu sa formom za unos narudžbe."""
        group = QGroupBox("Nova narudžba")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        # Kampanja (dropdown)
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(250)
        layout.addRow("Kampanja:", self.campaign_combo)

        # Kupac (dropdown)
        self.customer_combo = QComboBox()
        self.customer_combo.setPlaceholderText("Odaberite kupca...")
        self.customer_combo.setMinimumWidth(250)
        layout.addRow("Kupac:", self.customer_combo)

        # Proizvod — editable combo (bira iz kampanje ili upisuje ručno)
        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.setInsertPolicy(QComboBox.NoInsert)
        self.product_combo.lineEdit().setPlaceholderText(
            "Odaberite iz kampanje ili upišite naziv..."
        )
        self.product_combo.setMinimumWidth(250)
        layout.addRow("Proizvod:", self.product_combo)

        # Cijena (auto-fill iz kampanje, ili ručni unos)
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("npr. 199.99")
        layout.addRow("Cijena (KM):", self.price_input)

        # Broj rata
        self.installments_input = QSpinBox()
        self.installments_input.setRange(1, 10)
        self.installments_input.setValue(1)
        self.installments_input.setSuffix(" rata")
        layout.addRow("Broj rata:", self.installments_input)

        # Dugme za čuvanje
        self.save_btn = QPushButton("Sačuvaj narudžbu")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
        """)
        layout.addRow("", self.save_btn)

        # Poruka o uspjehu/grešci
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("padding: 8px; border-radius: 4px;")
        self.message_label.hide()
        layout.addRow("", self.message_label)

        return group

    def _create_table_group(self) -> QGroupBox:
        """Kreira grupu sa tabelom narudžbi."""
        group = QGroupBox("Postojeće narudžbe")
        layout = QVBoxLayout(group)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Kupac", "Proizvod", "Cijena", "Rate", "Datum", "Status"
        ])

        # Konfiguracija tabele
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Kupac
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Proizvod
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Cijena
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Rate
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Datum
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Status

        style_table(self.table)

        # Dvostruki klik za detalje
        self.table.doubleClicked.connect(self._show_order_details)

        layout.addWidget(self.table)

        # Refresh dugme
        refresh_btn = QPushButton("Osvježi")
        refresh_btn.clicked.connect(self._load_orders)
        layout.addWidget(refresh_btn)

        return group

    def _connect_signals(self) -> None:
        """Povezuje signale sa slotovima."""
        self.save_btn.clicked.connect(self.save_order)
        self.campaign_combo.currentIndexChanged.connect(self._on_campaign_changed)
        self.product_combo.activated.connect(self._on_product_activated)

    def _load_campaigns_for_combo(self) -> None:
        """Učitava kampanje u dropdown i automatski bira aktivnu."""
        # Privremeno blokiraj signal da ne okine _on_campaign_changed za svaki add
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaign_combo.addItem("— Odaberite kampanju —", userData=None)

        campaigns = self.campaign_service.list_campaigns()
        active_index = 0
        for i, campaign in enumerate(campaigns, start=1):
            status = campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status)
            label = f"{campaign.name}  [{status}]"
            self.campaign_combo.addItem(label, userData=campaign.id)
            if status == "active" and active_index == 0:
                active_index = i

        self.campaign_combo.blockSignals(False)
        self.campaign_combo.setCurrentIndex(active_index)
        # Ručno okini da se učitaju proizvodi za odabranu kampanju
        self._on_campaign_changed(active_index)

    def _on_campaign_changed(self, index: int) -> None:
        """Učitava proizvode iz odabrane kampanje u product_combo."""
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self._product_price_map = {}
        self.product_combo.blockSignals(False)

        campaign_id = self.campaign_combo.currentData()
        if not campaign_id:
            return

        prices = self.campaign_service.list_campaign_products(campaign_id)
        for cp in prices:
            if not cp.product:
                continue
            name = cp.product.name or ""
            brand = cp.product.brand or ""
            label = f"{brand} — {name}" if brand else name
            self.product_combo.addItem(label, userData=name)
            self._product_price_map[label] = cp

    def _on_product_activated(self, index: int) -> None:
        """Auto-fill cijene kad korisnik odabere proizvod iz dropdown-a."""
        label = self.product_combo.itemText(index)
        cp = self._product_price_map.get(label)
        if cp is None:
            return
        # Prefer akcijsku cijenu ako postoji
        price = cp.discount_price if cp.discount_price else cp.regular_price
        self.price_input.setText(str(price))

    def _load_customers(self) -> None:
        """Učitava kupce u dropdown."""
        self.customer_combo.clear()
        self.customer_combo.addItem("Odaberite kupca...", userData=None)

        customers = self.order_service.list_customers()
        for customer in customers:
            self.customer_combo.addItem(
                f"{customer.full_name} ({customer.city or 'N/A'})",
                userData=customer.id
            )

        # Prikaži warning ako nema aktivne kampanje
        if self.order_service.has_active_campaign():
            self.campaign_warning.hide()
        else:
            self.campaign_warning.show()

    def _load_orders(self) -> None:
        """Učitava narudžbe u tabelu."""
        orders = self.order_service.list_orders()

        self.table.setRowCount(0)
        self.table.setRowCount(len(orders))

        for row, order in enumerate(orders):
            # ID
            id_item = QTableWidgetItem(str(order.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, id_item)

            # Kupac
            customer_name = order.customer.full_name if order.customer else "N/A"
            self.table.setItem(row, 1, QTableWidgetItem(customer_name))

            # Proizvod
            self.table.setItem(row, 2, QTableWidgetItem(order.product_name_snapshot))

            # Cijena
            self.table.setItem(row, 3, create_numeric_item(order.total_price_snapshot, " KM"))

            # Broj rata
            installments_item = QTableWidgetItem(f"{order.installments_count}")
            installments_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, installments_item)

            # Datum
            date_item = QTableWidgetItem(order.order_date.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, date_item)

            # Status
            status_text = order.status.value.upper()
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            if order.status.value == "active":
                status_item.setForeground(QColor("#059669"))
            elif order.status.value == "completed":
                status_item.setForeground(QColor("#6b7280"))
            elif order.status.value == "cancelled":
                status_item.setForeground(QColor("#dc2626"))
            self.table.setItem(row, 6, status_item)

        # Auto-resize kolona
        self.table.resizeColumnsToContents()

    def save_order(self) -> None:
        """Čuva novu narudžbu."""
        customer_id = self.customer_combo.currentData()
        campaign_id = self.campaign_combo.currentData()

        # Stvarni naziv: iz userData ako je odabran iz dropdown-a, inače ono što je upisano
        current_index = self.product_combo.currentIndex()
        product_name = (
            self.product_combo.itemData(current_index)
            or self.product_combo.currentText()
        ).strip()

        price = self.price_input.text()
        installments = self.installments_input.value()

        # Validacija
        success, error = self.order_service.validate_order_input(
            customer_id, product_name, price, installments
        )
        if not success:
            self._show_message(error, error=True)
            return

        try:
            order = self.order_service.create_order(
                customer_id=customer_id,
                product_name=product_name,
                price=price,
                installments=installments,
                campaign_id=campaign_id,
            )

            self._show_message(
                f"Narudžba #{order.id} uspješno sačuvana! "
                f"Generisano {installments} rata.",
                error=False
            )

            # Očisti unos proizvoda i cijene
            self.product_combo.setCurrentIndex(-1)
            self.product_combo.clearEditText()
            self.price_input.clear()
            self.installments_input.setValue(1)

            self._load_orders()

        except ValueError as e:
            self._show_message(str(e), error=True)
        except Exception as e:
            self._show_message(f"Greška pri čuvanju: {str(e)}", error=True)

    def _show_message(self, message: str, error: bool = False) -> None:
        """Prikazuje poruku o uspjehu ili grešci."""
        self.message_label.setText(message)
        self.message_label.show()

        if error:
            self.message_label.setStyleSheet("""
                QLabel {
                    background-color: #fef2f2;
                    color: #dc2626;
                    border: 1px solid #fca5a5;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
        else:
            self.message_label.setStyleSheet("""
                QLabel {
                    background-color: #f0fdf4;
                    color: #059669;
                    border: 1px solid #86efac;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)

    def _show_order_details(self, index) -> None:
        """Prikazuje detalje narudžbe (dvostruki klik)."""
        row = index.row()
        order_id_item = self.table.item(row, 0)
        if not order_id_item:
            return

        try:
            order_id = int(order_id_item.text())
        except ValueError:
            return

        order = self.order_service.get_order_details(order_id)
        if not order:
            return

        # Prikaži detalje u messagebox-u
        details = f"""
        <h3>Narudžba #{order.id}</h3>
        <table>
            <tr><td><b>Kupac:</b></td><td>{order.customer.full_name}</td></tr>
            <tr><td><b>Proizvod:</b></td><td>{order.product_name_snapshot}</td></tr>
            <tr><td><b>Cijena:</b></td><td>{order.total_price_snapshot:.2f} KM</td></tr>
            <tr><td><b>Broj rata:</b></td><td>{order.installments_count}</td></tr>
            <tr><td><b>Datum:</b></td><td>{order.order_date.strftime('%d.%m.%Y')}</td></tr>
            <tr><td><b>Status:</b></td><td>{order.status.value.upper()}</td></tr>
        </table>
        
        <h4>Rate:</h4>
        <table border="1" cellpadding="4">
            <tr><th>Rata</th><th>Iznos</th><th>Dospijeće</th><th>Status</th></tr>
        """

        for inst in order.installments:
            details += f"""
                <tr>
                    <td>{inst.installment_number}</td>
                    <td>{inst.amount:.2f} KM</td>
                    <td>{inst.due_date.strftime('%d.%m.%Y')}</td>
                    <td>{inst.status.value}</td>
                </tr>
            """

        details += "</table>"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"Detalji narudžbe #{order.id}")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(details)
        msg_box.exec()

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_campaigns_for_combo()
        self._load_customers()
        self._load_orders()
