from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt


STATUS_CONFIG = {
    # status: (display_text, background_color, text_color)
    "paid":           ("PLAĆENO",    "#dcfce7", "#166534"),  # zelena
    "overdue":        ("KASNI",      "#fee2e2", "#991b1b"),  # crvena
    "partially_paid": ("DJELIMIČNO", "#fef3c7", "#92400e"),  # žuta
    "pending":        ("ČEKA",       "#f3f4f6", "#6b7280"),  # siva
    "active":         ("AKTIVAN",    "#dbeafe", "#1e40af"),  # plava
    "cancelled":      ("OTKAZAN",    "#f3f4f6", "#374151"),  # siva
    "completed":      ("ZAVRŠENO",   "#dcfce7", "#166534"),  # zelena
}


def make_status_badge(status: str) -> QLabel:
    """
    Kreira QLabel badge za prikaz statusa.
    
    Args:
        status: Status string (npr. "paid", "overdue", "pending")
    
    Returns:
        QLabel sa stilizovanim badge-om
    """
    # Default za nepoznate statuse
    display_text, bg_color, text_color = STATUS_CONFIG.get(
        status.lower(),
        (status.upper(), "#f3f4f6", "#6b7280")
    )
    
    badge = QLabel(display_text)
    badge.setAlignment(Qt.AlignCenter)
    badge.setStyleSheet(f"""
        QLabel {{
            background-color: {bg_color};
            color: {text_color};
            font-weight: bold;
            font-size: 11px;
            border-radius: 12px;
            padding: 4px 10px;
            min-width: 80px;
        }}
    """)
    
    return badge


def get_status_colors(status: str) -> tuple[str, str]:
    """
    Vraća boje za status (background, text).
    
    Korisno za bojanje redova u tabelama.
    """
    config = STATUS_CONFIG.get(status.lower(), (None, "#f3f4f6", "#6b7280"))
    return config[1], config[2]
