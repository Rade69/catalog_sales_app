#!/usr/bin/env python3
"""
FIX 2: Filteri za kupca + ikonice umjesto teksta za statuse.

Problem 1: Kad odabereš kupca, filteri (Sve, Kasne, Ovaj mjesec, Neplaćene) ne rade.
Problem 2: Umjesto ikonica piše samo tekst "PLAĆENO", "ČEKA", "KASNI".

Rješenje:
1. Filteri treba da rade i kad je kupac odabran
2. Dodati ikonice za statuse umjesto teksta
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ============================================================================
# ČITANJE TRENUTNOG KODA
# ============================================================================

payments_page_path = Path(__file__).resolve().parent / "app" / "gui" / "pages" / "payments_page.py"

with open(payments_page_path, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================================
# POPRAVKA 1: Filteri da rade i kad je kupac odabran
# ============================================================================

# Zamijeni _load_installments metodu
old_load = '''    def _load_installments(self) -> None:
        """Učitava rate sa filtrima."""
        # Dobavi ID odabranog kupca
        customer_id = self.customer_combo.currentData()

        # Dobavi tekst pretrage
        search_text = self.search_edit.text().strip()

        # AKO JE KUPEC ODABRAN → PRIKAŽI SVE NJEGOVE RATE (ne filtriraj po statusu)
        if customer_id is not None:
            try:
                installments = self._load_all_customer_installments(customer_id)
                
                # Ako postoji tekst pretrage, filtriraj ručno
                if search_text:
                    filtered = []
                    for inst in installments:
                        order = getattr(inst, 'order', None)
                        customer = getattr(order, 'customer', None) if order else None
                        kupac = customer.full_name if customer else ""
                        artikal = order.product_name_snapshot if order else ""
                        contract = getattr(order, 'contract_number', '') or ''
                        
                        if (search_text.lower() in kupac.lower() or
                            search_text.lower() in artikal.lower() or
                            search_text.lower() in str(contract).lower()):
                            filtered.append(inst)
                    installments = filtered
            except Exception as e:
                print(f"Greška pri učitavanju rata kupca: {e}")
                installments = []
        else:
            # Nije odabran kupac → koristi filtere
            try:
                installments = PaymentService.get_installments_for_payment(
                    filter_type=self._active_filter,
                    search=search_text,
                    customer_id=customer_id
                )
            except TypeError:
                # Starija verzija servisa ne podržava customer_id
                try:
                    installments = PaymentService.get_installments_for_payment(
                        filter_type=self._active_filter,
                        search=search_text
                    )
                except Exception:
                    installments = []
            except Exception:
                installments = []

        self._populate_table(installments)'''

new_load = '''    def _load_installments(self) -> None:
        """Učitava rate sa filtrima."""
        # Dobavi ID odabranog kupca
        customer_id = self.customer_combo.currentData()

        # Dobavi tekst pretrage
        search_text = self.search_edit.text().strip()

        # Uvijek koristi PaymentService sa filterima
        # Filteri rade i kad je kupac odabran
        try:
            installments = PaymentService.get_installments_for_payment(
                filter_type=self._active_filter,
                search=search_text,
                customer_id=customer_id
            )
        except TypeError:
            # Starija verzija servisa ne podržava customer_id
            try:
                installments = PaymentService.get_installments_for_payment(
                    filter_type=self._active_filter,
                    search=search_text
                )
            except Exception:
                installments = []
        except Exception:
            installments = []

        self._populate_table(installments)'''

if old_load in content:
    content = content.replace(old_load, new_load)
    print("✅ Izmijenjena _load_installments() - filteri sada rade i za kupca")
else:
    print("⚠️  Nije pronađena _load_installments() za zamjenu")

# ============================================================================
# POPRAVKA 2: Dodati ikonice umjesto teksta za statuse
# ============================================================================

# Nađi _populate_table metodu i zamijeni STATUS_STYLE sa ikonicama
old_status_style = '''        STATUS_STYLE = {
            "overdue":        ("KASNI",      "#fee2e2", "#991b1b"),
            "partially_paid": ("DJELIMIČNO", "#fef3c7", "#92400e"),
            "pending":        ("ČEKA",       "#f3f4f6", "#6b7280"),
            "paid":           ("PLAĆENO",    "#dcfce7", "#166534"),
        }'''

new_status_style = '''        STATUS_ICONS = {
            "overdue":        ("🔴", "KASNI",      "#fee2e2", "#991b1b"),
            "partially_paid": ("🟡", "DJELIMIČNO", "#fef3c7", "#92400e"),
            "pending":        ("⏳", "ČEKA",       "#f3f4f6", "#6b7280"),
            "paid":           ("✅", "PLAĆENO",    "#dcfce7", "#166534"),
        }'''

if old_status_style in content:
    content = content.replace(old_status_style, new_status_style)
    print("✅ Dodate ikonice za statuse")
else:
    print("⚠️  Nije pronađen STATUS_STYLE")

# Sada nađi gdje se kreira status_item i dodaj ikonicu
old_status_item = '''            # Status badge
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            label, bg, fg = STATUS_STYLE.get(status_val, ("?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(label)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 6, status_item)'''

new_status_item = '''            # Status badge sa ikonicom
            status_val = inst.status.value if hasattr(inst.status, 'value') else str(inst.status)
            icon, label, bg, fg = STATUS_ICONS.get(status_val, ("?", "?", "#f3f4f6", "#374151"))
            status_item = QTableWidgetItem(f"{icon} {label}")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setBackground(QBrush(QColor(bg)))
            status_item.setForeground(QBrush(QColor(fg)))
            self.installments_table.setItem(i, 6, status_item)'''

if old_status_item in content:
    content = content.replace(old_status_item, new_status_item)
    print("✅ Dodate ikonice u status badge")
else:
    print("⚠️  Nije pronađen kod za status_item")

# ============================================================================
# PISANJE IZMIJENJENOG KODA
# ============================================================================

backup_path2 = payments_page_path.with_suffix('.py.backup2')
with open(backup_path2, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n💾 Backup 2 kreiran: {backup_path2}")

with open(payments_page_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Izmijenjen payments_page.py (FIX 2)")

# ============================================================================
# SAŽETAK
# ============================================================================

print("\n" + "="*70)
print("✅ FIX 2 ZAVRŠEN")
print("="*70)
print("\n📝 ŠTA JE PROMIJENJENO:")
print("   1. Filteri (Sve, Kasne, Ovaj mjesec, Neplaćene) rade i kad je kupac odabran")
print("   2. Dodate ikonice za statuse:")
print("      ✅ PLAĆENO")
print("      🔴 KASNI")
print("      🟡 DJELIMIČNO")
print("      ⏳ ČEKA")
print()
print("📋 KAKO ĆE IZGLEDATI:")
print("   • Umjesto 'PLAĆENO' → '✅ PLAĆENO'")
print("   • Umjesto 'KASNI' → '🔴 KASNI'")
print("   • Umjesto 'ČEKA' → '⏳ ČEKA'")
print()
print("🔄 TESTIRAJ:")
print("   1. Pokreni: python run.py")
print("   2. Idi na Uplate")
print("   3. Odaberi kupca")
print("   4. Klikni na filtere (Sve, Kasne, Ovaj mjesec, Neplaćene)")
print("   5. Trebale bi se filtrirati rate i vidjeti se ikonice")
print()
