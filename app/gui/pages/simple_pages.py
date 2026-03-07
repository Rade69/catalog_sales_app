from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CrudPreviewPage(QWidget):
    def __init__(self, title: str, form_labels: list[str], table_headers: list[str], sample_rows: list[list[str]]) -> None:
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        form_card = QFrame()
        form_card.setProperty("card", True)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(12)

        form_title = QLabel(f"{title} — unos / izmjena")
        form_title.setProperty("sectionTitle", True)
        form_layout.addWidget(form_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for i, label in enumerate(form_labels):
            lbl = QLabel(label)
            inp = QLineEdit()
            inp.setPlaceholderText(label)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(inp, i, 1)
        form_layout.addLayout(grid)

        btns = QHBoxLayout()
        save = QPushButton("Sačuvaj")
        save.setProperty("primary", True)
        cancel = QPushButton("Otkaži")
        cancel.setProperty("secondary", True)
        btns.addWidget(save)
        btns.addWidget(cancel)
        form_layout.addLayout(btns)
        form_layout.addStretch(1)

        table_card = QFrame()
        table_card.setProperty("card", True)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(12)

        table_title = QLabel(f"{title} — pregled")
        table_title.setProperty("sectionTitle", True)
        table_layout.addWidget(table_title)

        table = QTableWidget(len(sample_rows), len(table_headers))
        table.setHorizontalHeaderLabels(table_headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setShowGrid(False)
        table.horizontalHeader().setStretchLastSection(True)
        for r, row in enumerate(sample_rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))
        table_layout.addWidget(table)

        root.addWidget(form_card, 1)
        root.addWidget(table_card, 2)
