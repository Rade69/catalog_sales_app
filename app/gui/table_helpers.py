"""
Table Helpers - Zajedničke funkcije za QTableWidget

Pruža konzistentan stil i ponašanje za sve tabele u aplikaciji.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.status_badge import StatusBadge


# -----------------------------------------------------------------------------
# Table Styling
# -----------------------------------------------------------------------------

def style_table(table: QTableWidget) -> None:
    """
    Primjenjuje konzistentan stil na QTableWidget.

    - Povećana visina reda (36px)
    - Padding u ćelijama
    - Header sa sivom pozadinom i bold tekstom
    - Hover efekat na redove
    - Alternating row colors
    """
    # Osnovne postavke
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    
    # Visina reda
    table.verticalHeader().setDefaultSectionSize(36)
    
    # Header stil
    header = table.horizontalHeader()
    header.setStyleSheet("""
        QHeaderView::section {
            background-color: #f3f4f6;
            color: #111827;
            font-weight: 700;
            font-size: 14px;
            padding: 12px 8px;
            border: none;
            border-bottom: 2px solid #e5e7eb;
        }
    """)

    # Hover efekat (koristi stylesheet za cijelu tabelu)
    table.setStyleSheet("""
        QTableWidget {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            gridline-color: #eef2f7;
            font-size: 16px;
        }
        QTableWidget::item {
            padding: 8px;
            color: #1f2937;
            background-color: transparent;
        }
        QTableWidget::item:alternate {
            background-color: #f9fafb;
        }
        QTableWidget::item:hover {
            background-color: #f3f4f6;
        }
        QTableWidget::item:selected {
            background-color: #dbeafe;
            color: #1e40af;
        }
    """)


def set_column_resize_mode(
    table: QTableWidget,
    column_modes: list[tuple[int, QHeaderView.ResizeMode]]
) -> None:
    """
    Postavlja resize mode za određene kolone.

    Args:
        table: QTableWidget
        column_modes: Lista tupli (column_index, ResizeMode)
    """
    header = table.horizontalHeader()
    for col_idx, mode in column_modes:
        header.setSectionResizeMode(col_idx, mode)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# Table Items
# -----------------------------------------------------------------------------

def create_table_item(
    text: str,
    align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter,
    bold: bool = False,
    color: str | None = None,
    numeric: bool = False
) -> QTableWidgetItem:
    """
    Kreira QTableWidgetItem sa stilom.

    Args:
        text: Tekst za prikaz
        align: Poravnanje (default: lijevo)
        bold: Da li je tekst bold
        color: Boja teksta (HEX)
        numeric: Da li je numerička vrijednost (desno poravnanje)

    Returns:
        QTableWidgetItem
    """
    item = QTableWidgetItem(text)
    
    # Poravnanje
    if numeric:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    else:
        item.setTextAlignment(align)
    
    # Bold
    if bold:
        font = item.font()
        font.setBold(True)
        item.setFont(font)
    
    # Boja
    if color:
        item.setForeground(QColor(color))
    
    return item


def create_numeric_item(value: float | int | None, suffix: str = "") -> QTableWidgetItem:
    """
    Kreira QTableWidgetItem za numeričke vrijednosti (desno poravnato).

    Args:
        value: Numerička vrijednost
        suffix: Sufiks (npr. " EUR")

    Returns:
        QTableWidgetItem
    """
    if value is None:
        item = QTableWidgetItem("—")
    else:
        formatted = f"{value:.2f}{suffix}" if suffix else f"{value:.2f}"
        item = QTableWidgetItem(formatted)
    
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def create_status_item(status: str) -> StatusBadge:
    """
    Kreira status badge widget.

    Args:
        status: Status string (paid, overdue, pending, etc.)

    Returns:
        StatusBadge widget
    """
    return StatusBadge(status)


# -----------------------------------------------------------------------------
# Empty State
# -----------------------------------------------------------------------------

def show_empty_state(table: QTableWidget, message: str = "Nema podataka za prikaz") -> None:
    """
    Prikazuje empty state poruku u tabeli.

    Args:
        table: QTableWidget
        message: Poruka za prikaz
    """
    from app.gui.components.empty_state_widget import EmptyStateWidget
    
    table.setRowCount(1)
    empty_widget = EmptyStateWidget(message)
    table.setCellWidget(0, 0, empty_widget)
    table.setSpan(0, 0, 1, table.columnCount())


def clear_table(table: QTableWidget) -> None:
    """
    Briše sve redove iz tabele.

    Args:
        table: QTableWidget
    """
    table.setRowCount(0)


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------

def setup_basic_table(
    table: QTableWidget,
    headers: list[str],
    column_modes: list[tuple[int, QHeaderView.ResizeMode]] | None = None
) -> None:
    """
    Postavlja osnovnu konfiguraciju tabele.

    Args:
        table: QTableWidget
        headers: Liste header-a
        column_modes: Opcionalna lista (col_index, ResizeMode)
    """
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    style_table(table)
    
    if column_modes:
        set_column_resize_mode(table, column_modes)


def populate_table_with_data(
    table: QTableWidget,
    rows: list[list],
    column_types: list[str] | None = None,
    empty_message: str = "Nema podataka za prikaz"
) -> None:
    """
    Popunjava tabelu sa podacima.

    Args:
        table: QTableWidget
        rows: Lista redova (svaki red je lista vrijednosti)
        column_types: Tipovi kolona ('text', 'numeric', 'status')
        empty_message: Poruka za praznu tabelu
    """
    clear_table(table)
    
    if not rows:
        show_empty_state(table, empty_message)
        return
    
    table.setRowCount(len(rows))
    
    for row_idx, row_data in enumerate(rows):
        for col_idx, value in enumerate(row_data):
            col_type = column_types[col_idx] if column_types else 'text'
            
            if col_type == 'numeric':
                item = create_numeric_item(value if isinstance(value, (int, float)) else None)
            elif col_type == 'status':
                table.setCellWidget(row_idx, col_idx, create_status_item(str(value)))
                continue
            else:
                item = create_table_item(str(value) if value is not None else "—")
            
            table.setItem(row_idx, col_idx, item)
