"""
Skripta za ažuriranje svih kupaca - postavi grad na "Bijeljina"
"""

from sqlalchemy import update
from app.database.database import session_scope
from app.database.models import Customer


def update_all_customers_to_bijeljina():
    """Ažurira sve kupce da imaju grad 'Bijeljina'."""
    
    with session_scope() as session:
        # Prebroj kupce prije ažuriranja
        count_before = session.query(Customer).count()
        
        # Ažuriraj sve kupce
        stmt = update(Customer).values(city="Bijeljina")
        result = session.execute(stmt)
        
        # Broj ažuriranih redova
        updated_count = result.rowcount
        
        print(f"✅ Ažurirano {updated_count} kupaca.")
        print(f"   Svi kupci sada imaju grad: Bijeljina")
        
        # Provjeri nekoliko kupaca
        customers = session.query(Customer).limit(5).all()
        print("\nPrimjeri ažuriranih kupaca:")
        for c in customers:
            print(f"  - {c.full_name} ({c.city})")


if __name__ == "__main__":
    update_all_customers_to_bijeljina()
