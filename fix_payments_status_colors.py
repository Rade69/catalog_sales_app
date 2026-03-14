#!/usr/bin/env python3
"""
FIX 3: Statusi sa POZADINSKOM BOJOM (bez emoji-a koji možda ne rade).

Umjesto: ✅ PLAĆENO, 🔴 KASNI
Koristi: PLAĆENO (zelena pozadina), KASNI (crvena pozadina)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

payments_page_path = Path(__file__).resolve().parent / "app" / "gui" / "pages" / "payments_page.py"

with open(payments_page_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Zamijeni STATUS_ICONS sa jednostavnijim STATUS_COLORS
old_icons = '''        STATUS_ICONS = {
            "overdue":        ("🔴", "KASNI",      "#fee2e2", "#991b1b"),
            "partially_paid": ("🟡", "DJELIMIČNO", "#fef3c7", "#92400e"),
            "pending":        ("⏳", "ČEKA",       "#f3f4f6", "#6b7280"),
            "paid":           ("✅", "PLAĆENO",    "#dcfce7", "#166534"),
        }'''

new_colors = '''        STATUS_COLORS = {
            "overdue":        ("KASNI",      "#fee2e2", "#991b1b"),
            "partially_paid": ("DJELIMIČNO", "#fef3c7", "#92400e"),
            "pending":        ("ČEKA",       "#f3f4f6", "#6b7280"),
            "paid":           ("PLAĆENO",    "#dcfce7", "#166534"),
        }'''

if old_icons in content:
    content = content.replace(old_icons, new_colors)
    print("✅ Zamijenjen STATUS_ICONS sa STATUS_COLORS")
else:
    print("⚠️  Nije pronađen STATUS_ICONS")

# Zamijeni kreiranje status_item-a
old_item = '''            # Status badge sa ikonicom
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            icon, label, bg, fg = STATUS_ICONS.get(status_val, ("?", "?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(f"{icon} {label}")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 6, status_item)'''

new_item = '''            # Status badge (tekst sa obojenom pozadinom)
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            label, bg, fg = STATUS_COLORS.get(status_val, ("?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            
            # Podešavanje fonta (bold za važne statuse)
            font = status_item.font()
            if status_val in ("paid", "overdue"):
                font.setBold(True)
            status_item.setFont(font)
            
            self.installments_table.setItem(i, 6, status_item)'''

if old_item in content:
    content = content.replace(old_item, new_item)
    print("✅ Zamijenjen status_item (bez emoji-a)")
else:
    print("⚠️  Nije pronađen kod za status_item")

# Sačuvaj backup
backup_path = payments_page_path.with_suffix('.py.backup3')
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"\n💾 Backup 3: {backup_path}")

# Piši izmjene
with open(payments_page_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Izmijenjen payments_page.py (FIX 3)")

print("\n" + "="*70)
print("✅ FIX 3 ZAVRŠEN - STATUSI SA BOJAMA (BEZ EMOJI-A)")
print("="*70)
print("\n📊 IZGLED:")
print("   PLAĆENO    → zelena pozadina, bold")
print("   KASNI      → crvena pozadina, bold")
print("   DJELIMIČNO → žuta pozadina")
print("   ČEKA       → siva pozadina")
print()
print("🔄 TESTIRAJ:")
print("   python run.py")
print()
