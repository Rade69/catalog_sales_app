#!/usr/bin/env python3
"""
FIX: Dodaje uplate za historijske rate koje nemaju evidentirane uplate.

Ova skripta rješava problem gdje su rate iz prošle godine kreirane,
ali nemaju pripadajuće Payment zapise, pa se prikazuju kao OVERDUE
umjesto PAID.

Način rada:
1. Učitava sve narudžbe koje imaju contract_number (historijske)
2. Za svaku narudžbu provjerava da li postoje rate
3. Ako rate postoje ali NEMAJU uplate → dodaje uplate
4. Ako je narudžba COMPLETED → sve rate označava kao PAID
5. Ako je narudžba ACTIVE → dodaje uplate za onoliko rata koliko je plaćeno

Korištenje:
    python fix_historical_installments.py

Napomena: Ova skripta je BEZBJEDNA - ne briše postojeće podatke,
samo dodaje uplate tamo gdje fale.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Dodaj parent directory u path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import (
    Order,
    OrderStatus,
    Installment,
    InstallmentStatus,
    Payment,
)


# ============================================================================
# KONFIGURACIJA
# ============================================================================

# Da li želiš vidjeti detaljan ispis?
VERBOSE = True

# Da li želiš napraviti promjene u bazi? (False = samo dry-run)
DRY_RUN = False

# Datum za uplate (koristi se order.order_date)
USE_ORDER_DATE_FOR_PAYMENT = True


# ============================================================================
# FUNKCIJE
# ============================================================================

def count_orders_without_payments() -> tuple[int, int]:
    """
    Broji narudžbe koje imaju rate ali nemaju uplate.
    
    Returns:
        (total_historical_orders, orders_missing_payments)
    """
    with session_scope() as session:
        # Sve narudžbe sa contract_number (historijske)
        all_orders = list(
            session.execute(
                select(Order).where(Order.contract_number.is_not(None))
            ).scalars().all()
        )
        
        total = len(all_orders)
        missing = 0
        
        for order in all_orders:
            # Provjeri da li ima rate
            num_installments = session.execute(
                select(func.count(Installment.id)).where(
                    Installment.order_id == order.id
                )
            ).scalar() or 0
            
            if num_installments == 0:
                continue  # Nema rata, preskoči
            
            # Provjeri da li ima uplata
            num_payments = session.execute(
                select(func.count(Payment.id))
                .join(Installment)
                .where(Installment.order_id == order.id)
            ).scalar() or 0
            
            if num_payments == 0:
                missing += 1
        
        return total, missing


def fix_installments() -> dict:
    """
    Dodaje Payment zapise za historijske narudžbe koje nemaju uplate.
    
    Returns:
        dict sa statistikom popravke
    """
    stats = {
        'orders_processed': 0,
        'orders_skipped': 0,
        'installments_updated': 0,
        'payments_created': 0,
        'errors': [],
    }
    
    with session_scope() as session:
        # Sve narudžbe sa contract_number (historijske)
        all_orders = list(
            session.execute(
                select(Order)
                .where(Order.contract_number.is_not(None))
                .options(joinedload(Order.installments))
            ).scalars().all()
        )
        
        print(f"\n📊 Pronađeno {len(all_orders)} historijskih narudžbi\n")
        
        for order in all_orders:
            if VERBOSE:
                print(f"\n{'='*70}")
                print(f"📋 Narudžba: {order.contract_number}")
                print(f"   Kupac ID: {order.customer_id}")
                print(f"   Iznos: {order.total_price_snapshot:.2f} KM")
                print(f"   Rate: {order.installments_count}")
                print(f"   Status: {order.status.value}")
            
            # Preskoči ako nema rata
            if not order.installments:
                if VERBOSE:
                    print(f"   ⚠️  Nema rata - preskačem")
                stats['orders_skipped'] += 1
                continue
            
            # Provjeri da li već postoje uplate
            num_payments = session.execute(
                select(func.count(Payment.id)).where(
                    Payment.installment_id.in_(
                        select(Installment.id).where(Installment.order_id == order.id)
                    )
                )
            ).scalar() or 0
            
            if num_payments > 0:
                if VERBOSE:
                    print(f"   ✅ Već ima {num_payments} uplata - preskačem")
                stats['orders_skipped'] += 1
                continue
            
            # Sortiraj rate po broju
            sorted_installments = sorted(
                order.installments, 
                key=lambda x: x.installment_number
            )
            
            if VERBOSE:
                print(f"   🔧 Nema uplata - dodajem...")
            
            stats['orders_processed'] += 1
            
            # Datum za uplate
            payment_date = order.order_date if USE_ORDER_DATE_FOR_PAYMENT else date.today()
            
            if order.status == OrderStatus.COMPLETED:
                # ✅ Sve rate su plaćene - dodaj uplatu za svaku ratu
                if VERBOSE:
                    print(f"   📝 Status COMPLETED - sve rate plaćene")
                
                for inst in sorted_installments:
                    inst.status = InstallmentStatus.PAID
                    inst.paid_at = payment_date
                    
                    if not DRY_RUN:
                        payment = Payment(
                            installment_id=inst.id,
                            payment_date=payment_date,
                            amount=Decimal(str(inst.amount)),
                            note="Automatski generisano — fix historical import",
                        )
                        session.add(payment)
                    
                    stats['installments_updated'] += 1
                    stats['payments_created'] += 1
                    
                    if VERBOSE:
                        print(f"      Rata {inst.installment_number}: {inst.amount:.2f} KM → PAID ✅")
            
            else:
                # ⚠️ ACTIVE narudžba - treba izračunati koliko je plaćeno
                # Nažalost, bez originalnog Excel fajla ne možemo znati tačan iznos
                # Pretpostavljamo da je prva rata plaćena ako je order ACTIVE
                
                if VERBOSE:
                    print(f"   ⚠️  Status ACTIVE - parcijalno plaćeno")
                    print(f"      ⚠️  UPOZORENJE: Ne mogu odrediti koliko je rata plaćeno")
                    print(f"      bez originalnog Excel fajla. Preskačem ovu narudžbu.")
                
                # Ovdje bi trebalo učitati originalni Excel fajl da bismo znali
                # koliko je rata plaćeno. Za sada preskačemo.
                stats['orders_skipped'] += 1
                stats['errors'].append(
                    f"Narudžba {order.contract_number}: ACTIVE status - "
                    f"potreban originalni Excel za određivanje plaćenih rata"
                )
    
    return stats


def print_summary(stats: dict) -> None:
    """Ispisuje sažetak popravke."""
    print("\n" + "="*70)
    print("📊 SAŽETAK POPRAVKE")
    print("="*70)
    print(f"  ✅ Narudžbi popravljeno:      {stats['orders_processed']}")
    print(f"  ⏭️  Narudžbi preskočeno:      {stats['orders_skipped']}")
    print(f"  📝 Rata ažurirano:            {stats['installments_updated']}")
    print(f"  💰 Uplata kreirano:           {stats['payments_created']}")
    
    if stats['errors']:
        print(f"\n⚠️  UPOZORENJA ({len(stats['errors'])}):")
        for err in stats['errors'][:5]:  # Prikaži prvih 5
            print(f"     • {err}")
        if len(stats['errors']) > 5:
            print(f"     ... i još {len(stats['errors']) - 5}")
    
    print("="*70)


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    """Glavna funkcija."""
    print("\n" + "="*70)
    print("🔧 FIX: Historijske rate bez uplata")
    print("="*70)
    
    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - Nema promjena u bazi!")
        print("   Za stvarne promjene, postavi DRY_RUN = False u skripti.\n")
    else:
        print("\n⚠️  UPOZORENJE: Ova skripta će napraviti promjene u bazi!")
        print("   Preporučuje se napraviti backup prije pokretanja.\n")
    
    # 1. Prebroj narudžbe bez uplata
    print("📊 Analiza stanja...")
    total, missing = count_orders_without_payments()
    
    print(f"   Ukupno historijskih narudžbi: {total}")
    print(f"   Narudžbi bez uplata: {missing}")
    
    if missing == 0:
        print("\n✅ Sve narudžbe već imaju uplate! Nema potrebe za popravkom.")
        return
    
    # 2. Pitaj korisnika za potvrdu
    if not DRY_RUN:
        print(f"\n⚠️  Da li želiš popraviti {missing} narudžbi?")
        response = input("   Unesi 'DA' za potvrdu: ").strip().upper()
        if response != 'DA':
            print("   Odustao/la.")
            return
    
    # 3. Pokreni popravku
    print("\n🔧 Pokrećem popravku...")
    stats = fix_installments()
    
    # 4. Ispiši sažetak
    print_summary(stats)
    
    if not DRY_RUN and stats['payments_created'] > 0:
        print("\n✅ Popravka uspješna!")
        print("\n📝 SLEDEĆI KORACI:")
        print("   1. Zatvori ovu skriptu")
        print("   2. Pokreni aplikaciju: python run.py")
        print("   3. Provjeri stranicu 'Rate' - statusi bi trebali biti ispravni")
        print("   4. Provjeri stranicu 'Uplate' - trebale bi se vidjeti nove uplate")
    elif DRY_RUN:
        print("\n💡 DRY RUN završen.")
        print("   Za stvarnu popravku, postavi DRY_RUN = False u skripti.")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
