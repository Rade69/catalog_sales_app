"""
PageHeader - Header komponenta za stranice sa naslovom i podnaslovom.

Koristi se kao zaglavlje svake stranice u aplikaciji.
"""

from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class PageHeader(QFrame):
    """
    Header komponenta za stranice.
    
    Primjer korištenja:
        header = PageHeader(
            title="Kupci",
            subtitle="Baza kupaca, pretraga i unos u SQLite bazu.",
        )
    """

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        show_refresh: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageHeader")
        self.setProperty("topBar", True)

        # Glavni layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Naslov i podnaslov
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: #111827;
        """)
        title_layout.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("PageSubtitle")
            self.subtitle_label.setStyleSheet("""
                color: #6b7280;
                font-size: 14px;
            """)
            self.subtitle_label.setWordWrap(True)
            title_layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

        layout.addLayout(title_layout)

    # -------------------------------------------------------------------------
    # Setteri
    # -------------------------------------------------------------------------

    def set_title(self, title: str) -> None:
        """Ažurira naslov."""
        self.title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        """Ažurira podnaslov."""
        if self.subtitle_label:
            self.subtitle_label.setText(subtitle)
