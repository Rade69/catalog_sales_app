"""
EmptyStateWidget - Widget za prikaz praznog stanja kad nema podataka.

Koristi se u tabelama i listama kad nema podataka za prikaz.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class EmptyStateWidget(QWidget):
    """
    Widget za prikaz praznog stanja.
    
    Primjer korištenja:
        empty_widget = EmptyStateWidget("Nema kupaca za prikaz")
        table.setCellWidget(0, 0, empty_widget)
    """

    def __init__(
        self,
        message: str = "Nema podataka za prikaz",
        icon: str = "📭",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        
        # Glavni layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]

        # Ikonica
        self.icon_label = QLabel(icon)
        self.icon_label.setStyleSheet("""
            font-size: 48px;
            color: #d1d5db;
        """)
        self.icon_label.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        layout.addWidget(self.icon_label)

        # Poruka
        self.message_label = QLabel(message)
        self.message_label.setStyleSheet("""
            color: #9ca3af;
            font-size: 14px;
            font-style: italic;
        """)
        self.message_label.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

    def set_message(self, message: str) -> None:
        """Ažurira poruku."""
        self.message_label.setText(message)

    def set_icon(self, icon: str) -> None:
        """Ažurira ikonicu."""
        self.icon_label.setText(icon)
