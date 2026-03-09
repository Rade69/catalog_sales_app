from __future__ import annotations

from decimal import Decimal
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, show_empty_state, create_numeric_item
from app.services.dashboard_service import (
    DashboardService,
    InstallmentRow,
    KpiData,
    PaymentRow,
)


class DashboardPage(QWidget):
    """
    Dashboard stranica - početni pregled poslovanja.

    Layout prema referentnom mockupu:
    - TOP BAR: Tamno plavi header (#1f4f9f) sa naslovom i kontrolama
    - CONTENT AREA: Svijetlo siva pozadina (#f5f7fb) sa 30px paddingom
    - RED 1: 4 KPI kartice (Kupci, Aktivne Narudžbe, Preostali Dug, Naplaćeno Ovaj Mjesec)
    - RED 2: 2 Status kartice (Rate koje Kasne, Rate ovog Mjeseca)
    - RED 3: 2 Tabele u card sekcijama (Uplate po mjesecima, Rate ovog mjeseca)
    """

    def __init__(self) -> None:
        super().__init__()

        self.dashboard_service = DashboardService()

        self._init_ui()
        self._load_dashboard_data()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Kontrolna traka: period + dugme
        controls_row = self._create_controls_row()
        main_layout.addWidget(controls_row)

        # RED 1: KPI Kartice (4 komada)
        kpi_section = self._create_kpi_section()
        main_layout.addWidget(kpi_section)

        # RED 2: Status Kartice (2 komada)
        status_section = self._create_status_section()
        main_layout.addWidget(status_section)

        # RED 3: Tabele (2 velike card sekcije)
        tables_section = self._create_tables_section()
        main_layout.addWidget(tables_section, 1)

    def _create_controls_row(self) -> QFrame:
        """Kreira red sa kontrolama (dugme za izvještaj)."""
        row = QFrame()
        row.setStyleSheet("background-color: transparent; border: none;")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addStretch(1)

        # Primary dugme
        self.report_btn = QPushButton("+ Novi izvještaj")
        self.report_btn.setProperty("primary", True)
        self.report_btn.setFixedHeight(36)
        layout.addWidget(self.report_btn)

        return row

    def _create_kpi_section(self) -> QFrame:
        """Kreira sekciju sa 4 KPI kartice (RED 1)."""
        card = QFrame()
        card.setStyleSheet("background-color: transparent; border: none;")

        layout = QGridLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(0)

        # 4 KPI kartice u jednom redu
        self.kpi_cards: List[QFrame] = []

        # Kartica 1: Kupci (plava)
        kpi1 = self._create_kpi_card(
            title="KUPCI",
            value="—",
            footer="Baza kupaca",
            color="#2563eb",
            card_type="kupci"
        )
        layout.addWidget(kpi1, 0, 0)
        self.kpi_cards.append(kpi1)

        # Kartica 2: Aktivne Narudžbe (svijetlo plava)
        kpi2 = self._create_kpi_card(
            title="AKTIVNE NARUDŽBE",
            value="—",
            footer="Sa neplaćenim ratama",
            color="#3b82f6",
            card_type="narudzbe"
        )
        layout.addWidget(kpi2, 0, 1)
        self.kpi_cards.append(kpi2)

        # Kartica 3: Preostali Dug (crvena)
        kpi3 = self._create_kpi_card(
            title="PREOSTALI DUG",
            value="—",
            footer="Aktivna potraživanja",
            color="#dc2626",
            card_type="dug"
        )
        layout.addWidget(kpi3, 0, 2)
        self.kpi_cards.append(kpi3)

        # Kartica 4: Naplaćeno Ovaj Mjesec (zelena)
        kpi4 = self._create_kpi_card(
            title="NAPLACENO OVAJ MJES.",
            value="—",
            footer="Tekući mjesec",
            color="#16a34a",
            card_type="naplaceno"
        )
        layout.addWidget(kpi4, 0, 3)
        self.kpi_cards.append(kpi4)

        return card

    def _create_kpi_card(
        self,
        title: str,
        value: str,
        footer: str,
        color: str,
        card_type: str
    ) -> QFrame:
        """Kreira pojedinačnu KPI karticu."""
        card = QFrame()
        card.setProperty("kpiCard", True)
        card.setProperty("cardType", card_type)
        card.setFixedHeight(115)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # Naslov
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: #6b7280; font-size: 11px; font-weight: 700;")
        layout.addWidget(title_label)

        # Vrijednost (velika)
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: #111827; font-size: 28px; font-weight: 800;")
        layout.addWidget(value_label)

        # Footer
        footer_label = QLabel(footer)
        footer_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        layout.addWidget(footer_label)

        layout.addStretch(1)

        # Sačuvaj reference
        card._value_label = value_label
        card._footer_label = footer_label

        return card

    def _create_status_section(self) -> QFrame:
        """Kreira sekciju sa 2 status kartice (RED 2)."""
        card = QFrame()
        card.setStyleSheet("background-color: transparent; border: none;")

        layout = QGridLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(0)

        # Kartica 1: Rate koje kasne (crvenkasta)
        self.overdue_card = self._create_status_card(
            title="RATE KOJE KASNE",
            value="0",
            footer="Prioritet za naplatu",
            status_type="overdue"
        )
        layout.addWidget(self.overdue_card, 0, 0)

        # Kartica 2: Rate ovog mjeseca (narandžasta)
        self.month_card = self._create_status_card(
            title="RATE OVOG MJESECA",
            value="0",
            footer="Dospijevaju sada",
            status_type="month"
        )
        layout.addWidget(self.month_card, 0, 1)

        return card

    def _create_status_card(
        self,
        title: str,
        value: str,
        footer: str,
        status_type: str
    ) -> QFrame:
        """Kreira status karticu sa alert stilom."""
        is_overdue = status_type == "overdue"
        title_color = "#991b1b" if is_overdue else "#9a3412"
        value_color = "#dc2626" if is_overdue else "#ea580c"
        footer_color = "#b91c1c" if is_overdue else "#9a3412"

        card = QFrame()
        card.setProperty("statusCard", True)
        card.setProperty("statusType", status_type)
        card.setFixedHeight(105)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # Naslov
        title_label = QLabel(title)
        title_label.setProperty("statusTitle", True)
        title_label.setStyleSheet(f"color: {title_color}; font-size: 11px; font-weight: 700;")
        layout.addWidget(title_label)

        # Vrijednost (velika)
        value_label = QLabel(value)
        value_label.setProperty("statusValue", True)
        value_label.setStyleSheet(f"color: {value_color}; font-size: 32px; font-weight: 800;")
        layout.addWidget(value_label)

        # Footer
        footer_label = QLabel(footer)
        footer_label.setStyleSheet(f"color: {footer_color}; font-size: 12px; font-weight: 600;")
        layout.addWidget(footer_label)

        layout.addStretch(1)

        # Sačuvaj reference
        card._value_label = value_label
        card._footer_label = footer_label

        return card

    def _create_tables_section(self) -> QFrame:
        """Kreira sekciju sa 2 velike tabele (RED 3)."""
        container = QFrame()
        container.setStyleSheet("background-color: transparent; border: none;")

        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(0)

        # Tabela 1: Nedavne uplate
        payments_table_card = self._create_table_card(
            title="Nedavne uplate",
            columns=["Kupac", "Artikal", "Rata", "Iznos (KM)", "Datum"],
            is_payments=True
        )
        layout.addWidget(payments_table_card, 0, 0)

        # Tabela 2: Rate ovog mjeseca
        month_table_card = self._create_table_card(
            title="Rate ovog mjeseca",
            columns=["Kupac", "Proizvod", "Rata", "Plaćeno", "Preostalo", "Dospijeće", "Status"],
            is_payments=False
        )
        layout.addWidget(month_table_card, 0, 1)

        return container

    def _create_table_card(
        self,
        title: str,
        columns: List[str],
        is_payments: bool = False
    ) -> QFrame:
        """Kreira card sekciju sa tabelom."""
        card = QFrame()
        card.setProperty("dashboardTable", True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        # Title
        title_label = QLabel(title)
        title_label.setProperty("tableTitle", True)
        title_label.setStyleSheet("color: #1f2937; font-size: 15px; font-weight: 700;")
        layout.addWidget(title_label)

        # Tabela
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        if is_payments:
            # Kupac | Artikal | Rata | Iznos (KM) | Datum
            table.setColumnWidth(2, 70)
            table.setColumnWidth(3, 95)
            table.setColumnWidth(4, 100)
            for i in range(2, len(columns)):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
        else:
            # Kupac | Proizvod | Rata | Plaćeno | Preostalo | Dospijeće | Status
            table.setColumnWidth(2, 70)
            table.setColumnWidth(3, 95)
            table.setColumnWidth(4, 95)
            table.setColumnWidth(5, 100)
            table.setColumnWidth(6, 90)
            for i in range(2, len(columns)):
                header.setSectionResizeMode(i, QHeaderView.Fixed)

        # Stil tabele
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                gridline-color: #f3f4f6;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #f3f4f6;
            }
            QTableWidget::item:hover {
                background-color: #f9fafb;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #6b7280;
                font-weight: 700;
                font-size: 12px;
                padding: 10px 8px;
                border: none;
                border-bottom: 2px solid #e5e7eb;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        """)

        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)

        layout.addWidget(table)

        # Sačuvaj referencu na tabelu
        if is_payments:
            self.payments_table = table
        else:
            self.month_table = table

        return card

    def _update_kpi_card_data(self, card: QFrame, kpi: KpiData) -> None:
        """Ažurira KPI karticu sa podacima."""
        if hasattr(card, "_value_label"):
            card._value_label.setText(kpi.value)
        if hasattr(card, "_footer_label"):
            card._footer_label.setText(kpi.footer)

    def _update_status_cards(self, kpis: List[KpiData]) -> None:
        """Ažurira status kartice sa podacima."""
        if len(kpis) > 0 and hasattr(self.overdue_card, "_value_label"):
            self.overdue_card._value_label.setText(kpis[0].value)
        if len(kpis) > 1 and hasattr(self.month_card, "_value_label"):
            self.month_card._value_label.setText(kpis[1].value)

    def _populate_payments_table(
        self,
        table: QTableWidget,
        rows: List[PaymentRow]
    ) -> None:
        """Popunjava tabelu sa nedavnim uplatama."""
        if not rows:
            show_empty_state(table, "Nema uplata")
            return

        table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(row.customer_name))
            table.setItem(i, 1, QTableWidgetItem(row.product_name))

            rata_text = f"{row.installment_number}/{row.total_installments}"
            rata_item = QTableWidgetItem(rata_text)
            rata_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            table.setItem(i, 2, rata_item)

            amount_item = create_numeric_item(row.amount, " KM")
            amount_item.setForeground(QColor("#059669"))
            table.setItem(i, 3, amount_item)

            date_item = QTableWidgetItem(row.payment_date.strftime("%d.%m.%Y."))
            date_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            table.setItem(i, 4, date_item)

    def _populate_month_table(
        self,
        table: QTableWidget,
        rows: List[InstallmentRow]
    ) -> None:
        """Popunjava tabelu sa ratama ovog mjeseca."""
        if not rows:
            show_empty_state(table, "Nema rata za ovaj mjesec")
            return

        table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(row.customer_name))
            table.setItem(i, 1, QTableWidgetItem(row.product_name))

            rata_text = f"{row.installment_number}/{row.total_installments}"
            table.setItem(i, 2, QTableWidgetItem(rata_text))

            table.setItem(i, 3, create_numeric_item(row.paid_amount, " KM"))

            remaining_item = create_numeric_item(row.remaining_amount, " KM")
            if row.remaining_amount > 0:
                remaining_item.setForeground(QColor("#dc2626"))
            table.setItem(i, 4, remaining_item)

            due_item = QTableWidgetItem(row.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            table.setItem(i, 5, due_item)

            status_map = {
                "paid": ("PLAĆENO", "#dcfce7", "#166534"),
                "partially_paid": ("DJELIMIČNO", "#fef3c7", "#92400e"),
                "overdue": ("KASNI", "#fee2e2", "#991b1b"),
                "pending": ("ČEKA", "#f3f4f6", "#6b7280"),
            }
            status_text, bg, fg = status_map.get(
                row.status, ("—", "#f3f4f6", "#6b7280")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            status_item.setBackground(QColor(bg))
            status_item.setForeground(QColor(fg))
            table.setItem(i, 6, status_item)

    def _load_dashboard_data(self) -> None:
        """Učitava sve podatke za dashboard."""
        # RED 1: KPI-jevi
        kpis = self.dashboard_service.get_dashboard_kpis()
        for i, kpi in enumerate(kpis):
            if i < len(self.kpi_cards):
                self._update_kpi_card_data(self.kpi_cards[i], kpi)

        # RED 2: Status KPI-jevi
        status_kpis = self.dashboard_service.get_status_kpis()
        self._update_status_cards(status_kpis)

        # RED 3: Tabele
        self._load_tables()

    def _load_tables(self) -> None:
        """Učitava podatke za tabele."""
        # Tabela 1: Nedavne uplate
        payments = self.dashboard_service.get_recent_payments(limit=8)
        if hasattr(self, "payments_table"):
            self._populate_payments_table(self.payments_table, payments)

        # Tabela 2: Rate ovog mjeseca
        month = self.dashboard_service.get_current_month_installments(limit=8)
        if hasattr(self, "month_table"):
            self._populate_month_table(self.month_table, month)

    def on_activate(self) -> None:
        """Osvježava podatke kada se stranica aktivira."""
        self._load_dashboard_data()
