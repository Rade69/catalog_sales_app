"""
SearchBar - Komponenta za pretragu sa placeholder-om i live search-om.

Koristi se za filtriranje tabela i lista.
"""

from PySide6.QtWidgets import QLineEdit, QWidget
from PySide6.QtCore import Signal


class SearchBar(QLineEdit):
    """
    Komponenta za pretragu.
    
    Primjer korištenja:
        search_bar = SearchBar(
            placeholder="🔍 Pretraži po imenu, telefonu...",
            on_search_changed=lambda text: print(f"Searching: {text}")
        )
    """

    # Signal za promjenu teksta (korisno za live search)
    search_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "🔍 Pretraga...",
        on_search_changed=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBar")
        
        # Placeholder
        self.setPlaceholderText(placeholder)
        
        # Stil
        self.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: #1f2937;
            }
            QLineEdit:focus {
                border-color: #2563eb;
                outline: none;
            }
            QLineEdit:hover {
                border-color: #9ca3af;
            }
        """)
        
        # Poveži signal
        self.textChanged.connect(self.search_changed.emit)
        if on_search_changed:
            self.search_changed.connect(on_search_changed)

    def clear_search(self) -> None:
        """Čisti pretragu."""
        self.clear()

    def get_search_text(self) -> str:
        """Vraća trenutni tekst pretrage."""
        return self.text().strip()
