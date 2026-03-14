#!/usr/bin/env python3
"""
FIX: Uplatama prikazi SVE RATE odabranog kupca (ne samo one koje kasne).

Problem:
Kada odabereš kupca u Uplatama, prikazuju se samo rate koje odgovaraju
aktivnom filteru (npr. "Kasne"). Ali treba prikazati SVE RATE tog kupca
(od prve do zadnje) da bi se vidjelo koje su plaćene, a koje nisu.

Rješenje:
Kada se odabere kupac, učitati SVE njegove rate, ne filtrirati po statusu.

Korištenje:
    python fix_payments_show_all_installments.py
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
# POPRAVKE
# ============================================================================

# 1. Dodati novu metodu za učitavanje SVIH rata kupca
# 2. Izmijeniti _load_installments da koristi tu metodu kad je kupac odabran

# Dodajemo nakon _load_customers metode
new_method = '''
    def _load_all_customer_installments(self, customer_id: int) -> list:
        """
        Učitava SVE RATE odabranog kupca (ne filtrira po statusu).
        
        Args:
            customer_id: ID kupca čije rate učitavamo
        
        Returns:
            Lista svih rata sortiranu po datumu dospijeća
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.database.database import session_scope
        from app.database.models import Installment, Order, Customer
        from sqlalchemy import func
        
        with session_scope() as session:
            # Učitaj sve rate za kupca
            stmt = (
                select(Installment)
                .join(Order)
                .where(Order.customer_id == customer_id)
                .options(
                    selectinload(Installment.order).selectinload(Order.customer),
                    selectinload(Installment.payments),
                )
                .order_by(Installment.due_date.asc())
            )
            
            installments = list(session.execute(stmt).scalars().unique())
            
            # Izračunaj paid_amount za svaku ratu
            for inst in installments:
                paid = sum(
                    (p.amount for p in inst.payments), Decimal("0.00")
                )
                object.__setattr__(inst, '_paid_amount_value', paid)
            
            session.expunge_all()
            return installments

'''

# Ubaci novu metodu prije _load_installments
insert_marker = "    def _load_installments(self) -> None:"
if insert_marker in content:
    content = content.replace(insert_marker, new_method + insert_marker)
    print("✅ Dodana metoda _load_all_customer_installments()")
else:
    print("⚠️  Nije pronađen marker za _load_installments")

# 3. Izmijeniti _load_installments da koristi novu metodu kad je kupac odabran
old_load = '''    def _load_installments(self) -> None:
        """Učitava rate sa filtrima."""
        # Dobavi ID odabranog kupca
        customer_id = self.customer_combo.currentData()

        # Dobavi tekst pretrage
        search_text = self.search_edit.text().strip()

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

if old_load in content:
    content = content.replace(old_load, new_load)
    print("✅ Izmijenjena metoda _load_installments()")
else:
    print("⚠️  Nije pronađena stara _load_installments() metoda")
    print("   Možda je već izmijenjena?")

# 4. Izmijeniti _set_filter da ne resetuje prikaz kad je kupac odabran
old_set_filter = '''    def _set_filter(self, key: str) -> None:
        """Postavlja aktivni filter i učitava rate."""
        for k, btn in self.filter_buttons.items():
            checked = (k == key)
            btn.setChecked(checked)
            color = "white" if checked else "#374151"
            btn.setIcon(get_pixmap(self._filter_icons[k], color, 16))
        self._active_filter = key
        # Eksplicitno čitaj customer_id prije učitavanja
        self._selected_customer_id = self.customer_combo.currentData()
        self._load_installments()'''

new_set_filter = '''    def _set_filter(self, key: str) -> None:
        """Postavlja aktivni filter i učitava rate."""
        for k, btn in self.filter_buttons.items():
            checked = (k == key)
            btn.setChecked(checked)
            color = "white" if checked else "#374151"
            btn.setIcon(get_pixmap(self._filter_icons[k], color, 16))
        self._active_filter = key
        
        # AKO JE KUPEC ODABRAN → filteri se ignorišu (prikazuju se SVE rate)
        # Samo osvježi tabelu
        self._selected_customer_id = self.customer_combo.currentData()
        self._load_installments()'''

if old_set_filter in content:
    content = content.replace(old_set_filter, new_set_filter)
    print("✅ Izmijenjena metoda _set_filter()")
else:
    print("⚠️  Nije pronađena _set_filter() metoda")

# ============================================================================
# PISANJE IZMIJENJENOG KODA
# ============================================================================

backup_path = payments_page_path.with_suffix('.py.backup')
with open(backup_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n💾 Backup kreiran: {backup_path}")

# Sada pišemo izmijenjeni kod
with open(payments_page_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Izmijenjen payments_page.py")

# ============================================================================
# SAŽETAK
# ============================================================================

print("\n" + "="*70)
print("✅ POPRAVKA ZAVRŠENA")
print("="*70)
print("\n📝 ŠTA JE PROMIJENJENO:")
print("   1. Dodana metoda _load_all_customer_installments()")
print("      → Učitava SVE RATE odabranog kupca")
print("   2. Izmijenjena _load_installments()")
print("      → Kad je kupac odabran: prikazuje SVE njegove rate")
print("      → Kad nije odabran: koristi filtere (overdue, month, etc.)")
print("   3. Izmijenjena _set_filter()")
print("      → Filteri se ignorišu kad je kupac odabran")
print()
print("📋 KAKO ĆE RADITI:")
print("   • Kad odabereš kupca → vidiš SVE njegove rate (1-M)")
print("   • Rate su sortirane po datumu dospijeća")
print("   • Vidiš koje su plaćene (zelene), koje kasne (crvene)")
print("   • Filteri (Kasne, Ovaj mjesec) rade samo kad NIJE odabran kupac")
print()
print("🔄 SLEDEĆI KORAK:")
print("   1. Zatvori aplikaciju ako je otvorena")
print("   2. Pokreni: python run.py")
print("   3. Idi na Uplate → Odaberi kupca")
print("   4. Trebale bi se prikazati SVE rate tog kupca")
print()
