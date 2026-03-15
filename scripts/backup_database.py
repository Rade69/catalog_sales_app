#!/usr/bin/env python3
"""
Backup skripta za bazu podataka.

Kreira backup trenutne baze podataka prije pokretanja popravki.

Korištenje:
    python backup_database.py
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database.database import DB_PATH, DATA_DIR


def create_backup() -> Path:
    """
    Kreira backup baze podataka.
    
    Returns:
        Putanja do kreiranog backup fajla
    """
    backup_dir = Path(__file__).resolve().parent / "backup"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"catalog_sales_backup_{timestamp}.db"
    
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Baza podataka nije pronađena: {DB_PATH}\n"
            f"Data directory: {DATA_DIR}\n"
            f"Provjeri da li je aplikacija barem jednom pokrenuta."
        )
    
    shutil.copy2(DB_PATH, backup_file)
    
    return backup_file


def main() -> None:
    """Glavna funkcija."""
    print("\n" + "="*70)
    print("💾 BACKUP BAZE PODATAKA")
    print("="*70)
    
    print(f"\n📁 Izvor: {DB_PATH}")
    
    try:
        backup_file = create_backup()
        print(f"✅ Backup kreiran: {backup_file}")
        print(f"📦 Veličina: {backup_file.stat().st_size / 1024:.2f} KB")
        print("\n" + "="*70)
        print("✅ BACKUP USPJEŠAN!")
        print("="*70)
        print("\n💡 Sada možeš sigurno pokrenuti:")
        print("   python fix_historical_installments.py")
        print()
        
    except FileNotFoundError as e:
        print(f"\n❌ GREŠKA: {e}")
        print("\n💡 Rješenje:")
        print("   1. Pokreni aplikaciju barem jednom: python run.py")
        print("   2. Zatim ponovo pokreni ovu backup skriptu")
        print()
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ NEOČEKIVANA GREŠKA: {e}")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
