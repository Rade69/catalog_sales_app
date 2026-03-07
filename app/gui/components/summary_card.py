"""
SummaryCard - KPI / Summary kartica za prikaz ključnih podataka.

Koristi se za dashboard KPI-jeve, statistike i slične prikaze.
"""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class SummaryCard(QFrame):
    """
    Kartica za prikaz summary / KPI podataka.
    
    Primjer korištenja:
        card = SummaryCard(
            title="Ukupan broj kupaca",
            value="248",
            footer="+12 ovaj mjesec",
            icon="👥"
        )
    """

    def __init__(
        self,
        title: str = "",
        value: str = "",
        footer: str = "",
        icon: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setObjectName("SummaryCard")

        # Glavni layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        # Icon + Title row
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        # Icon (ako postoji)
        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setStyleSheet("font-size: 24px;")
            title_layout.addWidget(self.icon_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setProperty("kpiTitle", True)
        self.title_label.setStyleSheet("""
            color: #6b7280;
            font-size: 13px;
            font-weight: 600;
        """)
        self.title_label.setWordWrap(True)
        title_layout.addWidget(self.title_label)

        layout.addLayout(title_layout)

        # Value (glavna vrijednost)
        self.value_label = QLabel(value)
        self.value_label.setProperty("kpiValue", True)
        self.value_label.setStyleSheet("""
            color: #111827;
            font-size: 32px;
            font-weight: 800;
        """)
        layout.addWidget(self.value_label)

        # Footer (opciono)
        if footer:
            self.footer_label = QLabel(footer)
            self.footer_label.setStyleSheet("""
                color: #9ca3af;
                font-size: 12px;
            """)
            self.footer_label.setWordWrap(True)
            layout.addWidget(self.footer_label)
        else:
            self.footer_label = None

        # Stretch da sadržaj bude na vrhu
        layout.addStretch(1)

    # -------------------------------------------------------------------------
    # Setteri za ažuriranje podataka
    # -------------------------------------------------------------------------

    def set_title(self, title: str) -> None:
        """Ažurira naslov kartice."""
        self.title_label.setText(title)

    def set_value(self, value: str) -> None:
        """Ažurira glavnu vrijednost."""
        self.value_label.setText(value)

    def set_footer(self, footer: str) -> None:
        """Ažurira footer tekst."""
        if self.footer_label:
            self.footer_label.setText(footer)
        elif footer:
            # Kreiraj footer label ako ga nema
            self.footer_label = QLabel(footer)
            self.footer_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
            self.layout().insertWidget(3, self.footer_label)

    def set_icon(self, icon: str) -> None:
        """Ažurira ikonicu."""
        if hasattr(self, "icon_label"):
            self.icon_label.setText(icon)
