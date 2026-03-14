#!/usr/bin/env python3
"""
Konverzija svih iznosa iz KM nazad u EUR.

Svi iznosi u Excel-u su u EUR. Greškom su konvertovani u KM.
Ova skripta konvertuje sve nazad u EUR.

Faktor konverzije: 1 EUR = 1.95583 KM
"""

from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database.database import session_scope
from app.database.models import Order, Installment, Payment
from sqlalchemy import select

EUR_TO_KM = Decimal("1.95583")

def convert_km_to_eur():
    """Konvertuj sve iznose iz KM u EUR."""
    
    print("\n" + "="*80)
    print("🔄 KONVERZIJA IZNOSA IZ KM → EUR")
    print("="*80)
    
    with session_scope() as session:
        # 1. Konvertuj Order.total_price_snapshot
        print("\n📄 Konverzija narudžbi (Order.total_price_snapshot)...")
        orders = session.execute(select(Order)).scalars().all()
        
        for order in orders:
            old_value = order.total_price_snapshot
            new_value = old_value / EUR_TO_KM
            order.total_price_snapshot = new_value.quantize(Decimal("0.01"))
        
        print(f"   ✅ Konvertovano {len(orders)} narudžbi")
        
        # 2. Konvertuj Installment.amount
        print("\n📋 Konverzija rata (Installment.amount)...")
        installments = session.execute(select(Installment)).scalars().all()
        
        for inst in installments:
            old_value = inst.amount
            new_value = old_value / EUR_TO_KM
            inst.amount = new_value.quantize(Decimal("0.01"))
        
        print(f"   ✅ Konvertovano {len(installments)} rata")
        
        # 3. Konvertuj Payment.amount
        print("\n💳 Konverzija uplata (Payment.amount)...")
        payments = session.execute(select(Payment)).scalars().all()
        
        for payment in payments:
            old_value = payment.amount
            new_value = old_value / EUR_TO_KM
            payment.amount = new_value.quantize(Decimal("0.01"))
        
        print(f"   ✅ Konvertovano {len(payments)} uplata")
        
        print("\n" + "="*80)
        print("✅ KONVERZIJA ZAVRŠENA!")
        print("="*80)
        
        # Prikaži primjer
        print("\n📊 PRIMJER (nakon konverzije):")
        order = session.execute(
            select(Order).where(Order.contract_number == "735969")
        ).scalars().first()
        
        if order:
            print(f"   Ugovor: {order.contract_number}")
            print(f"   Proizvod: {order.product_name_snapshot}")
            print(f"   Vrijednost: {order.total_price_snapshot:.2f} EUR ← SADA U EUR!")

if __name__ == "__main__":
    convert_km_to_eur()
