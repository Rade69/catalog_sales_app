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
}
#SidebarTitle {
    color: white;
    font-size: 18px;
    font-weight: 700;
    padding: 10px 12px;
}
QPushButton[nav="true"] {
    background: transparent;
    color: #f9fafb;
    border: none;
    text-align: left;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton[nav="true"]:hover {
    background: #1f2937;
    color: white;
}
QPushButton[nav="true"][active="true"] {
    background: #2563eb;
    color: white;
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
QLabel[kpiTitle="true"] {
    color: #6b7280;
    font-size: 12px;
    font-weight: 600;
}
QLabel[kpiValue="true"] {
    color: #111827;
    font-size: 28px;
    font-weight: 800;
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
