from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, show_empty_state
from app.services.campaign_service import CampaignService
from app.services.order_service import OrderService
from app.services.price_list_service import PriceListService

# ------------------------------------------------------------------
# Mape prijevoda — enum vrijednosti u bazi ostaju engleske,
# prikazujemo bosanske labele u UI-u
# ------------------------------------------------------------------
_CAMPAIGN_STATUS_BS = {
    "draft":    "nacrt",
    "active":   "aktivna",
    "archived": "arhivirana",
}
_ORDER_STATUS_BS = {
    "active":    "Aktivna",
    "completed": "Završena",
    "cancelled": "Otkazana",
}
_ORDER_STATUS_COLOR = {
    "active":    "#059669",
    "completed": "#6b7280",
    "cancelled": "#dc2626",
}
_INST_STATUS_BS = {
    "pending":   "Na čekanju",
    "paid":      "Plaćena",
    "overdue":   "Kasni",
    "cancelled": "Otkazana",
}

_SOURCE_CAMPAIGN  = "campaign"
_SOURCE_PRICELIST = "pricelist"


class OrdersPage(QWidget):
    """
    Stranica za upravljanje narudžbama — dva taba:
    - Tab 1: Nova narudžba (forma + artikli)
    - Tab 2: Pregled narudžbi (tabela + filteri + brisanje)
    """

    navigate_to = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._source: str = _SOURCE_CAMPAIGN
        self._all_prices: list = []
        self._all_orders: list = []
        self._selected_order_id: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #64748b;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                padding: 10px 28px;
                font-size: 13px;
                font-weight: 600;
                margin-right: 2px;
                border-radius: 6px 6px 0 0;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #111827;
                border-bottom: 2px solid #059669;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
                color: #374151;
            }
        """)

        self._tabs.addTab(self._build_new_order_tab(), "  ＋  Nova narudžba  ")
        self._tabs.addTab(self._build_orders_tab(), "  📋  Pregled narudžbi  ")

        root.addWidget(self._tabs, 1)

        self._connect_signals()
        self._load_source_combos()
        self._load_customers()
        self._load_orders()

    # ------------------------------------------------------------------
    # TAB 1: Nova narudžba
    # ------------------------------------------------------------------

    def _build_new_order_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Warning banner
        self.campaign_warning = QLabel(
            "⚠  Nema aktivne kampanje. Narudžba će biti vezana za prvu dostupnu kampanju "
            "(nacrt/arhivirana). Preporučuje se aktivirati kampanju prije unosa narudžbi."
        )
        self.campaign_warning.setWordWrap(True)
        self.campaign_warning.setStyleSheet("""
            QLabel {
                background-color: #fffbeb; color: #92400e;
                border: 1px solid #fcd34d; border-radius: 6px;
                padding: 10px 14px; font-size: 13px; margin: 8px;
            }
        """)
        self.campaign_warning.hide()
        layout.addWidget(self.campaign_warning)

        # Horizontalni splitter: forma | artikli
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.setHandleWidth(4)
        h_splitter.setStyleSheet("QSplitter::handle { background: #e5e7eb; }")
        h_splitter.addWidget(self._build_form_panel())
        h_splitter.addWidget(self._build_articles_panel())
        h_splitter.setSizes([400, 900])
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

        layout.addWidget(h_splitter, 1)
        return tab

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(480)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Nova narudžba")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        # Izvor artikala
        source_frame = QFrame()
        source_frame.setStyleSheet(
            "QFrame { background:#f8fafc; border:1px solid #e5e7eb; border-radius:6px; }"
        )
        sf_layout = QHBoxLayout(source_frame)
        sf_layout.setContentsMargins(12, 8, 12, 8)
        sf_lbl = QLabel("Naruči iz:")
        sf_lbl.setStyleSheet("font-weight:600; color:#374151; border:none;")
        self.radio_campaign  = QRadioButton("Pogodnosti")
        self.radio_pricelist = QRadioButton("Cjenovnika")
        self.radio_campaign.setChecked(True)
        self.radio_campaign.setStyleSheet("border:none;")
        self.radio_pricelist.setStyleSheet("border:none;")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self.radio_campaign,  0)
        self._radio_group.addButton(self.radio_pricelist, 1)
        sf_layout.addWidget(sf_lbl)
        sf_layout.addWidget(self.radio_campaign)
        sf_layout.addWidget(self.radio_pricelist)
        sf_layout.addStretch(1)
        layout.addWidget(source_frame)

        # Kupac
        layout.addWidget(QLabel("Kupac:"))
        self.customer_combo = QComboBox()
        layout.addWidget(self.customer_combo)

        # Artikal
        layout.addWidget(QLabel("Artikal:"))
        self.product_input = QLineEdit()
        self.product_input.setPlaceholderText("Klikni artikal iz liste desno ili upiši...")
        layout.addWidget(self.product_input)

        # Cijena
        layout.addWidget(QLabel("Cijena (KM):"))
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("npr. 199.99")
        layout.addWidget(self.price_input)

        # Broj rata
        layout.addWidget(QLabel("Broj rata:"))
        self.installments_combo = QComboBox()
        self.installments_combo.addItems([f"{i} rata" for i in range(1, 11)])
        self.installments_combo.setCurrentIndex(9)
        layout.addWidget(self.installments_combo)

        # Broj ugovora
        layout.addWidget(QLabel("Broj ugovora: (opciono)"))
        self.contract_number_input = QLineEdit()
        self.contract_number_input.setPlaceholderText("npr. 4-1-11-2-1-3-001")
        layout.addWidget(self.contract_number_input)

        # ---- Preview narudžbe ----
        preview_frame = QFrame()
        preview_frame.setMinimumHeight(90)
        preview_frame.setStyleSheet("""
            QFrame {
                background: #f0fdf4;
                border: 2px solid #059669;
                border-radius: 10px;
                margin-top: 4px;
            }
        """)
        pv = QVBoxLayout(preview_frame)
        pv.setContentsMargins(16, 12, 16, 12)
        pv.setSpacing(6)

        pv_title = QLabel("Pregled narudžbe")
        pv_title.setStyleSheet(
            "color:#059669; font-size:11px; font-weight:700; "
            "letter-spacing:0.05em; border:none; background:transparent;"
        )
        self.preview_total_label = QLabel("Ukupno: 0.00 KM")
        self.preview_total_label.setStyleSheet(
            "font-size:18px; font-weight:800; color:#111827; "
            "border:none; background:transparent;"
        )
        self.preview_installment_label = QLabel("10 × 0.00 KM po rati")
        self.preview_installment_label.setStyleSheet(
            "font-size:13px; color:#374151; border:none; background:transparent;"
        )

        pv.addWidget(pv_title)
        pv.addWidget(self.preview_total_label)
        pv.addWidget(self.preview_installment_label)
        layout.addWidget(preview_frame)

        layout.addStretch(1)

        # Dugmad
        self.save_btn = QPushButton("💾  Sačuvaj narudžbu")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background:#059669; color:white; border:none;
                border-radius:8px; font-weight:700; font-size:14px;
            }
            QPushButton:hover  { background:#047857; }
            QPushButton:pressed { background:#065f46; }
        """)
        layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Očisti formu")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.setMinimumHeight(36)
        layout.addWidget(self.clear_btn)

        # Poruka
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        return panel

    def _build_articles_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("card", True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Artikli")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title)

        hint = QLabel("Klikni na artikal → automatski popuni formu lijevo")
        hint.setStyleSheet("color:#6b7280; font-size:12px; font-style:italic;")
        layout.addWidget(hint)

        # Combo za izvor
        source_row = QHBoxLayout()
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(240)
        self.pricelist_combo = QComboBox()
        self.pricelist_combo.setMinimumWidth(240)
        self.pricelist_combo.hide()
        self.articles_count = QLabel("")
        self.articles_count.setStyleSheet("color:#9ca3af; font-size:12px;")
        source_row.addWidget(self.campaign_combo)
        source_row.addWidget(self.pricelist_combo)
        source_row.addStretch(1)
        source_row.addWidget(self.articles_count)
        layout.addLayout(source_row)

        # Pretraga
        self.articles_search = QLineEdit()
        self.articles_search.setPlaceholderText("🔍 Pretraži po nazivu, brendu ili šifri...")
        self.articles_search.textChanged.connect(self._filter_articles)
        layout.addWidget(self.articles_search)

        # Tabela artikala — 7 kolona (kao u Cjenovniku)
        self.articles_table = QTableWidget(0, 7)
        self.articles_table.setHorizontalHeaderLabels([
            "Rb.", "Firma", "Naziv artikla", "Šifra", "Cijena (KM)", "Bod", "Status"
        ])
        ah = self.articles_table.horizontalHeader()
        ah.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Rb.
        ah.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Firma
        ah.setSectionResizeMode(2, QHeaderView.Stretch)           # Naziv
        ah.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Šifra
        ah.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Cijena
        ah.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Bod
        ah.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Status
        self.articles_table.verticalHeader().setVisible(False)
        self.articles_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.articles_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.articles_table.setAlternatingRowColors(True)
        self.articles_table.setStyleSheet("""
            QTableWidget { font-size:13px; }
            QTableWidget::item { padding:6px 8px; }
            QTableWidget::item:selected { background:#dbeafe; color:#1d4ed8; }
        """)
        self.articles_table.itemClicked.connect(self._on_article_clicked)
        layout.addWidget(self.articles_table, 1)

        return panel

    # ------------------------------------------------------------------
    # TAB 2: Pregled narudžbi
    # ------------------------------------------------------------------

    def _build_orders_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setProperty("card", True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)

        # Filteri
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.orders_search = QLineEdit()
        self.orders_search.setPlaceholderText("🔍 Pretraži po kupcu, artiklu ili br. ugovora...")
        self.orders_search.setMinimumWidth(280)
        self.orders_search.textChanged.connect(self._filter_orders)

        self.orders_status_filter = QComboBox()
        self.orders_status_filter.setMinimumWidth(140)
        self.orders_status_filter.addItem("Svi statusi", userData=None)
        self.orders_status_filter.addItem("Aktivna",   userData="active")
        self.orders_status_filter.addItem("Završena",  userData="completed")
        self.orders_status_filter.addItem("Otkazana",  userData="cancelled")
        self.orders_status_filter.currentIndexChanged.connect(self._filter_orders)

        self.delete_btn = QPushButton("🗑  Obriši odabranu")
        self.delete_btn.setMinimumHeight(36)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background:#fee2e2; color:#dc2626;
                border:1px solid #fca5a5; border-radius:8px; font-weight:700;
                padding: 0 16px;
            }
            QPushButton:hover { background:#fecaca; }
            QPushButton:disabled {
                background:#f9fafb; color:#d1d5db; border-color:#e5e7eb;
            }
        """)
        self.delete_btn.clicked.connect(self._delete_selected_order)

        filter_row.addWidget(self.orders_search, 1)
        filter_row.addWidget(self.orders_status_filter)
        filter_row.addWidget(self.delete_btn)
        panel_layout.addLayout(filter_row)

        # Tabela narudžbi
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Br. ugovora", "Kupac", "Artikal",
            "Cijena (KM)", "Rate", "Datum", "Status"
        ])
        th = self.table.horizontalHeader()
        th.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(2, QHeaderView.Stretch)
        th.setSectionResizeMode(3, QHeaderView.Stretch)
        th.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        th.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        style_table(self.table)
        # Inline editovanje je onemogućeno — koristimo custom dialog za Br. ugovora
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                gridline-color: #eef2f7;
                font-size: 16px;
            }
            QTableWidget::item {
                padding: 8px;
                color: #1f2937;
                background-color: transparent;
            }
            QTableWidget::item:alternate {
                background-color: #f9fafb;
            }
            QTableWidget::item:hover {
                background-color: #f3f4f6;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
            }
            QLineEdit {
                font-size: 16px;
                padding: 4px 8px;
                border: 2px solid #2563eb;
                border-radius: 4px;
            }
        """)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_order_selected)
        panel_layout.addWidget(self.table, 1)

        layout.addWidget(panel, 1)
        return tab

    # ------------------------------------------------------------------
    # Signali
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.save_btn.clicked.connect(self._save_order)
        self.clear_btn.clicked.connect(self._clear_form)
        self._radio_group.buttonToggled.connect(self._on_source_changed)
        self.campaign_combo.currentIndexChanged.connect(self._on_campaign_combo_changed)
        self.pricelist_combo.currentIndexChanged.connect(self._on_pricelist_combo_changed)
        self.price_input.textChanged.connect(self._update_preview)
        self.installments_combo.currentIndexChanged.connect(self._update_preview)

    # ------------------------------------------------------------------
    # Ažuriranje broja ugovora iz tabele
    # ------------------------------------------------------------------

    def _on_contract_number_changed(self, row: int, col: int) -> None:
        """
        Poziva se kada se izmijeni broj ugovora u tabeli (kolona 1).
        Ažurira narudžbu u bazi sa novim brojem ugovora.
        """
        if col != 1:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        order_id = item.data(Qt.UserRole)
        if not order_id:
            return

        new_contract = self.table.item(row, 1).text().strip() or None

        try:
            OrderService.update_contract_number(order_id, new_contract)
            
            # Ažuriraj boju i font ako je unesen broj
            contract_item = self.table.item(row, 1)
            if new_contract:
                contract_item.setForeground(QColor("#1d4ed8"))
                f = QFont(); f.setBold(True); contract_item.setFont(f)
            else:
                contract_item.setForeground(QColor("#9ca3af"))
        except Exception as e:
            QMessageBox.warning(self, "Greška", f"Neuspješno ažuriranje broja ugovora:\n{str(e)}")
            # Vrati staru vrijednost
            order = OrderService.get_order_details(order_id)
            if order:
                self.table.blockSignals(True)
                self.table.item(row, 1).setText(order.contract_number or "")
                self.table.blockSignals(False)

    # ------------------------------------------------------------------
    # Učitavanje podataka
    # ------------------------------------------------------------------

    def _load_source_combos(self) -> None:
        # Kampanje — bosanski status label
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        campaigns = CampaignService.list_campaigns()
        active_index = 0
        for i, c in enumerate(campaigns):
            raw = c.status.value if hasattr(c.status, "value") else str(c.status)
            bs  = _CAMPAIGN_STATUS_BS.get(raw, raw)
            self.campaign_combo.addItem(f"{c.name}  [{bs}]", userData=c.id)
            if raw == "active" and active_index == 0:
                active_index = i
        self.campaign_combo.blockSignals(False)
        self.campaign_combo.setCurrentIndex(active_index)

        # Cjenovnici
        self.pricelist_combo.blockSignals(True)
        self.pricelist_combo.clear()
        for pl in PriceListService.list_all():
            self.pricelist_combo.addItem(pl.name, userData=pl.id)
        self.pricelist_combo.blockSignals(False)
        if self.pricelist_combo.count():
            self.pricelist_combo.setCurrentIndex(0)

        self._reload_articles()

    def _load_customers(self) -> None:
        self.customer_combo.clear()
        self.customer_combo.addItem("Odaberite kupca...", userData=None)
        for c in OrderService.list_customers():
            self.customer_combo.addItem(
                f"{c.full_name} ({c.city or 'N/A'})", userData=c.id
            )
        self._check_campaign_warning()

    def _load_orders(self) -> None:
        self._all_orders = OrderService.list_orders()
        self._filter_orders()

    # ------------------------------------------------------------------
    # Izvor artikala
    # ------------------------------------------------------------------

    def _on_source_changed(self, button, checked: bool) -> None:
        if not checked:
            return
        if self._radio_group.id(button) == 0:
            self._source = _SOURCE_CAMPAIGN
            self.campaign_combo.show()
            self.pricelist_combo.hide()
        else:
            self._source = _SOURCE_PRICELIST
            self.campaign_combo.hide()
            self.pricelist_combo.show()
        self.articles_search.clear()
        self._reload_articles()

    def _on_campaign_combo_changed(self, _: int) -> None:
        if self._source == _SOURCE_CAMPAIGN:
            self.articles_search.clear()
            self._reload_articles()

    def _on_pricelist_combo_changed(self, _: int) -> None:
        if self._source == _SOURCE_PRICELIST:
            self.articles_search.clear()
            self._reload_articles()

    def _reload_articles(self) -> None:
        if self._source == _SOURCE_CAMPAIGN:
            cid = self.campaign_combo.currentData()
            self._all_prices = CampaignService.list_campaign_products(cid) if cid else []
        else:
            pid = self.pricelist_combo.currentData()
            self._all_prices = PriceListService.get_items(pid) if pid else []
        self._render_articles(self._all_prices)

    def _render_articles(self, items: list) -> None:
        self.articles_table.setRowCount(0)
        self.articles_table.setRowCount(len(items))
        self.articles_count.setText(f"{len(items)} artikala")

        for row, item in enumerate(items):
            if self._source == _SOURCE_CAMPAIGN:
                # CampaignPrice — nema svih polja kao PriceListItem
                p       = item.product
                rb      = str(row + 1)
                firma   = p.brand if p else ""
                naziv   = p.name if p else "—"
                sifra   = "—"
                cijena  = item.regular_price
                bod     = item.points
                status  = "—"
            else:
                # PriceListItem — sva polja
                rb      = str(row + 1)
                firma   = item.supplier or ""
                naziv   = item.name or "—"
                sifra   = item.supplier_code or "—"
                cijena  = item.regular_price
                bod     = item.points
                status  = item.status or "—"

            row_data = [
                (rb,     Qt.AlignCenter),
                (firma,  Qt.AlignLeft),
                (naziv,  Qt.AlignLeft),
                (sifra,  Qt.AlignCenter),
                (f"{cijena:.2f}" if cijena else "—", Qt.AlignRight),
                (str(int(bod)) if bod else "—",      Qt.AlignCenter),
                (status, Qt.AlignCenter),
            ]

            for col, (val, align) in enumerate(row_data):
                cell = QTableWidgetItem(val)
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                cell.setTextAlignment(align | Qt.AlignVCenter)
                self.articles_table.setItem(row, col, cell)

            # Spremi originalni item za auto-fill (u koloni 0)
            self.articles_table.item(row, 0).setData(Qt.UserRole, item)

        self.articles_table.resizeColumnsToContents()

    def _filter_articles(self) -> None:
        q = self.articles_search.text().strip().lower()
        if not q:
            self._render_articles(self._all_prices)
            return
        if self._source == _SOURCE_CAMPAIGN:
            filtered = [
                cp for cp in self._all_prices
                if cp.product and (
                    q in (cp.product.name or "").lower() or
                    q in (cp.product.brand or "").lower()
                )
            ]
        else:
            filtered = [
                it for it in self._all_prices
                if q in (it.name or "").lower()
                or q in (it.supplier or "").lower()
                or q in (it.supplier_code or "").lower()
            ]
        self._render_articles(filtered)

    def _on_article_clicked(self, cell: QTableWidgetItem) -> None:
        first = self.articles_table.item(cell.row(), 0)
        if not first:
            return
        item = first.data(Qt.UserRole)
        if not item:
            return
        if self._source == _SOURCE_CAMPAIGN:
            name  = item.product.name if item.product else ""
            price = item.regular_price
        else:
            name  = item.name or ""
            price = item.regular_price
        self.product_input.setText(name)
        self.price_input.setText(str(price) if price else "")
        self._update_preview()

    # ------------------------------------------------------------------
    # Filtriranje i prikaz narudžbi
    # ------------------------------------------------------------------

    def _filter_orders(self) -> None:
        if not hasattr(self, "_all_orders"):
            return

        q      = self.orders_search.text().strip().lower()
        status = self.orders_status_filter.currentData()

        result = self._all_orders

        if status:
            result = [o for o in result
                      if (o.status.value if hasattr(o.status, "value") else str(o.status)) == status]

        if q:
            result = [
                o for o in result
                if q in (o.customer.full_name if o.customer else "").lower()
                or q in o.product_name_snapshot.lower()
                or q in (o.contract_number or "").lower()
            ]

        self._render_orders(result)

    def _render_orders(self, orders: list) -> None:
        if not orders:
            show_empty_state(self.table, "Nema narudžbi za prikaz")
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(orders))

        for row, order in enumerate(orders):
            raw      = order.status.value if hasattr(order.status, "value") else str(order.status)
            status_bs = _ORDER_STATUS_BS.get(raw, raw)
            contract  = order.contract_number or ""

            values = [
                (str(order.id),                                            Qt.AlignCenter),
                (contract,                                                 Qt.AlignCenter),
                (order.customer.full_name if order.customer else "N/A",   Qt.AlignLeft),
                (order.product_name_snapshot,                              Qt.AlignLeft),
                (f"{order.total_price_snapshot:.2f}",                     Qt.AlignRight),
                (str(order.installments_count),                            Qt.AlignCenter),
                (order.order_date.strftime("%d.%m.%Y"),                   Qt.AlignCenter),
                (status_bs,                                                Qt.AlignCenter),
            ]

            for col, (val, align) in enumerate(values):
                it = QTableWidgetItem(val)
                it.setTextAlignment(align | Qt.AlignVCenter)

                # Kolona 1 (Br. ugovora) je editabilna
                if col == 1:
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    if order.contract_number:
                        it.setForeground(QColor("#1d4ed8"))
                        f = QFont(); f.setBold(True); it.setFont(f)
                    else:
                        it.setForeground(QColor("#9ca3af"))
                else:
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                if col == 7:
                    it.setForeground(QColor(_ORDER_STATUS_COLOR.get(raw, "#374151")))

                self.table.setItem(row, col, it)

            self.table.item(row, 0).setData(Qt.UserRole, order.id)

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        try:
            price = Decimal(self.price_input.text().replace(",", ".").strip() or "0")
        except Exception:
            price = Decimal("0.00")
        inst = self.installments_combo.currentIndex() + 1
        per  = (price / inst).quantize(Decimal("0.01")) if inst else Decimal("0.00")
        self.preview_total_label.setText(f"Ukupno: {price:.2f} KM")
        self.preview_installment_label.setText(f"{inst} × {per:.2f} KM po rati")

    # ------------------------------------------------------------------
    # Čuvanje narudžbe
    # ------------------------------------------------------------------

    def _check_campaign_warning(self) -> None:
        idx = self.campaign_combo.currentIndex()
        if idx >= 0 and self._source == _SOURCE_CAMPAIGN:
            self.campaign_warning.hide()
        elif not OrderService.has_active_campaign():
            self.campaign_warning.show()
        else:
            self.campaign_warning.hide()

    def _save_order(self) -> None:
        customer_id = self.customer_combo.currentData()
        if not customer_id:
            self._show_message("Obavezno odabrati kupca.", error=True); return

        product_name = self.product_input.text().strip()
        if not product_name:
            self._show_message("Obavezno unijeti naziv artikla.", error=True); return

        price_text = self.price_input.text().replace(",", ".").strip()
        if not price_text:
            self._show_message("Obavezno unijeti cijenu.", error=True); return
        try:
            if Decimal(price_text) <= 0:
                self._show_message("Cijena mora biti veća od 0.", error=True); return
        except Exception:
            self._show_message("Neispravna cijena.", error=True); return

        installments   = self.installments_combo.currentIndex() + 1
        contract_number = self.contract_number_input.text().strip() or None
        campaign_id    = (
            self.campaign_combo.currentData()
            if self._source == _SOURCE_CAMPAIGN else None
        )

        try:
            order = OrderService.create_order(
                customer_id=customer_id,
                product_name=product_name,
                price=price_text,
                installments=installments,
                campaign_id=campaign_id,
                contract_number=contract_number,
            )
            self._show_message(
                f"✅ Narudžba #{order.id} sačuvana! Generisano {installments} rata.",
                error=False,
            )
            self._clear_form(keep_source=True)
            self._load_orders()
            # Skok na tab Pregled narudžbi
            self._tabs.setCurrentIndex(1)
        except Exception as e:
            self._show_message(str(e), error=True)

    def _clear_form(self, keep_source: bool = False) -> None:
        self.customer_combo.setCurrentIndex(0)
        self.product_input.clear()
        self.price_input.clear()
        self.installments_combo.setCurrentIndex(9)
        self.contract_number_input.clear()
        self.articles_search.clear()
        self._update_preview()
        self.message_label.hide()

    # ------------------------------------------------------------------
    # Brisanje narudžbe
    # ------------------------------------------------------------------

    def _on_order_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self._selected_order_id = None
            self.delete_btn.setEnabled(False)
            return
        item = self.table.item(row, 0)
        if item:
            self._selected_order_id = item.data(Qt.UserRole)
            self.delete_btn.setEnabled(True)

    def _delete_selected_order(self) -> None:
        if not self._selected_order_id:
            return
        order = OrderService.get_order_details(self._selected_order_id)
        if not order:
            return

        raw          = order.status.value if hasattr(order.status, "value") else str(order.status)
        status_bs    = _ORDER_STATUS_BS.get(raw, raw)
        contract_info = f"Br. ugovora: {order.contract_number}\n" if order.contract_number else ""

        confirm = QMessageBox.question(
            self, "Potvrdi brisanje narudžbe",
            f"Da li sigurno želiš obrisati ovu narudžbu?\n\n"
            f"Kupac: {order.customer.full_name if order.customer else 'N/A'}\n"
            f"Artikal: {order.product_name_snapshot}\n"
            f"{contract_info}"
            f"Ukupno: {order.total_price_snapshot:.2f} KM — {order.installments_count} rata\n"
            f"Status: {status_bs}\n\n"
            "Bit će obrisane i sve rate i uplate.\nOva radnja se ne može poništiti.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            OrderService.delete_order(self._selected_order_id)
            self._selected_order_id = None
            self.delete_btn.setEnabled(False)
            self._load_orders()
        except Exception as e:
            QMessageBox.warning(self, "Greška", str(e))

    # ------------------------------------------------------------------
    # Detalji narudžbe (dvostruki klik)
    # ------------------------------------------------------------------

    def _on_table_double_clicked(self, index) -> None:
        if index.column() == 1:
            self._edit_contract_number_dialog(index.row())
        else:
            self._show_order_details(index)

    def _edit_contract_number_dialog(self, row: int) -> None:
        """Otvara custom dialog za unos/izmjenu broja ugovora."""
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        order_id = id_item.data(Qt.UserRole)
        contract_item = self.table.item(row, 1)
        current_value = contract_item.text() if contract_item else ""

        _QFont = QFont
        dialog = QDialog(self)
        dialog.setWindowTitle("Broj ugovora")
        dialog.resize(500, 200)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        lbl = QLabel("Unesi broj ugovora:")
        _lf = _QFont(); _lf.setPointSize(13); lbl.setFont(_lf)
        layout.addWidget(lbl)

        field = QLineEdit(current_value)
        _ff = _QFont(); _ff.setPointSize(14); field.setFont(_ff)
        field.setMinimumHeight(46)
        field.setPlaceholderText("npr. UG-2026-001")
        field.setStyleSheet(
            "QLineEdit { border: 2px solid #2563eb; border-radius: 8px; padding: 4px 12px; }"
        )
        layout.addWidget(field)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        ok_btn = QPushButton("Sačuvaj")
        clear_btn = QPushButton("Obriši")
        cancel_btn = QPushButton("Otkaži")
        for btn, bg, hover in [
            (ok_btn,     "#2563eb", "#1d4ed8"),
            (clear_btn,  "#dc2626", "#b91c1c"),
            (cancel_btn, "#6b7280", "#4b5563"),
        ]:
            btn.setMinimumHeight(42)
            _bf = _QFont(); _bf.setPointSize(12); btn.setFont(_bf)
            btn.setStyleSheet(
                f"QPushButton {{ background:{bg}; color:white; border-radius:8px; padding:0 24px; }}"
                f"QPushButton:hover {{ background:{hover}; }}"
            )
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        clear_btn.clicked.connect(lambda: (field.clear(), dialog.accept()))
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        field.setFocus()
        if dialog.exec() != QDialog.Accepted:
            return

        new_contract = field.text().strip() or None
        try:
            OrderService.update_contract_number(order_id, new_contract)
            if contract_item:
                contract_item.setText(new_contract or "")
                if new_contract:
                    contract_item.setForeground(QColor("#1d4ed8"))
                    f = QFont(); f.setBold(True); contract_item.setFont(f)
                else:
                    contract_item.setForeground(QColor("#9ca3af"))
                    contract_item.setFont(QFont())
        except Exception as e:
            QMessageBox.warning(self, "Greška", f"Neuspješno ažuriranje:\n{str(e)}")

    def _show_order_details(self, index) -> None:
        item = self.table.item(index.row(), 0)
        if not item:
            return
        order = OrderService.get_order_details(item.data(Qt.UserRole))
        if not order:
            return

        raw = order.status.value if hasattr(order.status, "value") else str(order.status)
        status_bs = _ORDER_STATUS_BS.get(raw, raw)
        contract_info = f"<b>Br. ugovora:</b> {order.contract_number}<br>" if order.contract_number else ""

        # Kreiraj custom dijalog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Detalji narudžbe #{order.id}")
        dialog.resize(1000, 700)
        dialog.setMinimumWidth(900)
        dialog.setMinimumHeight(600)

        # Glavni layout
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(16)

        # Naslov
        _QFont = QFont
        title = QLabel(f"Narudžba #{order.id}")
        title.setStyleSheet("font-weight: 800; color: #111827;")
        _tf = _QFont(); _tf.setPointSize(20); title.setFont(_tf)
        main_layout.addWidget(title)
        
        # Info sekcija
        info_frame = QFrame()
        info_frame.setStyleSheet("background: #f9fafb; border-radius: 10px; padding: 16px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(10)
        
        info_text = QLabel(
            f"<b>Kupac:</b> {order.customer.full_name if order.customer else 'N/A'}<br>"
            f"<b>Artikal:</b> {order.product_name_snapshot}<br>"
            f"{contract_info}"
            f"<b>Cijena:</b> {order.total_price_snapshot:.2f} KM<br>"
            f"<b>Broj rata:</b> {order.installments_count}<br>"
            f"<b>Datum:</b> {order.order_date.strftime('%d.%m.%Y')}<br>"
            f"<b>Status:</b> <span style='color: {_ORDER_STATUS_COLOR.get(raw, "#374151")}; font-weight: 700;'>{status_bs}</span>"
        )
        info_text.setStyleSheet("color: #1f2937;")
        _inf = _QFont(); _inf.setPointSize(13); info_text.setFont(_inf)
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        main_layout.addWidget(info_frame)
        
        # Tabela rata
        rates_title = QLabel("Pregled rata:")
        rates_title.setStyleSheet("font-weight: 700; color: #111827; margin-top: 10px;")
        _rt = _QFont(); _rt.setPointSize(15); rates_title.setFont(_rt)
        main_layout.addWidget(rates_title)
        
        rates_table = QTableWidget()
        rates_table.setColumnCount(4)
        rates_table.setHorizontalHeaderLabels(["Rata", "Iznos (KM)", "Dospijeće", "Status"])
        rates_table.setRowCount(len(order.installments))
        rates_table.verticalHeader().setVisible(False)
        rates_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        rates_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        rates_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        rates_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        rates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        rates_table.setSelectionBehavior(QTableWidget.SelectRows)
        rates_table.setAlternatingRowColors(True)
        rates_table.setStyleSheet("""
            QTableWidget {
                font-size: 18px;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
            }
            QHeaderView::section {
                background: #e5e7eb;
                font-size: 16px;
                font-weight: 700;
                padding: 12px;
                border: none;
            }
            QTableWidget::item {
                padding: 10px;
            }
        """)
        
        for i, inst in enumerate(order.installments):
            inst_status = _INST_STATUS_BS.get(inst.status.value if hasattr(inst.status, "value") else str(inst.status), str(inst.status))
            
            # Rata broj
            rata_item = QTableWidgetItem(str(inst.installment_number))
            rata_item.setTextAlignment(Qt.AlignCenter)
            rates_table.setItem(i, 0, rata_item)
            
            # Iznos
            iznos_item = QTableWidgetItem(f"{inst.amount:.2f}")
            iznos_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rates_table.setItem(i, 1, iznos_item)
            
            # Dospijeće
            due_item = QTableWidgetItem(inst.due_date.strftime("%d.%m.%Y"))
            due_item.setTextAlignment(Qt.AlignCenter)
            rates_table.setItem(i, 2, due_item)
            
            # Status
            status_item = QTableWidgetItem(inst_status)
            status_item.setTextAlignment(Qt.AlignCenter)
            rates_table.setItem(i, 3, status_item)
        
        main_layout.addWidget(rates_table)
        
        # Dugme Zatvori
        close_btn = QPushButton("Zatvori")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                font-size: 18px;
                font-weight: 700;
                padding: 14px 40px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
        """)
        close_btn.setMinimumHeight(50)
        close_btn.clicked.connect(dialog.accept)
        main_layout.addWidget(close_btn)
        
        dialog.exec()

    # ------------------------------------------------------------------
    # Pomoćne metode
    # ------------------------------------------------------------------

    def _show_message(self, message: str, error: bool = False) -> None:
        self.message_label.setText(message)
        self.message_label.show()
        self.message_label.setStyleSheet(
            "QLabel { background:#fef2f2; color:#dc2626; "
            "border:1px solid #fca5a5; border-radius:6px; padding:8px; }"
            if error else
            "QLabel { background:#f0fdf4; color:#059669; "
            "border:1px solid #86efac; border-radius:6px; padding:8px; }"
        )

    def on_activate(self) -> None:
        self._load_source_combos()
        self._load_customers()
        self._load_orders()
