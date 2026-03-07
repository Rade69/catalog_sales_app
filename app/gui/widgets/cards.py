from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class KpiCard(QFrame):
    def __init__(self, title: str, value: str, footer: str = "") -> None:
        super().__init__()
        self.setProperty("card", True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setProperty("kpiTitle", True)

        value_label = QLabel(value)
        value_label.setProperty("kpiValue", True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        if footer:
            footer_label = QLabel(footer)
            footer_label.setStyleSheet("color: #6b7280;")
            layout.addWidget(footer_label)
