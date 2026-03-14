#!/usr/bin/env python3
"""
Popravka: Dodaje uplate za 13 specifičnih rata iz 2025. godine.

Ova skripta dodaje Payment zapise za rate koje su:
- Iz 2025. godine (prošle)
- Status: OVERDUE
- Nemaju evidentirane uplate
- Ugovori: 682163, 682166, 682167, 682168, 682169, 682171, 682175

Ovo su vjerovatno rate koje su plaćene ali nisu evidentirane prilikom
importa historijskih podataka.

Korištenje:
    python fix_overdue_installments_2025.py
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import (
    Order,
    OrderStatus,
    Installment,
    InstallmentStatus,
    Payment,
)


# Ugovori koje treba popraviti
CONTRACTS_TO_FIX = [
    "682163",  # Marina Mišković
    "682166",  # Jovana Simić
    "682167",  # Snežana Tomić
    "682168",  # Svetlana Tomić
    "682169",  # Ivana Stevanovic
    "682171",  # Danijela Borković
    "682175",  # Nikola Stojanović
]


def main() -> None:
    """Glavna funkcija."""
    print("\n" + "="*70)
    print("🔧 POPRAVKA: 13 rata iz 2025. bez uplata")
    print("="*70)
    print()
    print("📋 Ugovori za popravku:")
    for contract in CONTRACTS_TO_FIX:
        print(f"   • {contract}")
    print()
    
    # Da li je dry-run?
    dry_run = False
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        dry_run = True
        print("⚠️  DRY RUN MODE - Nema promjena u bazi!")
        print()
    
    stats = {
        'installments_fixed': 0,
        'payments_created': 0,
        'total_amount': Decimal("0.00"),
    }
    
    with session_scope() as session:
        for contract in CONTRACTS_TO_FIX:
            # Pronađi narudžbu
            order = session.execute(
                select(Order)
                .where(Order.contract_number == contract)
                .options(joinedload(Order.installments))
            ).scalars().first()
            
            if not order:
                print(f"❌ Ugovor {contract} nije pronađen!")
                continue
            
            print(f"\n{'='*60}")
            print(f"📋 Ugovor: {contract}")
            print(f"   Kupac ID: {order.customer_id}")
            print(f"   Ukupno: {order.total_price_snapshot:.2f} KM")
            print(f"   Status: {order.status.value}")
            
            # Pronađi rate bez uplata
            overdue_no_payment = []
            for inst in order.installments:
                # Provjeri da li ima uplata
                num_payments = session.execute(
                    select(func.count(Payment.id)).where(
                        Payment.installment_id == inst.id
                    )
                ).scalar() or 0
                
                if num_payments == 0 and inst.status == InstallmentStatus.OVERDUE:
                    overdue_no_payment.append(inst)
            
            # Filtriraj samo rate iz 2025. godine
            overdue_2025_only = [
                inst for inst in overdue_no_payment 
                if inst.due_date < date(2026, 1, 1)
            ]
            
            if not overdue_2025_only:
                print(f"   ✅ Nema rata iz 2025. za popravku")
                # Prikaži ako ima novijih
                if overdue_no_payment:
                    print(f"   ℹ️  Ima {len(overdue_no_payment)} novijih rata (2026.) bez uplata")
                continue
            
            print(f"   🔧 Rata iz 2025. za popravku: {len(overdue_2025_only)}")
            
            for inst in overdue_2025_only:
                print(f"      • Rata {inst.installment_number}: "
                      f"{inst.amount:.2f} KM, Dospijeće: {inst.due_date}")
                
                if not dry_run:
                    # Kreiraj uplatu
                    payment = Payment(
                        installment_id=inst.id,
                        payment_date=inst.due_date,  # Koristi datum dospijeća
                        amount=Decimal(str(inst.amount)),
                        note="Automatski dodano — fix historical import 2025",
                    )
                    session.add(payment)
                    
                    # Ažuriraj status rate
                    inst.status = InstallmentStatus.PAID
                    inst.paid_at = inst.due_date
                    
                    stats['installments_fixed'] += 1
                    stats['payments_created'] += 1
                    stats['total_amount'] += inst.amount
            
            print(f"   ✅ Popravljeno!")
    
    # Sažetak
    print("\n" + "="*70)
    print("📊 SAŽETAK")
    print("="*70)
    
    if dry_run:
        print(f"  (DRY RUN - nema promjena)")
    
    print(f"  ✅ Rata ažurirano:      {stats['installments_fixed']}")
    print(f"  💰 Uplata kreirano:     {stats['payments_created']}")
    print(f"  💵 Ukupan iznos:        {stats['total_amount']:.2f} KM")
    print("="*70)
    
    if not dry_run and stats['payments_created'] > 0:
        print("\n✅ POPRAVKA USPJEŠNA!")
        print("\n📝 SLEDEĆI KORACI:")
        print("   1. Zatvori ovu skriptu")
        print("   2. Pokreni aplikaciju: python run.py")
        print("   3. Provjeri stranicu 'Rate' - ovih 13 rata bi trebalo biti ✅ PAID")
        print("   4. Provjeri stranicu 'Uplate' - trebale bi se vidjeti nove uplate")
        print()
    elif dry_run:
        print("\n💡 Za stvarnu popravku, pokreni bez --dry-run:")
        print("   python fix_overdue_installments_2025.py")
        print()


# Import func ovdje da bude dostupan
from sqlalchemy import func

if __name__ == "__main__":
    main()
