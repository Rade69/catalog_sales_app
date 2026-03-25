"""
Jednostavna skripta za kreiranje testnih podataka - bez OrderService.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.database.database import session_scope
from app.database.models import (
    Customer, Order, Campaign, Product, 
    Installment, Payment, CampaignPrice
)


def create_test_data():
    with session_scope() as session:
        # Provjeri ima li već podataka
        if session.query(Customer).count() > 0:
            print("⚠️  Već postoje podaci u bazi. Preskačem kreiranje.")
            return
        
        print("📦 Kreiranje testnih podataka...")
        
        # 1. Kreiraj kampanju
        campaign = Campaign(
            name="Test Kampanja 2026",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=60),
            status="active",
            source_excel_filename="test.xlsx"
        )
        session.add(campaign)
        session.flush()
        print(f"  ✓ Kampanja kreirana: {campaign.name}")
        
        # 2. Kreiraj proizvode
        products = [
            Product(name="Vitamin C 1000mg", normalized_name="vitamin c", brand="HealthCare"),
            Product(name="Omega 3", normalized_name="omega 3", brand="HealthCare"),
            Product(name="Multivitamin", normalized_name="multivitamin", brand="VitaPlus"),
            Product(name="Kalcijum + D3", normalized_name="kalcijum", brand="VitaPlus"),
            Product(name="Magnezijum", normalized_name="magnezijum", brand="VitaPlus"),
        ]
        for p in products:
            session.add(p)
        session.flush()
        print(f"  ✓ {len(products)} proizvoda kreirano")
        
        # 3. Kreiraj campaign prices
        for i, product in enumerate(products, 1):
            price = CampaignPrice(
                campaign_id=campaign.id,
                product_id=product.id,
                regular_price=Decimal(f"{19.99 * i}"),
                discount_price=Decimal(f"{15.99 * i}") if i % 2 == 0 else None,
                points=i * 10
            )
            session.add(price)
        print(f"  ✓ {len(products)} cijena kreirano")
        
        # 4. Kreiraj kupce
        customers = [
            Customer(full_name="Jovan Jovanović", phone="061 123 456", city="Sarajevo"),
            Customer(full_name="Marko Marković", phone="062 234 567", city="Banja Luka"),
            Customer(full_name="Petar Petrović", phone="063 345 678", city="Tuzla"),
            Customer(full_name="Ana Anić", phone="065 456 789", city="Mostar"),
            Customer(full_name="Milica Milić", phone="066 567 890", city="Zenica"),
        ]
        for c in customers:
            session.add(c)
        session.flush()
        print(f"  ✓ {len(customers)} kupaca kreirano")
        
        # 5. Kreiraj narudžbe DIREKTNO (ne kroz OrderService)
        for i, customer in enumerate(customers[:3]):
            product = products[i % len(products)]
            total_price = Decimal(f"{19.99 * product.id}")
            
            order = Order(
                customer_id=customer.id,
                campaign_id=campaign.id,
                product_id=product.id,
                order_date=date.today(),
                status="active",
                product_name_snapshot=product.name,
                product_normalized_name_snapshot=product.normalized_name,
                product_brand_snapshot=product.brand,
                quantity=1,
                unit_price_snapshot=total_price,
                total_price_snapshot=total_price,
                installments_count=5,
                first_due_date=date.today() + timedelta(days=30)
            )
            session.add(order)
            session.flush()
            
            # Kreiraj rate
            installment_amount = total_price / 5
            for j in range(5):
                installment = Installment(
                    order_id=order.id,
                    installment_number=j + 1,
                    due_date=date.today() + timedelta(days=30 * (j + 1)),
                    amount=installment_amount,
                    status="pending" if j > 0 else "paid"
                )
                session.add(installment)
            
            # Kreiraj uplatu za prvu ratu
            if order.installments:
                payment = Payment(
                    installment_id=order.installments[0].id,
                    payment_date=date.today(),
                    amount=installment_amount,
                    note="Test uplata"
                )
                session.add(payment)
            
            print(f"  ✓ Narudžba #{order.id} kreirana za {customer.full_name}")
        
        print("\n✅ Test podaci uspješno kreirani!")
        print("\n📊 Rezime:")
        print(f"   Kupci: {len(customers)}")
        print(f"   Proizvodi: {len(products)}")
        print(f"   Kampanje: 1")
        print(f"   Narudžbe: 3")


if __name__ == "__main__":
    create_test_data()
