from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, create_numeric_item
from app.services.campaign_service import CampaignService
from app.services.order_service import OrderService
from app.gui.icons import create_icon_label, get_pixmap


class OrdersPage(QWidget):
    """Stranica za upravljanje narudžbama."""

    # Signal za navigaciju (koristi se iz Dashboard-a)
    navigate_to = Signal(str)

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

        # --- Gornji dio: Forma za unos (Card Layout) ---
        form_card = self._create_order_form_card()
        splitter.addWidget(form_card)

        # --- Donji dio: Tabela narudžbi ---
        table_group = self._create_table_group()
        splitter.addWidget(table_group)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _create_order_form_card(self) -> QFrame:
        """Kreira card sa formom za unos narudžbe."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 1. Title
        title_layout = QHBoxLayout()
        cart_icon = create_icon_label("cart", "#1f2937", 22)
        title_layout.addWidget(cart_icon)
        title = QLabel("Nova narudžba")
        title.setProperty("sectionTitle", True)
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        layout.addLayout(title_layout)

        # 2. Fields (Grid Layout)
        fields_widget = QWidget()
        fields_layout = QGridLayout(fields_widget)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setHorizontalSpacing(16)
        fields_layout.setVerticalSpacing(14)

        # Red 0: Kampanja i Kupac
        fields_layout.addWidget(QLabel("Kampanja:"), 0, 0)
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(200)
        self.campaign_combo.setToolTip("Odaberite kampanju iz koje će se učitati proizvodi")
        fields_layout.addWidget(self.campaign_combo, 0, 1)

        fields_layout.addWidget(QLabel("Kupac:"), 0, 2)
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(200)
        self.customer_combo.setToolTip("Odaberite kupca iz baze")
        fields_layout.addWidget(self.customer_combo, 0, 3)

        # Red 1: Proizvod i Cijena
        fields_layout.addWidget(QLabel("Proizvod:"), 1, 0)
        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.setInsertPolicy(QComboBox.NoInsert)
        self.product_combo.lineEdit().setPlaceholderText("Odaberite iz kampanje ili upišite naziv...")
        self.product_combo.setMinimumWidth(200)
        self.product_combo.setToolTip("Odaberite proizvod iz kampanje ili upišite novi naziv")
        fields_layout.addWidget(self.product_combo, 1, 1)

        fields_layout.addWidget(QLabel("Cijena (KM):"), 1, 2)
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("npr. 199.99")
        self.price_input.setToolTip("Unesite cijenu proizvoda")
        fields_layout.addWidget(self.price_input, 1, 3)

        # Red 2: Broj rata
        fields_layout.addWidget(QLabel("Broj rata:"), 2, 0)
        self.installments_combo = QComboBox()
        self.installments_combo.addItems([f"{i} rata" for i in range(1, 11)])
        self.installments_combo.setCurrentIndex(0)  # Default: 1 rata
        self.installments_combo.setMinimumWidth(200)
        self.installments_combo.setToolTip("Odaberite broj rata (1-10)")
        self.installments_combo.currentIndexChanged.connect(self._update_preview)
        fields_layout.addWidget(self.installments_combo, 2, 1)

        # Red 3: Broj ugovora (opciono)
        fields_layout.addWidget(QLabel("Broj ugovora:"), 2, 2)
        self.contract_number_input = QLineEdit()
        self.contract_number_input.setPlaceholderText("npr. 4-1-11-2-1-3 (opciono)")
        self.contract_number_input.setMinimumWidth(200)
        self.contract_number_input.setToolTip(
            "Broj ugovora sa kupcem — opciono polje, ali važno za praćenje"
        )
        fields_layout.addWidget(self.contract_number_input, 2, 3)

        # Spacer
        fields_layout.setColumnStretch(2, 1)
        fields_layout.setColumnStretch(3, 1)

        layout.addWidget(fields_widget)

        # 3. Preview sekcija
        preview_group = QGroupBox("Preview narudžbe")
        preview_group.setStyleSheet("""
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
        preview_layout = QHBoxLayout(preview_group)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(32)

        # Dodaj ikonicu
        chart_icon = create_icon_label("chart", "#059669", 20)
        preview_layout.insertWidget(0, chart_icon)

        self.preview_total_label = QLabel("Ukupno: 0.00 KM")
        self.preview_total_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #111827;")
        preview_layout.addWidget(self.preview_total_label)

        self.preview_installment_label = QLabel("1 rata → 0.00 KM")
        self.preview_installment_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #111827;")
        preview_layout.addWidget(self.preview_installment_label)

        preview_layout.addStretch(1)
        layout.addWidget(preview_group)

        # 4. Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.save_btn = QPushButton("Sačuvaj narudžbu")
        self.save_btn.setProperty("primary", True)
        self.save_btn.setMinimumHeight(44)
        self.save_btn.setToolTip("Kreiraj narudžbu sa automatski generisanim ratama")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:pressed {
                background-color: #065f46;
            }
        """)
        save_pixmap = get_pixmap("save", "#ffffff", 18)
        self.save_btn.setIcon(save_pixmap)
        button_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Očisti formu")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.setMinimumHeight(44)
        self.clear_btn.setToolTip("Očisti sva polja za novi unos")
        clear_pixmap = get_pixmap("refresh", "#374151", 18)
        self.clear_btn.setIcon(clear_pixmap)
        button_layout.addWidget(self.clear_btn)

        self.delete_btn = QPushButton("Obriši narudžbu")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:pressed {
                background-color: #991b1b;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #d1d5db;
            }
        """)
        self.delete_btn.setToolTip("Obriši odabranu narudžbu iz tabele")
        self.delete_btn.setEnabled(False)
        delete_pixmap = get_pixmap("delete", "#ffffff", 18)
        self.delete_btn.setIcon(delete_pixmap)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch(1)
        layout.addLayout(button_layout)

        # 5. Poruka o uspjehu/grešci
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("padding: 10px; border-radius: 6px; font-size: 13px;")
        self.message_label.hide()
        layout.addWidget(self.message_label)

        return card

    def _create_table_group(self) -> QGroupBox:
        """Kreira grupu sa tabelom narudžbi."""
        group = QGroupBox("Postojeće narudžbe")
        layout = QVBoxLayout(group)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Br. ugovora", "Kupac", "Proizvod", "Cijena", "Rate", "Datum", "Status"
        ])

        # Konfiguracija tabele
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Br. ugovora
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # type: ignore[arg-type]  # Kupac
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # type: ignore[arg-type]  # Proizvod
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Cijena
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Rate
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Datum
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # type: ignore[arg-type]  # Status

        style_table(self.table)

        # Dvostruki klik za detalje
        self.table.doubleClicked.connect(self._show_order_details)

        layout.addWidget(self.table)

        # Refresh dugme
        refresh_btn = QPushButton("Osvježi")
        refresh_btn.setProperty("secondary", True)
        refresh_pixmap = get_pixmap("refresh", "#374151", 18)
        refresh_btn.setIcon(refresh_pixmap)
        refresh_btn.clicked.connect(self._load_orders)
        layout.addWidget(refresh_btn)

        return group

    def _connect_signals(self) -> None:
        """Povezuje signale sa slotovima."""
        self.save_btn.clicked.connect(self.save_order)
        self.clear_btn.clicked.connect(self.clear_form)
        self.delete_btn.clicked.connect(self.delete_selected_order)
        self.table.itemSelectionChanged.connect(self._on_order_selected)
        self.campaign_combo.currentIndexChanged.connect(self._on_campaign_changed)
        self.campaign_combo.currentIndexChanged.connect(self._check_campaign_warning)
        self.product_combo.activated.connect(self._on_product_activated)

        # Preview update
        self.price_input.textChanged.connect(self._update_preview)
        self.installments_combo.currentIndexChanged.connect(self._update_preview)

    def _load_campaigns_for_combo(self) -> None:
        """Učitava kampanje u dropdown i automatski bira aktivnu."""
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
        self._update_preview()

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
        self._check_campaign_warning()

    def _check_campaign_warning(self) -> None:
        """Provjerava i ažurira warning poruku o kampanji."""
        # Sakrij warning ako je odabrana kampanja (nije "— Odaberite kampanju —")
        selected_index = self.campaign_combo.currentIndex()
        if selected_index > 0:  # Prva stavka je "— Odaberite kampanju —"
            self.campaign_warning.hide()
        else:
            # Prikaži warning samo ako nema aktivne kampanje
            if self.order_service.has_active_campaign():
                self.campaign_warning.hide()
            else:
                self.campaign_warning.show()

    def _load_orders(self) -> None:
        """Učitava narudžbe u tabelu."""
        orders = self.order_service.list_orders()

        if not orders:
            self.table.setRowCount(1)
            placeholder = QTableWidgetItem("Nema narudžbi za prikaz")
            placeholder.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            placeholder.setForeground(QColor("#9ca3af"))
            placeholder.setFlags(Qt.ItemIsEnabled)  # type: ignore[arg-type]
            self.table.setItem(0, 0, placeholder)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(orders))

        for row, order in enumerate(orders):
            # ID (col 0)
            id_item = QTableWidgetItem(str(order.id))
            id_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 0, id_item)

            # Br. ugovora (col 1) — NOVO
            contract = order.contract_number or "—"
            contract_item = QTableWidgetItem(contract)
            contract_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            if order.contract_number:
                contract_item.setForeground(QColor("#1d4ed8"))  # Plava ako postoji
            self.table.setItem(row, 1, contract_item)

            # Kupac (col 2)
            customer_name = order.customer.full_name if order.customer else "N/A"
            self.table.setItem(row, 2, QTableWidgetItem(customer_name))

            # Proizvod (col 3)
            self.table.setItem(row, 3, QTableWidgetItem(order.product_name_snapshot))

            # Cijena (col 4)
            self.table.setItem(row, 4, create_numeric_item(order.total_price_snapshot, " KM"))

            # Broj rata (col 5)
            installments_item = QTableWidgetItem(f"{order.installments_count}")
            installments_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 5, installments_item)

            # Datum (col 6)
            date_item = QTableWidgetItem(order.order_date.strftime("%d.%m.%Y"))
            date_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            self.table.setItem(row, 6, date_item)

            # Status (col 7)
            status_text = order.status.value.upper()
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            if order.status.value == "active":
                status_item.setForeground(QColor("#059669"))
            elif order.status.value == "completed":
                status_item.setForeground(QColor("#6b7280"))
            elif order.status.value == "cancelled":
                status_item.setForeground(QColor("#dc2626"))
            self.table.setItem(row, 7, status_item)

        # Auto-resize kolona
        self.table.resizeColumnsToContents()

    def _update_preview(self) -> None:
        """Ažurira preview sekciju sa ukupnim iznosom i iznosom rate."""
        try:
            price_text = self.price_input.text().replace(",", ".").strip()
            if not price_text:
                price = Decimal("0.00")
            else:
                price = Decimal(price_text)
        except Exception:
            price = Decimal("0.00")

        # Broj rata iz combo-a (indeks + 1 jer je 0 = 1 rata)
        installments = self.installments_combo.currentIndex() + 1

        # Iznos rate (zaokruženo na 2 decimale)
        installment_amount = (price / installments).quantize(Decimal("0.01"))

        # Ažuriraj label-e
        self.preview_total_label.setText(f"Ukupno: {price:.2f} KM")
        self.preview_installment_label.setText(f"{installments} rata → {installment_amount:.2f} KM")

    def save_order(self) -> None:
        """Čuva novu narudžbu."""
        # Validacija prije slanja
        validation_error = self._validate_form()
        if validation_error:
            self._show_message(validation_error, error=True)
            return

        customer_id = self.customer_combo.currentData()
        campaign_id = self.campaign_combo.currentData()

        # Stvarni naziv: iz userData ako je odabran iz dropdown-a, inače ono što je upisano
        current_index = self.product_combo.currentIndex()
        product_name = (
            self.product_combo.itemData(current_index)
            or self.product_combo.currentText()
        ).strip()

        price = self.price_input.text()
        installments = self.installments_combo.currentIndex() + 1

        try:
            order = self.order_service.create_order(
                customer_id=customer_id,
                product_name=product_name,
                price=price,
                installments=installments,
                campaign_id=campaign_id,
                contract_number=self.contract_number_input.text().strip() or None,
            )

            self._show_message(
                f"✅ Narudžba #{order.id} uspješno sačuvana! "
                f"Generisano {installments} rata.",
                error=False
            )

            # Očisti unos proizvoda i cijene
            self.product_combo.setCurrentIndex(-1)
            self.product_combo.clearEditText()
            self.price_input.clear()
            self.installments_combo.setCurrentIndex(0)  # Reset na 1 ratu
            self._update_preview()

            self._load_orders()

        except ValueError as e:
            self._show_message(str(e), error=True)
        except Exception as e:
            self._show_message(f"Greška pri čuvanju: {str(e)}", error=True)

    def _validate_form(self) -> Optional[str]:
        """
        Validira formu prije slanja.
        Vraća error poruku ili None ako je sve OK.
        """
        # Kupac
        customer_id = self.customer_combo.currentData()
        if not customer_id:
            return "Obavezno odabrati kupca."

        # Proizvod
        current_index = self.product_combo.currentIndex()
        product_name = (
            self.product_combo.itemData(current_index)
            or self.product_combo.currentText()
        ).strip()
        if not product_name:
            return "Obavezno unijeti naziv proizvoda."

        # Cijena
        price_text = self.price_input.text().replace(",", ".").strip()
        if not price_text:
            return "Obavezno unijeti cijenu."
        
        try:
            price = Decimal(price_text)
            if price <= 0:
                return "Cijena mora biti veća od 0."
        except Exception:
            return "Neispravna cijena."

        # Broj rata
        installments = self.installments_combo.currentIndex() + 1
        if installments < 1 or installments > 10:
            return "Broj rata mora biti između 1 i 10."

        return None

    def clear_form(self) -> None:
        """Čisti formu za novi unos."""
        self.product_combo.setCurrentIndex(-1)
        self.product_combo.clearEditText()
        self.price_input.clear()
        self.installments_combo.setCurrentIndex(0)  # Reset na 1 ratu
        self.contract_number_input.clear()
        self._update_preview()
        self.message_label.hide()

    def _on_order_selected(self) -> None:
        """Poziva se kad se odabere red u tabeli narudžbi."""
        row = self.table.currentRow()
        # Omogući dugme za brisanje samo ako je red odabran
        self.delete_btn.setEnabled(row >= 0)

    def delete_selected_order(self) -> None:
        """Briše odabranu narudžbu nakon potvrde."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Upozorenje", "Odaberite narudžbu za brisanje.")
            return

        # Dohvati ID narudžbe
        id_item = self.table.item(row, 0)
        if not id_item:
            return

        try:
            order_id = int(id_item.text())
        except ValueError:
            return

        # Dohvati detalje narudžbe za prikaz u potvrdi
        order = self.order_service.get_order_details(order_id)
        if not order:
            QMessageBox.warning(self, "Greška", "Narudžba nije pronađena.")
            return

        # Potvrdni dijalog
        confirm = QMessageBox.question(
            self,
            "Potvrdi brisanje",
            f"Da li ste sigurni da želite obrisati narudžbu #{order.id}?\n\n"
            f"Kupac: {order.customer.full_name if order.customer else 'N/A'}\n"
            f"Proizvod: {order.product_name_snapshot}\n"
            f"Ukupno: {order.total_price_snapshot:.2f} KM\n"
            f"Rate: {order.installments_count}\n\n"
            "Ova akcija će obrisati narudžbu i sve pripadajuće rate i uplate.\n"
            "Ova akcija se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        # Briši narudžbu
        try:
            self.order_service.delete_order(order_id)
            self._show_message(f"✅ Narudžba #{order_id} uspješno obrisana.", error=False)
            self._load_orders()
            self.delete_btn.setEnabled(False)
        except ValueError as e:
            self._show_message(str(e), error=True)
        except Exception as e:
            self._show_message(f"Greška pri brisanju: {str(e)}", error=True)

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
                    border-radius: 6px;
                    padding: 10px;
                }
            """)
        else:
            self.message_label.setStyleSheet("""
                QLabel {
                    background-color: #f0fdf4;
                    color: #059669;
                    border: 1px solid #86efac;
                    border-radius: 6px;
                    padding: 10px;
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
        msg_box.setTextFormat(Qt.RichText)  # type: ignore[arg-type]
        msg_box.setText(details)
        msg_box.exec()

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira."""
        self._load_campaigns_for_combo()
        self._load_customers()
        self._load_orders()
