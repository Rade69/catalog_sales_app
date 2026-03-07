"""
StatusBadge - Badge za prikaz statusa sa bojama.

Koristi se za vizuelno označavanje statusa u tabelama i karticama.
"""

from enum import Enum
from typing import Optional

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt


class StatusType(str, Enum):
    """Tipovi statusa sa bojama."""
    SUCCESS = "success"      # Zelena - plaćeno, aktivno
    WARNING = "warning"      # Žuta - djelimično, na čekanju
    DANGER = "danger"        # Crvena - kasni, otkazano
    INFO = "info"            # Plava - aktivna kampanja
    NEUTRAL = "neutral"      # Siva - pending, arhivirano


# Konfiguracija boja za svaki status
STATUS_CONFIG = {
    # status: (display_text, background_color, text_color)
    StatusType.SUCCESS: ("PLAĆENO", "#dcfce7", "#166534"),
    StatusType.WARNING: ("DJELIMIČNO", "#fef3c7", "#92400e"),
    StatusType.DANGER: ("KASNI", "#fee2e2", "#991b1b"),
    StatusType.INFO: ("AKTIVAN", "#dbeafe", "#1e40af"),
    StatusType.NEUTRAL: ("ČEKA", "#f3f4f6", "#6b7280"),
}

# Alias za lakše korištenje
STATUS_ALIASES = {
    "paid": StatusType.SUCCESS,
    "completed": StatusType.SUCCESS,
    "active": StatusType.INFO,
    "overdue": StatusType.DANGER,
    "cancelled": StatusType.DANGER,
    "partially_paid": StatusType.WARNING,
    "pending": StatusType.NEUTRAL,
    "draft": StatusType.NEUTRAL,
    "archived": StatusType.NEUTRAL,
}


class StatusBadge(QLabel):
    """
    Badge za prikaz statusa.
    
    Primjer korištenja:
        badge = StatusBadge("paid")
        # ili
        badge = StatusBadge(StatusType.SUCCESS, custom_text="Završeno")
    """

    def __init__(
        self,
        status: str | StatusType = StatusType.NEUTRAL,
        custom_text: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        
        # Odredi tip statusa
        if isinstance(status, str):
            status_type = STATUS_ALIASES.get(status.lower(), StatusType.NEUTRAL)
        else:
            status_type = status
        
        # Dohvati konfiguraciju
        config = STATUS_CONFIG.get(status_type, STATUS_CONFIG[StatusType.NEUTRAL])
        
        # Tekst (custom ili iz konfiguracije)
        display_text = custom_text if custom_text else config[0]
        bg_color = config[1]
        text_color = config[2]
        
        # Stil badge-a
        self.setAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                font-weight: bold;
                font-size: 11px;
                border-radius: 12px;
                padding: 4px 12px;
                min-width: 70px;
            }}
        """)
        
        self.setText(display_text)

    @staticmethod
    def from_status_string(status: str) -> "StatusBadge":
        """
        Kreira badge iz string statusa.
        
        Args:
            status: String statusa (npr. "paid", "overdue", "pending")
        
        Returns:
            StatusBadge instanca
        """
        return StatusBadge(status)

    @staticmethod
    def from_status_type(status_type: StatusType, custom_text: Optional[str] = None) -> "StatusBadge":
        """
        Kreira badge iz StatusType enum-a.
        
        Args:
            status_type: Tip statusa
            custom_text: Opcioni custom tekst
        
        Returns:
            StatusBadge instanca
        """
        return StatusBadge(status_type, custom_text)
