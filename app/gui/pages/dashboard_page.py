from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.cards import KpiCard


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        cards = QGridLayout()
        cards.setHorizontalSpacing(16)
        cards.setVerticalSpacing(16)
        cards.addWidget(KpiCard("Ukupno kupaca", "248", "+12 ovaj mjesec"), 0, 0)
        cards.addWidget(KpiCard("Aktivne narudžbe", "91", "7 novih"), 0, 1)
        cards.addWidget(KpiCard("Rate koje kasne", "14", "Prioritet za naplatu"), 0, 2)
        cards.addWidget(KpiCard("Ukupan dug", "12.480 KM", "Aktivna potraživanja"), 0, 3)
        root.addLayout(cards)

        bottom = QHBoxLayout()
        bottom.setSpacing(16)

        left_card = QFrame()
        left_card.setProperty("card", True)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Rate za naplatu")
        title.setProperty("sectionTitle", True)
        left_layout.addWidget(title)

        table = QTableWidget(5, 4)
        table.setHorizontalHeaderLabels(["Kupac", "Artikal", "Rata", "Iznos"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        data = [
            ("Milica Petrović", "Blender Philips", "3/5", "20 KM"),
            ("Jelena Savić", "Tava set", "2/4", "35 KM"),
            ("Marko Ilić", "Mikser Bosch", "1/6", "25 KM"),
            ("Slađana Marić", "Pegla Tefal", "4/8", "18 KM"),
            ("Dejan Lazić", "Usisivač Gorenje", "5/10", "42 KM"),
        ]
        for r, row in enumerate(data):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(r, c, item)
        table.horizontalHeader().setStretchLastSection(True)
        left_layout.addWidget(table)

        right_card = QFrame()
        right_card.setProperty("card", True)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)
        title2 = QLabel("Šta sam zamislio u prvoj verziji")
        title2.setProperty("sectionTitle", True)
        right_layout.addWidget(title2)

        for text in [
            "1. Kampanja se uvozi iz Excel fajla i kreira mjesečni katalog.",
            "2. Kupac se bira ili kreira iz modula Kupci.",
            "3. Narudžba čuva snapshot cijene i naziva proizvoda.",
            "4. Broj rata automatski generiše plan otplate.",
            "5. Uplate se evidentiraju po rati i kasnije ulaze u izvještaj.",
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #374151;")
            right_layout.addWidget(lbl)
        right_layout.addStretch(1)

        bottom.addWidget(left_card, 2)
        bottom.addWidget(right_card, 1)
        root.addLayout(bottom)
