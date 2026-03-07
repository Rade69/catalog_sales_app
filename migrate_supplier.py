#!/usr/bin/env python3
"""
Migracija: Dodaje 'supplier' kolonu u price_list_items tabelu.
"""

from pathlib import Path
import sys

# Dodaj parent directory u path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import text, inspect
from app.database.database import engine, session_scope
from app.database.models import PriceListItem


def migrate():
    """Dodaje supplier kolonu ako ne postoji."""
    
    # Provjeri da li kolona već postoji
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('price_list_items')]
    
    if 'supplier' in columns:
        print("✓ Kolona 'supplier' već postoji u price_list_items tabeli.")
        return
    
    print("Dodavanje kolone 'supplier' u price_list_items tabelu...")
    
    with engine.connect() as conn:
        # SQLite: ALTER TABLE ADD COLUMN
        conn.execute(text(
            "ALTER TABLE price_list_items ADD COLUMN supplier VARCHAR(200)"
        ))
        conn.commit()
    
    # Kreiraj index za supplier kolonu
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_price_list_items_supplier ON price_list_items (supplier)"
        ))
        conn.commit()
    
    print("✓ Migracija uspješna! Kolona 'supplier' je dodana.")


if __name__ == "__main__":
    migrate()
