from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import (
    ChartData,
    DashboardService,
    InstallmentRow,
    KpiData,
)


class DashboardPage(QWidget):
    """
    Dashboard stranica - početni pregled poslovanja.
    
    Prikazuje:
    - KPI kartice (6 komada)
    - Grafove (uplate po mjesecima, narudžbe po kampanjama)
    - Tabele (rate koje kasne, rate ovog mjeseca)
    """

    def __init__(self) -> None:
        super().__init__()
        
        self.dashboard_service = DashboardService()
        
        self._init_ui()
        self._load_dashboard_data()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        # Scroll area za sav sadržaj
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        # Glavni widget unutar scrolla
        scroll_widget = QWidget()
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        
        # 1. KPI Kartice
        kpi_section = self._create_kpi_section()
        main_layout.addWidget(kpi_section)
        
        # 2. Grafovi
        charts_section = self._create_charts_section()
        main_layout.addWidget(charts_section)
        
        # 3. Tabele
        tables_section = self._create_tables_section()
        main_layout.addWidget(tables_section)
        
        # Dodaj stretch na kraj
        main_layout.addStretch(1)
        
        scroll.setWidget(scroll_widget)
        
        # Postavi scroll u glavni layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(scroll)

    def _create_kpi_section(self) -> QFrame:
        """Kreira sekciju sa KPI karticama."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(16)
        
        # Naslov sekcije
        title = QLabel("Ključni pokazatelji")
        title.setProperty("sectionTitle", True)
        layout.addWidget(title, 0, 0, 1, 6)
        
        # Mjesto za 6 KPI kartica (2 reda x 3 kolone)
        self.kpi_cards: List[QWidget] = []
        for i in range(6):
            row = (i // 3) + 1
            col = i % 3
            kpi_card = self._create_empty_kpi_card()
            layout.addWidget(kpi_card, row, col)
            self.kpi_cards.append(kpi_card)
        
        return card

    def _create_empty_kpi_card(self) -> QWidget:
        """Kreira praznu KPI karticu."""
        card = QFrame()
        card.setProperty("kpiCard", True)
        card.setStyleSheet("""
            QWidget[kpiCard="true"] {
                background-color: #f9fafb;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        title_label = QLabel("—")
        title_label.setStyleSheet("color: #6b7280; font-size: 13px;")
        title_label.setWordWrap(True)
        
        value_label = QLabel("—")
        value_label.setStyleSheet("""
            color: #111827;
            font-size: 28px;
            font-weight: bold;
        """)
        
        footer_label = QLabel("")
        footer_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(footer_label)
        
        # Sačuvaj reference za ažuriranje
        card._title_label = title_label
        card._value_label = value_label
        card._footer_label = footer_label
        
        return card

    def _update_kpi_card(self, card: QWidget, kpi: KpiData) -> None:
        """Ažurira KPI karticu sa podacima."""
        card._title_label.setText(kpi.title)
        card._value_label.setText(kpi.value)
        card._footer_label.setText(kpi.footer)

    def _create_charts_section(self) -> QFrame:
        """Kreira sekciju sa grafovima."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        
        # Naslov
        title = QLabel("Pregled po mjesecima i kampanjama")
        title.setProperty("sectionTitle", True)
        
        # Vertikalni layout za grafove
        charts_layout = QVBoxLayout()
        charts_layout.addWidget(title)
        
        # Graf 1: Uplate po mjesecima
        self.payments_chart = self._create_simple_bar_chart(
            "Uplate po mjesecima (posljednjih 6 mjeseci)",
            [],
            []
        )
        charts_layout.addWidget(self.payments_chart)
        
        # Graf 2: Narudžbe po kampanjama
        self.orders_chart = self._create_simple_bar_chart(
            "Broj narudžbi po kampanjama",
            [],
            []
        )
        charts_layout.addWidget(self.orders_chart)
        
        charts_layout.addStretch(1)
        layout.addLayout(charts_layout, 1)
        
        return card

    def _create_simple_bar_chart(
        self,
        title: str,
        labels: List[str],
        values: List[float]
    ) -> QFrame:
        """
        Kreira jednostavan bar chart bez vanjskih biblioteka.
        Koristi QProgressBar za vizuelizaciju.
        """
        card = QFrame()
        card.setProperty("chartCard", True)
        card.setStyleSheet("""
            QWidget[chartCard="true"] {
                background-color: #f3f4f6;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Naslov grafa
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #374151; font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)

        # Kontejner za barove (lokalna varijabla, ne instance atribut)
        bars_container = QWidget()
        bars_layout = QVBoxLayout(bars_container)
        bars_layout.setSpacing(6)
        bars_layout.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(bars_container)

        # Sačuvaj reference na card objektu
        card._bars_layout = bars_layout
        card._title_label = title_label

        # Ako ima podataka, popuni barove
        if labels and values:
            self._update_bar_chart(card, labels, values)

        return card

    def _update_bar_chart(
        self,
        chart_card: QFrame,
        labels: List[str],
        values: List[float]
    ) -> None:
        """Ažurira bar chart sa podacima."""
        # Obriši stare barove
        while chart_card._bars_layout.count():
            item = chart_card._bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not values:
            no_data = QLabel("Nema podataka")
            no_data.setStyleSheet("color: #9ca3af; font-style: italic; padding: 8px;")
            chart_card._bars_layout.addWidget(no_data)
            return
        
        # Nađi max vrijednost za skaliranje
        max_value = max(values) if values else 1
        if max_value == 0:
            max_value = 1
        
        # Kreiraj barove
        for label, value in zip(labels, values):
            bar_widget = QWidget()
            bar_layout = QHBoxLayout(bar_widget)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(8)
            
            # Labela
            label_widget = QLabel(label[:15] + "..." if len(label) > 15 else label)
            label_widget.setStyleSheet("color: #374151; font-size: 11px;")
            label_widget.setFixedWidth(100)
            bar_layout.addWidget(label_widget)
            
            # Progress bar
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int((value / max_value) * 100))
            progress.setTextVisible(False)
            progress.setFixedHeight(20)
            progress.setStyleSheet("""
                QProgressBar {
                    background-color: #e5e7eb;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #059669;
                    border-radius: 4px;
                }
            """)
            bar_layout.addWidget(progress, 1)
            
            # Vrijednost
            value_label = QLabel(f"{value:.0f}" if value == int(value) else f"{value:.2f}")
            value_label.setStyleSheet("color: #111827; font-weight: bold; font-size: 12px;")
            value_label.setFixedWidth(60)
            value_label.setAlignment(Qt.AlignRight)
            bar_layout.addWidget(value_label)
            
            chart_card._bars_layout.addWidget(bar_widget)

    def _create_tables_section(self) -> QFrame:
        """Kreira sekciju sa tabelama."""
        card = QFrame()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        
        # Tabela 1: Rate koje kasne
        overdue_label = QLabel("Rate koje kasne")
        overdue_label.setProperty("sectionTitle", True)
        layout.addWidget(overdue_label)
        
        self.overdue_table = self._create_installments_table()
        layout.addWidget(self.overdue_table)
        
        # Tabela 2: Rate ovog mjeseca
        month_label = QLabel("Rate za ovaj mjesec")
        month_label.setProperty("sectionTitle", True)
        layout.addWidget(month_label)
        
        self.month_table = self._create_installments_table()
        layout.addWidget(self.month_table)
        
        return card

    def _create_installments_table(self) -> QTableWidget:
        """Kreira tabelu za rate."""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Kupac", "Proizvod", "Rata", "Iznos", "Plaćeno", "Preostalo", "Dospijeće", "Status"
        ])
        
        # Konfiguracija
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Kupac
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Proizvod
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Rata
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Iznos
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Plaćeno
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Preostalo
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Dospijeće
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status
        
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        
        return table

    def _populate_installments_table(
        self,
        table: QTableWidget,
        rows: List[InstallmentRow]
    ) -> None:
        """Popunjava tabelu sa podacima o ratama."""
        table.setRowCount(0)
        table.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            # Kupac
            table.setItem(i, 0, QTableWidgetItem(row.customer_name))
            
            # Proizvod
            table.setItem(i, 1, QTableWidgetItem(row.product_name))
            
            # Rata (n/N)
            rata_text = f"{row.installment_number}/{row.total_installments}"
            table.setItem(i, 2, QTableWidgetItem(rata_text))
            
            # Iznos
            amount_item = QTableWidgetItem(f"{row.amount:.2f} KM")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 3, amount_item)
            
            # Plaćeno
            paid_item = QTableWidgetItem(f"{row.paid_amount:.2f} KM")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 4, paid_item)
            
            # Preostalo
            remaining_item = QTableWidgetItem(f"{row.remaining_amount:.2f} KM")
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if row.remaining_amount > 0:
                remaining_item.setForeground(QColor("#dc2626"))
            table.setItem(i, 5, remaining_item)
            
            # Dospijeće
            due_item = QTableWidgetItem(row.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 6, due_item)
            
            # Status
            status_text = {
                "paid": "PLAĆENO",
                "partially_paid": "DJELIMIČNO",
                "overdue": "KASNI",
                "pending": "ČEKA"
            }.get(row.status, row.status.upper())
            
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)
            
            # Boja statusa
            if row.status == "paid":
                status_item.setForeground(QColor("#059669"))
            elif row.status == "overdue":
                status_item.setForeground(QColor("#dc2626"))
            elif row.status == "partially_paid":
                status_item.setForeground(QColor("#d97706"))
            else:
                status_item.setForeground(QColor("#6b7280"))
            
            table.setItem(i, 7, status_item)
        
        table.resizeColumnsToContents()

    def _load_dashboard_data(self) -> None:
        """Učitava sve podatke za dashboard."""
        # 1. KPI-evi
        kpis = self.dashboard_service.get_all_kpis()
        for i, kpi in enumerate(kpis):
            if i < len(self.kpi_cards):
                self._update_kpi_card(self.kpi_cards[i], kpi)
        
        # 2. Grafovi
        self._load_charts()
        
        # 3. Tabele
        self._load_tables()

    def _load_charts(self) -> None:
        """Učitava podatke za grafove."""
        # Graf 1: Uplate po mjesecima
        payments_data = self.dashboard_service.get_monthly_payments_chart_data()
        self._update_bar_chart(
            self.payments_chart,
            payments_data.labels,
            payments_data.values
        )
        
        # Graf 2: Narudžbe po kampanjama
        orders_data = self.dashboard_service.get_orders_by_campaign_chart_data()
        self._update_bar_chart(
            self.orders_chart,
            orders_data.labels,
            orders_data.values
        )

    def _load_tables(self) -> None:
        """Učitava podatke za tabele."""
        # Tabela 1: Rate koje kasne
        overdue = self.dashboard_service.get_overdue_installments(limit=10)
        self._populate_installments_table(self.overdue_table, overdue)
        
        # Tabela 2: Rate ovog mjeseca
        month = self.dashboard_service.get_current_month_installments(limit=10)
        self._populate_installments_table(self.month_table, month)

    def on_activate(self) -> None:
        """Poziva se kada se stranica aktivira - osvježava podatke."""
        self._load_dashboard_data()
