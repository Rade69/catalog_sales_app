from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.gui.base_page import BasePage
from app.gui.icons import get_pixmap
from app.gui.table_helpers import style_table, show_empty_state, create_numeric_item
from app.services.dashboard_service import (
    DashboardService,
    DashboardData,
    InstallmentRow,
    KpiData,
    PaymentRow,
)
from app.gui.workers import LoadDashboardWorker


class DashboardPage(BasePage):
    """
    Dashboard stranica - početni pregled poslovanja.

    Layout prema referentnom mockupu:
    - HEADER: Informativna traka sa datumom
    - RED 1: 4 KPI kartice (Kupci, Aktivne Narudžbe, Preostali Dug, Naplaćeno Ovaj Mjesec)
    - RED 2: 2 Status kartice (Rate koje Kasne, Rate ovog Mjeseca)
    - RED 3: 2 Tabele u card sekcijama (Uplate po mjesecima, Rate ovog mjeseca)
    """

    def __init__(self) -> None:
        super().__init__()

        self._worker: Optional[LoadDashboardWorker] = None
        self._loading_label: Optional[QLabel] = None

        self._init_ui()

    def _init_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # Header traka sa datumom
        header = self._create_header_row()
        main_layout.addWidget(header)

        # Loading label (skriven dok se ne učitava)
        self._loading_label = QLabel("Učitavanje podataka...")
        self._loading_label.setStyleSheet(
            "color: #6b7280; font-size: 14px; font-style: italic; padding: 8px;"
        )
        self._loading_label.hide()
        main_layout.addWidget(self._loading_label)

        # RED 1: KPI Kartice (4 komada)
        kpi_section = self._create_kpi_section()
        main_layout.addWidget(kpi_section)

        # RED 2: Status Kartice (2 komada)
        status_section = self._create_status_section()
        main_layout.addWidget(status_section)

        # RED 3: Tabele (2 velike card sekcije)
        tables_section = self._create_tables_section()
        main_layout.addWidget(tables_section, 1)

    def _create_header_row(self) -> QFrame:
        """Kreira header traku sa datumom."""
        _BS_DAYS = {
            0: "Ponedjeljak", 1: "Utorak", 2: "Srijeda",
            3: "Četvrtak",    4: "Petak",  5: "Subota", 6: "Nedjelja"
        }
        _BS_MONTHS = {
            1: "januara", 2: "februara", 3: "marta", 4: "aprila",
            5: "maja", 6: "juna", 7: "jula", 8: "augusta",
            9: "septembra", 10: "oktobra", 11: "novembra", 12: "decembra"
        }
        today = date.today()
        date_str = (
            f"{_BS_DAYS[today.weekday()]}, "
            f"{today.day}. {_BS_MONTHS[today.month]} {today.year}."
        )

        row = QFrame()
        row.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 4)

        title = QLabel("Kontrolna tabla")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #111827; border: none;"
        )
        date_label = QLabel(date_str)
        date_label.setStyleSheet(
            "font-size: 15px; color: #4b5563; font-weight: 600;"
        )

        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(date_label)
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
            title="KUPCI", value="—", footer="Baza kupaca",
            color="#2563eb", card_type="kupci", icon="customers"
        )
        layout.addWidget(kpi1, 0, 0)
        self.kpi_cards.append(kpi1)

        # Kartica 2: Aktivne Narudžbe (svijetlo plava)
        kpi2 = self._create_kpi_card(
            title="AKTIVNE NARUDŽBE", value="—", footer="Sa neplaćenim ratama",
            color="#3b82f6", card_type="narudzbe", icon="orders"
        )
        layout.addWidget(kpi2, 0, 1)
        self.kpi_cards.append(kpi2)

        # Kartica 3: Preostali Dug (crvena)
        kpi3 = self._create_kpi_card(
            title="PREOSTALI DUG", value="—", footer="Aktivna potraživanja",
            color="#dc2626", card_type="dug", icon="credit-card"
        )
        layout.addWidget(kpi3, 0, 2)
        self.kpi_cards.append(kpi3)

        # Kartica 4: Naplaćeno Ovaj Mjesec (zelena)
        kpi4 = self._create_kpi_card(
            title="NAPLAĆENO OVAJ MJESEC", value="—", footer="Tekući mjesec",
            color="#16a34a", card_type="naplaceno", icon="payments"
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
        card_type: str,
        icon: str = "",
    ) -> QFrame:
        """Kreira pojedinačnu KPI karticu sa obojenom gornjom trakom i ikonom."""
        # Mapa accent → blaga pozadina
        bg_map = {
            "#2563eb": "#eff6ff",   # plava
            "#3b82f6": "#eff6ff",   # plava varijanta
            "#dc2626": "#fef2f2",   # crvena
            "#16a34a": "#f0fdf4",   # zelena
        }
        bg_color = bg_map.get(color, "#f9fafb")

        card = QFrame()
        card.setProperty("kpiCard", True)
        card.setProperty("cardType", card_type)
        card.setFixedHeight(120)
        card.setStyleSheet(f"""
            QFrame[kpiCard="true"] {{
                background: {bg_color};
                border: 1px solid #e5e7eb;
                border-top: 4px solid {color};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        # Naslov sa ikonom
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        if icon:
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(24, 24)
            icon_lbl.setPixmap(get_pixmap(icon, color, 24))
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            title_row.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #6b7280; font-size: 14px; font-weight: 700; "
            "letter-spacing: 0.05em; border: none; background: transparent;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        # Vrijednost (velika)
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"color: #111827; font-size: 30px; font-weight: 800; "
            f"border: none; background: transparent;"
        )
        layout.addWidget(value_label)

        # Footer
        footer_label = QLabel(footer)
        footer_label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: 600; "
            f"border: none; background: transparent;"
        )
        layout.addWidget(footer_label)

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
        status_type: str,
    ) -> QFrame:
        """Kreira status karticu sa alert stilom i obojenom pozadinom."""
        is_overdue  = status_type == "overdue"
        bg_color    = "#fef2f2"  if is_overdue else "#fff7ed"
        border_col  = "#fca5a5"  if is_overdue else "#fdba74"
        title_color = "#991b1b"  if is_overdue else "#9a3412"
        value_color = "#dc2626"  if is_overdue else "#ea580c"
        icon_name   = "alert"    if is_overdue else "calendar"

        card = QFrame()
        card.setProperty("statusCard", True)
        card.setProperty("statusType", status_type)
        card.setFixedHeight(110)
        card.setStyleSheet(f"""
            QFrame[statusCard="true"] {{
                background: {bg_color};
                border: 1px solid {border_col};
                border-left: 5px solid {value_color};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        # Naslov sa ikonom
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(20, 20)
        icon_lbl.setPixmap(get_pixmap(icon_name, title_color, 20))
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        title_row.addWidget(icon_lbl)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {title_color}; font-size: 14px; font-weight: 700; "
            f"letter-spacing: 0.05em; border: none; background: transparent;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        # Vrijednost
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"color: {value_color}; font-size: 34px; font-weight: 800; "
            f"border: none; background: transparent;"
        )
        layout.addWidget(value_label)

        # Footer
        footer_label = QLabel(footer)
        footer_label.setStyleSheet(
            f"color: {title_color}; font-size: 14px; font-weight: 500; "
            f"border: none; background: transparent;"
        )
        layout.addWidget(footer_label)

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
            columns=["Kupac", "Artikal", "Rata", "Iznos (EUR)", "Datum"],
            is_payments=True
        )
        layout.addWidget(payments_table_card, 0, 0)

        # Tabela 2: Rate ovog mjeseca
        month_table_card = self._create_table_card(
            title="Rate ovog mjeseca",
            columns=["Kupac", "Proizvod", "Rata", "Plaćeno", "Preostalo", "Dospijeće"],
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
        """Kreira card sekciju sa tabelom i badge-om za broj zapisa."""
        card = QFrame()
        card.setProperty("dashboardTable", True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        # Naslov red: naziv + badge sa brojem zapisa
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #1f2937; font-size: 15px; font-weight: 700; border: none;"
        )

        self._badge_payments = QLabel("") if is_payments else None
        self._badge_month    = QLabel("") if not is_payments else None
        badge = self._badge_payments if is_payments else self._badge_month
        if badge:
            badge.setStyleSheet("""
                QLabel {
                    background: #e5e7eb;
                    color: #374151;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 8px;
                    border-radius: 10px;
                    border: none;
                }
            """)

        title_row.addWidget(title_label)
        if badge:
            title_row.addWidget(badge)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        # Tabela
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = table.horizontalHeader()
        header.setMinimumSectionSize(52)
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        # Kolona "Rata" (index 2) - minimalna širina
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(2, 68)

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

            amount_item = create_numeric_item(row.amount, " EUR")
            amount_item.setForeground(QColor("#059669"))
            table.setItem(i, 3, amount_item)

            date_item = QTableWidgetItem(row.payment_date.strftime("%d.%m.%Y."))
            date_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            table.setItem(i, 4, date_item)

        # Ažuriraj badge
        if hasattr(self, "_badge_payments") and self._badge_payments:
            self._badge_payments.setText(str(len(rows)))

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

            table.setItem(i, 3, create_numeric_item(row.paid_amount, " EUR"))

            remaining_item = create_numeric_item(row.remaining_amount, " EUR")
            if row.remaining_amount > 0:
                remaining_item.setForeground(QColor("#dc2626"))
            table.setItem(i, 4, remaining_item)

            due_item = QTableWidgetItem(row.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
            table.setItem(i, 5, due_item)


        # Ažuriraj badge
        if hasattr(self, "_badge_month") and self._badge_month:
            self._badge_month.setText(str(len(rows)))

    def _load_dashboard_data(self) -> None:
        """Učitava sve podatke za dashboard koristeći background worker."""
        # Zaštita od višestrukog pokretanja
        if self._worker and self._worker.isRunning():
            return

        # Prikaži loading, sakrij tabele dok se učitava
        self._set_loading_state(True)

        self._worker = LoadDashboardWorker()
        self._worker.finished.connect(self._on_dashboard_loaded)
        self._worker.error.connect(self._on_dashboard_error)
        self._worker.start()

    def _set_loading_state(self, loading: bool) -> None:
        """Postavlja UI u loading stanje."""
        super()._set_loading_state(loading)
        
        if loading:
            self._loading_label.show()
            # Disable interakciju sa tabelama tokom učitavanja
            if hasattr(self, "payments_table"):
                self.payments_table.setEnabled(False)
            if hasattr(self, "month_table"):
                self.month_table.setEnabled(False)
        else:
            self._loading_label.hide()
            if hasattr(self, "payments_table"):
                self.payments_table.setEnabled(True)
            if hasattr(self, "month_table"):
                self.month_table.setEnabled(True)

    def _on_dashboard_loaded(self, data: DashboardData) -> None:
        """Handler za završetak učitavanja dashboarda."""
        self._set_loading_state(False)

        # RED 1: KPI-jevi
        for i, kpi in enumerate(data.kpis):
            if i < len(self.kpi_cards):
                self._update_kpi_card_data(self.kpi_cards[i], kpi)

        # RED 2: Status KPI-jevi
        self._update_status_cards(data.status_kpis)

        # RED 3: Tabele
        if hasattr(self, "payments_table"):
            self._populate_payments_table(self.payments_table, data.recent_payments)

        if hasattr(self, "month_table"):
            self._populate_month_table(self.month_table, data.current_month_installments)

    def _on_dashboard_error(self, error_msg: str) -> None:
        """Handler za grešku prilikom učitavanja dashboarda."""
        self._set_loading_state(False)
        self._show_error_message(
            "Greška pri učitavanju",
            f"Neuspješno učitavanje podataka:\n{error_msg}"
        )

    def _load_tables(self) -> None:
        """Učitava podatke za tabele (legacy method - više se ne koristi)."""
        # Ova metoda je zadržana za kompatibilnost, ali se ne koristi
        pass

    def on_activate(self) -> None:
        """Osvježava podatke kada se stranica aktivira."""
        super().on_activate()
        self._load_dashboard_data()
