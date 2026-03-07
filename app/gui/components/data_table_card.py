"""
DataTableCard - Kartica sa tabelom za prikaz podataka.

Koristi se za prikaz tabularnih podataka sa konzistentnim stilom.
"""

from typing import List, Optional

from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class DataTableCard(QFrame):
    """
    Kartica sa tabelom za prikaz podataka.
    
    Primjer korištenja:
        table_card = DataTableCard(
            title="Postojeće narudžbe",
            columns=["ID", "Kupac", "Proizvod", "Cijena", "Status"],
            column_resize_modes=["fixed", "stretch", "stretch", "resize", "fixed"],
        )
        table_card.add_button("🔄 Osvježi", on_refresh_clicked)
    """

    def __init__(
        self,
        title: str = "",
        columns: Optional[List[str]] = None,
        column_resize_modes: Optional[List[str]] = None,
        show_refresh_button: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setObjectName("DataTableCard")

        # Glavni layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header sa naslovom i opcionalnim dugmetom
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel(title)
        self.title_label.setProperty("sectionTitle", True)
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch(1)
        
        # Refresh dugme (opciono)
        if show_refresh_button:
            self.refresh_btn = QPushButton("🔄 Osvježi")
            self.refresh_btn.setProperty("secondary", True)
            header_layout.addWidget(self.refresh_btn)
        else:
            self.refresh_btn = None
        
        layout.addLayout(header_layout)

        # Tabela
        self.table = QTableWidget()
        if columns:
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            
            # Postavi resize mode za svaku kolonu
            header = self.table.horizontalHeader()
            if column_resize_modes:
                for i, mode in enumerate(column_resize_modes):
                    if i < len(column_resize_modes):
                        if mode == "stretch":
                            header.setSectionResizeMode(i, QHeaderView.Stretch)
                        elif mode == "resize":
                            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                        elif mode == "fixed":
                            header.setSectionResizeMode(i, QHeaderView.Fixed)
            else:
                # Default: zadnja kolona stretch, ostale resize
                for i in range(len(columns) - 1):
                    header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(len(columns) - 1, QHeaderView.Stretch)
        
        # Stil tabele
        self.table.setProperty("card", True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[arg-type]
        self.table.setSelectionMode(QTableWidget.SingleSelection)  # type: ignore[arg-type]
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[arg-type]
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        layout.addWidget(self.table)

    # -------------------------------------------------------------------------
    # Helper metodi
    # -------------------------------------------------------------------------

    def add_button(self, text: str, callback) -> QPushButton:
        """Dodaje dugme u header i povezuje callback."""
        if self.refresh_btn:
            self.refresh_btn.setText(text)
            self.refresh_btn.clicked.connect(callback)
        return self.refresh_btn if self.refresh_btn else QPushButton()

    def set_data(
        self,
        rows: List[List],
        column_types: Optional[List[str]] = None,
    ) -> None:
        """
        Postavlja podatke u tabelu.
        
        Args:
            rows: Lista redova, svaki red je lista vrijednosti
            column_types: Tipovi kolona ("text", "numeric", "center", "status")
        """
        if not rows:
            self.show_empty_state("Nema podataka za prikaz")
            return
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                if col_idx < self.table.columnCount():
                    item = self._create_table_item(value, column_types, col_idx)
                    self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()

    def _create_table_item(
        self,
        value,
        column_types: Optional[List[str]],
        col_idx: int,
    ) -> QTableWidgetItem:
        """Kreira QTableWidgetItem sa odgovarajućim stilom."""
        item = QTableWidgetItem(str(value) if value is not None else "")
        
        # Odredi tip kolone
        col_type = None
        if column_types and col_idx < len(column_types):
            col_type = column_types[col_idx]
        
        # Postavi alignment
        if col_type == "numeric":
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[arg-type]
        elif col_type == "center":
            item.setTextAlignment(Qt.AlignCenter)  # type: ignore[arg-type]
        
        return item

    def show_empty_state(self, message: str = "Nema podataka za prikaz") -> None:
        """Prikazuje poruku kad nema podataka."""
        from app.gui.components.empty_state_widget import EmptyStateWidget
        
        self.table.setRowCount(1)
        empty_widget = EmptyStateWidget(message)
        self.table.setCellWidget(0, 0, empty_widget)
        self.table.setSpan(0, 0, 1, self.table.columnCount())

    def clear(self) -> None:
        """Čisti tabelu."""
        self.table.setRowCount(0)

    def get_selected_row_index(self) -> int:
        """Vraća indeks selektovanog reda ili -1 ako nema selekcije."""
        return self.table.currentRow()

    def get_selected_row_data(self) -> Optional[dict]:
        """Vraća podatke selektovanog reda kao dictionary."""
        row = self.get_selected_row_index()
        if row < 0:
            return None
        
        data = {}
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col)
            key = header.text() if header else f"col_{col}"
            item = self.table.item(row, col)
            data[key] = item.text() if item else ""
        return data
