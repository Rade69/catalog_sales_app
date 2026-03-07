APP_STYLESHEET = """
QWidget {
    background: #f6f7fb;
    color: #1f2937;
    font-family: 'Segoe UI', 'Arial';
    font-size: 13px;
}
QMainWindow {
    background: #f6f7fb;
}
#Sidebar {
    background: #111827;
    border-radius: 16px;
}
#SidebarTitle {
    color: #111827;
    font-size: 18px;
    font-weight: 700;
    padding: 10px 12px;
    background: #f3f4f6;
    border-radius: 10px;
}
#TopBar {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
}
#PageTitle {
    font-size: 22px;
    font-weight: 700;
}
#PageSubtitle {
    color: #6b7280;
    font-size: 13px;
}
#ContentArea {
    background: transparent;
}
QFrame[card="true"] {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
}
QLabel[sectionTitle="true"] {
    font-size: 16px;
    font-weight: 700;
}
QTableWidget {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    gridline-color: #eef2f7;
}
QHeaderView::section {
    background: #f3f4f6;
    border: none;
    padding: 10px;
    font-weight: 700;
}
QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {
    background: white;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 8px 10px;
}
QPushButton[primary="true"] {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 700;
}
QPushButton[secondary="true"] {
    background: white;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 700;
}
"""
