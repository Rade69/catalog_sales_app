from __future__ import annotations

from decimal import Decimal
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.table_helpers import style_table, show_empty_state, create_numeric_item
from app.gui.widgets.status_badge import make_status_badge
from app.services.dashboard_service import (
    DashboardService,
    InstallmentRow,
    KpiData,
)


class DashboardPage(QWidget):
    """
    Dashboard stranica - početni pregled poslovanja.

    Layout:
    - RED 1: 4 KPI kartice (Kupci, Narudžbe, Dug, Naplaćeno)
    - RED 2: 2 Status kartice (Kasne, Ovaj mjesec)
    - RED 3: 2 Tabele (Rate koje kasne, Rate ovog mjeseca)

    Bez grafova - samo najvažniji podaci.
    """

    def __init__(self) -> None:
        super().__init__()

        self.dashboard_service = DashboardService()

        self._init_ui()
        self._load_dashboard_data()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_widget = QWidget()
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        # RED 1: KPI Kartice (4 komada)
        kpi_section = self._create_kpi_section()
        main_layout.addWidget(kpi_section)

        # RED 2: Status Kartice (2 komada)
        status_section = self._create_status_section()
        main_layout.addWidget(status_section)

        # RED 3: Tabele
        tables_section = self._create_tables_section()
        main_layout.addWidget(tables_section)

        main_layout.addStretch(1)
        scroll.setWidget(scroll_widget)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(scroll)

    def _create_kpi_section(self) -> QFrame:
        """Kreira sekciju sa 4 KPI kartice (RED 1)."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(16)

        # Mjesto za 4 KPI kartice (1 red x 4 kolone)
        self.kpi_cards: List[QWidget] = []
        for i in range(4):
            kpi_card = self._create_kpi_card()
            layout.addWidget(kpi_card, 0, i)
            self.kpi_cards.append(kpi_card)

        return card

    def _create_kpi_card(self) -> QWidget:
        """Kreira KPI karticu sa naslovom, vrijednošću i ikonicom."""
        card = QFrame()
        card.setProperty("kpiCard", True)
        card.setStyleSheet("""
            QWidget[kpiCard="true"] {
                background-color: #f9fafb;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #e5e7eb;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header: naslov + icon
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel("—")
        self.title_label.setStyleSheet("color: #6b7280; font-size: 13px; font-weight: 600;")
        self.title_label.setWordWrap(True)
        header_layout.addWidget(self.title_label)
        
        self.icon_label = QLabel("")
        self.icon_label.setStyleSheet("font-size: 20px;")
        header_layout.addStretch(1)
        header_layout.addWidget(self.icon_label)
        
        layout.addLayout(header_layout)

        # Velika vrijednost
        self.value_label = QLabel("—")
        self.value_label.setStyleSheet("""
            color: #111827;
            font-size: 32px;
            font-weight: 800;
        """)
        layout.addWidget(self.value_label)

        # Footer
        self.footer_label = QLabel("")
        self.footer_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(self.footer_label)

        return card

    def _update_kpi_card(self, card: QWidget, kpi: KpiData, index: int) -> None:
        """Ažurira KPI karticu sa podacima."""
        title = card.findChild(QLabel, f"title_{index}")
        value = card.findChild(QLabel, f"value_{index}")
        footer = card.findChild(QLabel, f"footer_{index}")
        icon = card.findChild(QLabel, f"icon_{index}")
        
        if title:
            title.setText(kpi.title)
        if value:
            value.setText(kpi.value)
        if footer:
            footer.setText(kpi.footer)
        if icon:
            icon.setText(kpi.icon)

    def _create_status_section(self) -> QFrame:
        """Kreira sekciju sa 2 status kartice (RED 2)."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(16)

        # Mjesto za 2 status kartice (1 red x 2 kolone)
        self.status_cards: List[QWidget] = []
        for i in range(2):
            status_card = self._create_status_card()
            layout.addWidget(status_card, 0, i)
            self.status_cards.append(status_card)

        return card

    def _create_status_card(self) -> QWidget:
        """Kreira status karticu sa stilom za alert."""
        card = QFrame()
        card.setProperty("statusCard", True)
        card.setStyleSheet("""
            QWidget[statusCard="true"] {
                background-color: #fef3c7;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #fcd34d;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header: naslov + icon
        header_layout = QHBoxLayout()
        
        title_label = QLabel("—")
        title_label.setObjectName("statusTitle")
        title_label.setStyleSheet("color: #92400e; font-size: 13px; font-weight: 600;")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)
        
        icon_label = QLabel("")
        icon_label.setStyleSheet("font-size: 20px;")
        header_layout.addStretch(1)
        header_layout.addWidget(icon_label)
        
        layout.addLayout(header_layout)

        # Velika vrijednost
        value_label = QLabel("—")
        value_label.setStyleSheet("""
            color: #78350f;
            font-size: 32px;
            font-weight: 800;
        """)
        layout.addWidget(value_label)

        # Footer
        footer_label = QLabel("")
        footer_label.setStyleSheet("color: #b45309; font-size: 12px;")
        layout.addWidget(footer_label)

        # Sačuvaj reference
        card._title_label = title_label
        card._value_label = value_label
        card._footer_label = footer_label
        card._icon_label = icon_label

        return card

    def _update_status_card(self, card: QWidget, kpi: KpiData) -> None:
        """Ažurira status karticu sa podacima."""
        card._title_label.setText(kpi.title)
        card._value_label.setText(kpi.value)
        card._footer_label.setText(kpi.footer)
        card._icon_label.setText(kpi.icon)

    def _create_tables_section(self) -> QFrame:
        """Kreira sekciju sa tabelama (RED 3)."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        # Tabela 1: Rate koje kasne
        overdue_label = QLabel("⚠️ Rate koje kasne")
        overdue_label.setProperty("sectionTitle", True)
        layout.addWidget(overdue_label)

        self.overdue_table = self._create_overdue_table()
        layout.addWidget(self.overdue_table)

        # Tabela 2: Rate ovog mjeseca
        month_label = QLabel("📅 Rate za ovaj mjesec")
        month_label.setProperty("sectionTitle", True)
        layout.addWidget(month_label)

        self.month_table = self._create_month_table()
        layout.addWidget(self.month_table)

        return card

    def _create_overdue_table(self) -> QTableWidget:
        """Kreira tabelu za rate koje kasne."""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Kupac", "Proizvod", "Rata", "Plaćeno", "Preostalo", "Dospijeće"
        ])

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        style_table(table)

        return table

    def _create_month_table(self) -> QTableWidget:
        """Kreira tabelu za rate ovog mjeseca."""
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "Kupac", "Proizvod", "Rata", "Plaćeno", "Preostalo", "Dospijeće", "Status"
        ])

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        style_table(table)

        return table

    def _populate_overdue_table(
        self,
        table: QTableWidget,
        rows: List[InstallmentRow]
    ) -> None:
        """Popunjava tabelu sa ratama koje kasne."""
        if not rows:
            show_empty_state(table, "Nema rata koje kasne")
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
            due_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 5, due_item)

        table.resizeColumnsToContents()

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
            due_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 5, due_item)

            status_badge = make_status_badge(row.status)
            table.setCellWidget(i, 6, status_badge)

        table.resizeColumnsToContents()

    def _load_dashboard_data(self) -> None:
        """Učitava sve podatke za dashboard."""
        # RED 1: KPI-jevi
        kpis = self.dashboard_service.get_dashboard_kpis()
        for i, kpi in enumerate(kpis):
            if i < len(self.kpi_cards):
                self._update_kpi_card(self.kpi_cards[i], kpi, i)

        # RED 2: Status KPI-jevi
        status_kpis = self.dashboard_service.get_status_kpis()
        for i, kpi in enumerate(status_kpis):
            if i < len(self.status_cards):
                self._update_status_card(self.status_cards[i], kpi)

        # RED 3: Tabele
        self._load_tables()

    def _load_tables(self) -> None:
        """Učitava podatke za tabele."""
        # Tabela 1: Rate koje kasne
        overdue = self.dashboard_service.get_overdue_installments(limit=10)
        self._populate_overdue_table(self.overdue_table, overdue)

        # Tabela 2: Rate ovog mjeseca
        month = self.dashboard_service.get_current_month_installments(limit=10)
        self._populate_month_table(self.month_table, month)

    def on_activate(self) -> None:
        """Osvježava podatke kada se stranica aktivira."""
        self._load_dashboard_data()
