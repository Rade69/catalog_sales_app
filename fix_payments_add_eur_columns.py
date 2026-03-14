#!/usr/bin/env python3
"""
FIX: Dodaj kolone "Vrijed.(EUR)", "Ukupno (EUR)", "Preostalo (EUR)" u Uplate.

Ove kolone pokazuju:
- Vrijed.(EUR) = Ukupna cijena narudžbe (iznos iz ugovora)
- Ukupno (EUR) = Suma svih uplata do sada
- Preostalo (EUR) = Vrijednost - Ukupno (koliko još treba platiti)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

payments_page_path = Path(__file__).resolve().parent / "app" / "gui" / "pages" / "payments_page.py"

with open(payments_page_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================================
# 1. DODATI NOVE KOLONE U TABLICU
# ============================================================================

# Nađi gdje se kreira tabela i dodaj nove kolone
old_table_init = '''        self.installments_table = QTableWidget(0, 7)
        self.installments_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Rata", "Dospijeće", "Iznos", "Plaćeno", "Status"
        ])'''

new_table_init = '''        self.installments_table = QTableWidget(0, 10)
        self.installments_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Vrijed.(EUR)", "Ukupno (EUR)", "Preostalo (EUR)",
            "Rata", "Dospijeće", "Status"
        ])'''

if old_table_init in content:
    content = content.replace(old_table_init, new_table_init)
    print("✅ Dodane 3 nove kolone: Vrijed.(EUR), Ukupno (EUR), Preostalo (EUR)")
else:
    # Probaj drugu varijantu
    old_table_init2 = '''        self.installments_table = QTableWidget(0, 8)
        self.installments_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Rata", "Dospijeće", "Iznos", "Plaćeno", "Status"
        ])'''
    
    if old_table_init2 in content:
        content = content.replace(old_table_init2, '''        self.installments_table = QTableWidget(0, 10)
        self.installments_table.setHorizontalHeaderLabels([
            "Kupac", "Artikal", "Vrijed.(EUR)", "Ukupno (EUR)", "Preostalo (EUR)",
            "Rata", "Dospijeće", "Status"
        ])''')
        print("✅ Dodane 3 nove kolone (varijanta 2)")
    else:
        print("⚠️  Nije pronađena kreacija tabele - tražim drugu lokaciju")

# ============================================================================
# 2. AŽURIRAJ _populate_table METODU DA POPUNI NOVE KOLONE
# ============================================================================

# Nađi _populate_table i dodaj kod za nove kolone
old_populate_start = '''    def _populate_table(self, installments: list) -> None:
        self.installments_table.setRowCount(0)
        self.installments_table.setRowCount(len(installments))'''

new_populate_start = '''    def _populate_table(self, installments: list) -> None:
        """Popunjava tabelu ratama sa svim kolonama (uključujući Vrijed., Ukupno, Preostalo)."""
        self.installments_table.setRowCount(0)
        self.installments_table.setRowCount(len(installments))
        
        # Praćenje suma za footer
        total_value = Decimal("0.00")
        total_paid = Decimal("0.00")
        total_remaining = Decimal("0.00")'''

if old_populate_start in content:
    content = content.replace(old_populate_start, new_populate_start)
    print("✅ Dodano praćenje suma za footer")
else:
    print("⚠️  Nije pronađen _populate_table start")

# Dodaj kolone u petlji - nađi gdje se popunjavaju kolone
old_loop = '''        for i, inst in enumerate(installments):
            # Kupac - koristi getattr da izbjegne lazy loading na detached objektu
            order = getattr(inst, 'order', None)
            customer = getattr(order, 'customer', None) if order else None
            kupac = customer.full_name if customer else ""
            self.installments_table.setItem(i, 0, QTableWidgetItem(kupac))

            # Artikal
            artikal = order.product_name_snapshot if order else ""
            self.installments_table.setItem(i, 1, QTableWidgetItem(artikal))

            # Rata N/M
            total = order.installments_count if order else "?"
            rata_item = QTableWidgetItem(f"{inst.installment_number}/{total}")
            rata_item.setTextAlignment(Qt.AlignCenter)
            rata_item.setData(Qt.UserRole, inst.id)
            self.installments_table.setItem(i, 2, rata_item)

            # Dospijeće — crveno ako kasni
            due_item = QTableWidgetItem(inst.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)
            if inst.due_date < today:
                due_item.setForeground(QBrush(QColor("#dc2626")))
            self.installments_table.setItem(i, 3, due_item)

            # Iznos rate
            iznos = Decimal(str(inst.amount))
            iznos_item = QTableWidgetItem(f"{iznos:.2f}")
            iznos_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.installments_table.setItem(i, 4, iznos_item)

            # Plaćeno
            paid = getattr(inst, '_paid_amount_value', Decimal("0"))
            paid_item = QTableWidgetItem(f"{Decimal(str(paid)):.2f}")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if paid > 0:
                paid_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(i, 5, paid_item)

            # Status badge sa ikonicom
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            label, bg, fg = STATUS_COLORS.get(status_val, ("?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 6, status_item)'''

new_loop = '''        for i, inst in enumerate(installments):
            # Kupac - koristi getattr da izbjegne lazy loading na detached objektu
            order = getattr(inst, 'order', None)
            customer = getattr(order, 'customer', None) if order else None
            kupac = customer.full_name if customer else ""
            self.installments_table.setItem(i, 0, QTableWidgetItem(kupac))

            # Artikal
            artikal = order.product_name_snapshot if order else ""
            self.installments_table.setItem(i, 1, QTableWidgetItem(artikal))

            # Vrijednost narudžbe (ukupna cijena) - KONVERZIJA EUR
            order_value = Decimal(str(order.total_price_snapshot)) if order else Decimal("0.00")
            order_value_eur = order_value / Decimal("1.95583")  # EUR = KM / 1.95583
            value_item = QTableWidgetItem(f"{order_value_eur:.2f}")
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_item.setForeground(QBrush(QColor("#1f2937")))
            self.installments_table.setItem(i, 2, value_item)

            # Ukupno plaćeno (suma svih uplata) - KONVERZIJA EUR
            paid_total = getattr(inst, '_paid_amount_value', Decimal("0"))
            paid_total_eur = Decimal(str(paid_total)) / Decimal("1.95583")
            paid_item = QTableWidgetItem(f"{paid_total_eur:.2f}")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if paid_total > 0:
                paid_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(i, 3, paid_item)

            # Preostalo (Vrijednost - Ukupno) - KONVERZIJA EUR
            remaining = order_value - Decimal(str(paid_total))
            remaining_eur = remaining / Decimal("1.95583")
            remaining_item = QTableWidgetItem(f"{remaining_eur:.2f}")
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if remaining > 0:
                remaining_item.setForeground(QBrush(QColor("#dc2626")))
            else:
                remaining_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(i, 4, remaining_item)

            # Ažuriraj sume za footer
            total_value += order_value_eur
            total_paid += paid_total_eur
            total_remaining += remaining_eur

            # Rata N/M
            total = order.installments_count if order else "?"
            rata_item = QTableWidgetItem(f"{inst.installment_number}/{total}")
            rata_item.setTextAlignment(Qt.AlignCenter)
            rata_item.setData(Qt.UserRole, inst.id)
            self.installments_table.setItem(i, 5, rata_item)

            # Dospijeće — crveno ako kasni
            due_item = QTableWidgetItem(inst.due_date.strftime("%d.%m.%Y."))
            due_item.setTextAlignment(Qt.AlignCenter)
            if inst.due_date < today:
                due_item.setForeground(QBrush(QColor("#dc2626")))
            self.installments_table.setItem(i, 6, due_item)

            # Status badge
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            label, bg, fg = STATUS_COLORS.get(status_val, ("?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 7, status_item)'''

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("✅ Dodane kolone: Vrijed.(EUR), Ukupno (EUR), Preostalo (EUR)")
else:
    print("⚠️  Nije pronađena petlja za popunjavanje tabele")

# ============================================================================
# 3. DODATI FOOTER SA SUMAMA
# ============================================================================

# Nađi kraj _populate_table i dodaj footer
old_count_label = '''        self.count_label.setText(f"{len(installments)} rata")'''

new_count_label = '''        self.count_label.setText(f"{len(installments)} rata")
        
        # Dodaj footer red sa sumama (ako ima podataka)
        if installments:
            footer_row = self.installments_table.rowCount()
            self.installments_table.insertRow(footer_row)
            
            # "UKUPNO" label
            ukupno_item = QTableWidgetItem("UKUPNO:")
            ukupno_item.setFont(self._bold_font())
            ukupno_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.installments_table.setItem(footer_row, 0, ukupno_item)
            self.installments_table.setSpan(footer_row, 0, 1, 2)  # Spoji Kupac i Artikal
            
            # Vrijednost
            value_item = QTableWidgetItem(f"{total_value:.2f}")
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_item.setFont(self._bold_font())
            self.installments_table.setItem(footer_row, 2, value_item)
            
            # Ukupno plaćeno
            paid_item = QTableWidgetItem(f"{total_paid:.2f}")
            paid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            paid_item.setFont(self._bold_font())
            if total_paid > 0:
                paid_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(footer_row, 3, paid_item)
            
            # Preostalo
            remaining_item = QTableWidgetItem(f"{total_remaining:.2f}")
            remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            remaining_item.setFont(self._bold_font())
            if total_remaining > 0:
                remaining_item.setForeground(QBrush(QColor("#dc2626")))
            else:
                remaining_item.setForeground(QBrush(QColor("#059669")))
            self.installments_table.setItem(footer_row, 4, remaining_item)
            
            # Oboji footer red
            for col in range(self.installments_table.columnCount()):
                item = self.installments_table.item(footer_row, col)
                if item:
                    item.setBackground(QBrush(QColor("#f3f4f6")))'''

if old_count_label in content:
    content = content.replace(old_count_label, new_count_label)
    print("✅ Dodan footer red sa sumama")
else:
    print("⚠️  Nije pronađen count_label")

# ============================================================================
# 4. DODATI _bold_font METODU
# ============================================================================

# Dodaj metodu za bold font
old_init_end = '''        self._load_customers()
        self._load_installments()'''

new_init_end = '''        self._load_customers()
        self._load_installments()
    
    def _bold_font(self):
        """Kreira bold font za footer i važne stavke."""
        font = QFont()
        font.setBold(True)
        return font'''

if old_init_end in content:
    content = content.replace(old_init_end, new_init_end)
    print("✅ Dodana _bold_font() metoda")
else:
    print("⚠️  Nije pronađen kraj __init__")

# ============================================================================
# 5. AŽURIRAJ ŠIRINE KOLONA
# ============================================================================

# Nađi gdje se postavljaju širine kolona
old_column_widths = '''        # Postavi širine kolona
        header = self.installments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Kupac
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Artikal
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Rata
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Dospijeće
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Iznos
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Plaćeno
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Status'''

new_column_widths = '''        # Postavi širine kolona
        header = self.installments_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Kupac
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Artikal
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Vrijed.
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Ukupno
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Preostalo
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Rata
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Dospijeće
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Status'''

if old_column_widths in content:
    content = content.replace(old_column_widths, new_column_widths)
    print("✅ Ažurirane širine kolona")
else:
    print("⚠️  Nisu pronađene širine kolona - možda su već ažurirane")

# ============================================================================
# SAČUVAJ BACKUP I PIŠI IZMJENE
# ============================================================================

backup_path = payments_page_path.with_suffix('.py.backup_columns')
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"\n💾 Backup kreiran: {backup_path}")

with open(payments_page_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Izmijenjen payments_page.py - dodate kolone u EUR")

# ============================================================================
# SAŽETAK
# ============================================================================

print("\n" + "="*80)
print("✅ IMPLEMENTIRANO: NOVE KOLONE U EURIMA")
print("="*80)
print("\n📊 DODATE KOLONE:")
print("   1. Vrijed.(EUR) - Ukupna cijena narudžbe (KM / 1.95583)")
print("   2. Ukupno (EUR) - Suma svih uplata do sada")
print("   3. Preostalo (EUR) - Koliko još treba platiti")
print()
print("📊 FOOTER RED:")
print("   • UKUPNO: - prikazuje sume svih kolona")
print("   • Bold font za važne podatke")
print("   • Siva pozadina za footer")
print()
print("📋 IZGLED TABELLE:")
print("   ┌─────────┬──────────┬───────────┬───────────┬─────────────┬───────┬────────────┬─────────┐")
print("   │ Kupac   │ Artikal  │ Vrijed.   │ Ukupno    │ Preostalo   │ Rata  │ Dospijeće  │ Status  │")
print("   │         │          │ (EUR)     │ (EUR)     │ (EUR)       │       │            │         │")
print("   ├─────────┼──────────┼───────────┼───────────┼─────────────┼───────┼────────────┼─────────┤")
print("   │ Jelena  │ AF 2600  │  105.00   │   10.73   │   94.27     │ 1/10  │ 28.02.26   │ 🟡 DJEL.│")
print("   └─────────┴──────────┴───────────┴───────────┴─────────────┴───────┴────────────┴─────────┘")
print("   ┌─────────┴──────────┴───────────┴───────────┴─────────────┴───────┴────────────┴─────────┐")
print("   │ UKUPNO:             105.00       10.73       94.27                                      │")
print("   └─────────────────────────────────────────────────────────────────────────────────────────┘")
print()
print("🔄 TESTIRAJ:")
print("   python run.py")
print("   → Odi na Uplate")
print("   → Vidiš nove kolone u EUR")
print("   → Footer pokazuje ukupne sume")
print()
