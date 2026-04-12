"""
Paginacioni widget za QTableWidget.

Omogućava paginaciju velikih skupova podataka sa kontrolama za navigaciju,
prikazom trenutne stranice i ukupnog broja zapisa.
"""

from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
    QComboBox,
)


class PaginationWidget(QWidget):
    """
    Paginacioni widget sa kontrolama za navigaciju kroz stranice.
    
    Emituje signal `page_changed` kada se promijeni stranica.
    
    Atributi:
        page_size: Broj zapisa po stranici (default: 50)
        current_page: Trenutna stranica (1-based)
        total_items: Ukupan broj zapisa
        total_pages: Ukupan broj stranica
    """
    
    page_changed = Signal(int, int)  # (page_number, page_size)
    
    # Predefinisane opcije za broj zapisa po stranici
    PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250, 500]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._total_items = 0
        self._current_page = 1
        self._page_size = 50
        self._total_pages = 1
        
        self._setup_ui()
        self._update_display()
    
    def _setup_ui(self) -> None:
        """Inicijalizuje UI komponente."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(10)
        
        # Label za prikaz ukupnog broja zapisa
        self.total_label = QLabel("Ukupno: 0")
        self.total_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.total_label)
        
        layout.addStretch(1)
        
        # Dugme za prvu stranicu
        self.first_btn = QPushButton("<<")
        self.first_btn.setFixedWidth(30)
        self.first_btn.clicked.connect(self._go_to_first)
        layout.addWidget(self.first_btn)
        
        # Dugme za prethodnu stranicu
        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.clicked.connect(self._go_to_prev)
        layout.addWidget(self.prev_btn)
        
        # SpinBox za broj stranice
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setFixedWidth(60)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        layout.addWidget(self.page_spin)
        
        # Label za ukupan broj stranica
        self.pages_label = QLabel("/ 1")
        layout.addWidget(self.pages_label)
        
        # Dugme za sljedeću stranicu
        self.next_btn = QPushButton(">")
        self.next_btn.setFixedWidth(30)
        self.next_btn.clicked.connect(self._go_to_next)
        layout.addWidget(self.next_btn)
        
        # Dugme za posljednju stranicu
        self.last_btn = QPushButton(">>")
        self.last_btn.setFixedWidth(30)
        self.last_btn.clicked.connect(self._go_to_last)
        layout.addWidget(self.last_btn)
        
        layout.addStretch(1)
        
        # Label za broj zapisa po stranici
        page_size_label = QLabel("Zapisa po stranici:")
        layout.addWidget(page_size_label)
        
        # ComboBox za odabir broja zapisa po stranici
        self.page_size_combo = QComboBox()
        for size in self.PAGE_SIZE_OPTIONS:
            self.page_size_combo.addItem(str(size), size)
        
        # Pronađi trenutnu vrijednost u opcijama ili dodaj je
        current_index = self.page_size_combo.findData(self._page_size)
        if current_index >= 0:
            self.page_size_combo.setCurrentIndex(current_index)
        else:
            self.page_size_combo.addItem(str(self._page_size), self._page_size)
            self.page_size_combo.setCurrentIndex(self.page_size_combo.count() - 1)
        
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        self.page_size_combo.setFixedWidth(80)
        layout.addWidget(self.page_size_combo)
    
    def _update_display(self) -> None:
        """Ažurira prikaz paginacionih kontrola."""
        # Ažuriraj ukupan broj zapisa
        self.total_label.setText(f"Ukupno: {self._total_items}")
        
        # Ažuriraj broj stranica
        self._total_pages = max(1, (self._total_items + self._page_size - 1) // self._page_size)
        self.pages_label.setText(f"/ {self._total_pages}")
        
        # Ažuriraj SpinBox
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(self._total_pages)
        self.page_spin.setValue(self._current_page)
        self.page_spin.blockSignals(False)
        
        # Omogući/onemogući dugmiće za navigaciju
        self.first_btn.setEnabled(self._current_page > 1)
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._total_pages)
        self.last_btn.setEnabled(self._current_page < self._total_pages)
    
    def _go_to_first(self) -> None:
        """Idi na prvu stranicu."""
        if self._current_page != 1:
            self._current_page = 1
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _go_to_prev(self) -> None:
        """Idi na prethodnu stranicu."""
        if self._current_page > 1:
            self._current_page -= 1
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _go_to_next(self) -> None:
        """Idi na sljedeću stranicu."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _go_to_last(self) -> None:
        """Idi na posljednju stranicu."""
        if self._current_page != self._total_pages:
            self._current_page = self._total_pages
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _on_page_spin_changed(self, value: int) -> None:
        """Rukuje promjenom stranice preko SpinBox-a."""
        if value != self._current_page:
            self._current_page = value
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def _on_page_size_changed(self, index: int) -> None:
        """Rukuje promjenom broja zapisa po stranici."""
        new_size = self.page_size_combo.itemData(index)
        if new_size != self._page_size:
            self._page_size = new_size
            # Resetuj na prvu stranicu kada se promijeni page_size
            self._current_page = 1
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def set_total_items(self, total_items: int) -> None:
        """
        Postavi ukupan broj zapisa.
        
        Args:
            total_items: Ukupan broj zapisa u bazi
        """
        if total_items < 0:
            total_items = 0
        
        self._total_items = total_items
        
        # Ako je trenutna stranica veća od ukupnog broja stranica,
        # resetuj na posljednju stranicu
        if self._current_page > self._total_pages:
            self._current_page = max(1, self._total_pages)
        
        self._update_display()
    
    def set_page_size(self, page_size: int) -> None:
        """
        Postavi broj zapisa po stranici.
        
        Args:
            page_size: Broj zapisa po stranici (mora biti > 0)
        """
        if page_size <= 0:
            return
        
        self._page_size = page_size
        
        # Dodaj opciju ako ne postoji
        index = self.page_size_combo.findData(page_size)
        if index < 0:
            self.page_size_combo.addItem(str(page_size), page_size)
            index = self.page_size_combo.count() - 1
        
        self.page_size_combo.setCurrentIndex(index)
        
        # Resetuj na prvu stranicu
        self._current_page = 1
        self._update_display()
    
    def set_current_page(self, page: int) -> None:
        """
        Postavi trenutnu stranicu.
        
        Args:
            page: Broj stranice (1-based)
        """
        if 1 <= page <= self._total_pages and page != self._current_page:
            self._current_page = page
            self._update_display()
            self.page_changed.emit(self._current_page, self._page_size)
    
    def reset(self) -> None:
        """Resetuj paginaciju na početno stanje."""
        self._total_items = 0
        self._current_page = 1
        self._page_size = 50
        self._update_display()
    
    def get_current_page(self) -> int:
        """Vrati trenutnu stranicu (1-based)."""
        return self._current_page
    
    def get_page_size(self) -> int:
        """Vrati broj zapisa po stranici."""
        return self._page_size
    
    def get_total_items(self) -> int:
        """Vrati ukupan broj zapisa."""
        return self._total_items
    
    def get_total_pages(self) -> int:
        """Vrati ukupan broj stranica."""
        return self._total_pages
    
    def get_offset(self) -> int:
        """Vrati offset za SQL upit (0-based)."""
        return (self._current_page - 1) * self._page_size
    
    def get_limit(self) -> int:
        """Vrati limit za SQL upit."""
        return self._page_size
    
    def is_first_page(self) -> bool:
        """Da li je trenutna stranica prva."""
        return self._current_page == 1
    
    def is_last_page(self) -> bool:
        """Da li je trenutna stranica posljednja."""
        return self._current_page == self._total_pages
    
    def has_data(self) -> bool:
        """Da li ima podataka za prikaz."""
        return self._total_items > 0