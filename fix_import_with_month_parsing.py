#!/usr/bin/env python3
"""
FIX: Ponovni uvoz historijskih podataka sa ispravnim datumima na osnovu mjeseca iz tabele.

Ova skripta:
1. Čita mjesec i godinu iz Excel zaglavlja (red 4, kolone 16 i 19)
2. Određuje datum prve rate na osnovu tog mjeseca
3. Briše postojeće historijske narudžbe (ako postoje)
4. Kreira nove narudžbe sa ispravnim datumima

Korištenje:
    python fix_import_with_month_parsing.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignStatus,
    Customer,
    Installment,
    Order,
    OrderStatus,
)
from app.services.installment_service import InstallmentService


# ============================================================================
# KONFIGURACIJA
# ============================================================================

# Putanja do Excel fajla
EXCEL_PATH = "/home/radovan/Desktop/ASYCUDA_PRO/ostalo/fwdpogodnosti0326cjenovnik02_03_2026_/4-1-11-2-1-3-Sanja-februar 2026. - p.xlsx"

# Naziv kampanje
HISTORICAL_CAMPAIGN_NAME = "Historijat 2025-2026"

# EUR → BAM kurs
EUR_TO_BAM = Decimal("1.95583")

# Da li brisati postojeće podatke prije uvoza?
DELETE_EXISTING = True

# Verbose ispis
VERBOSE = True


# ============================================================================
# POMOĆNE FUNKCIJE
# ============================================================================

# Bosanski mjeseci → broj mjeseca
BS_MONTHS = {
    "januar": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "mart": 3, "mar": 3,
    "april": 4, "apr": 4,
    "maj": 5,
    "jun": 6,
    "jul": 7,
    "august": 8, "aug": 8,
    "septembar": 9, "sep": 9,
    "oktobar": 10, "okt": 10,
    "novembar": 11, "nov": 11,
    "decembar": 12, "dec": 12,
}


def _normalize_name(name: str) -> str:
    """Normalizuje ime kupca."""
    name = name.strip()
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"\s+", " ", name)
    return name


def _safe_decimal(val) -> Decimal | None:
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "nan"):
        return None
    try:
        return Decimal(s.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _safe_int(val, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(str(val).strip()))))
    except (ValueError, TypeError):
        return default


def _parse_month_from_excel(path: Path) -> tuple[int, int]:
    """
    Čita mjesec i godinu iz Excel zaglavlja.
    
    Očekuje format u redu 4:
    - Kolona 16: "Februar"
    - Kolona 19: "2026.god."
    
    Returns:
        (month, year) npr. (2, 2026)
    """
    df = pd.read_excel(str(path), header=None, nrows=10, dtype=str)
    
    # Traži red 4 (indeks 4)
    if 4 < len(df):
        row = df.iloc[4]
        
        # Traži kolonu sa "mjesec"
        month_col = None
        for col_idx in range(len(row)):
            val = str(row.iloc[col_idx]).strip().lower() if pd.notna(row.iloc[col_idx]) else ""
            if "mjesec" in val or "mesec" in val:
                month_col = col_idx + 1  # Sljedeća kolona ima naziv mjeseca
                break
        
        # Ako nismo našli oznaku "mjesec", probaj direktno kolone 16 i 19
        if month_col is None:
            month_col = 16
        
        # Čitaj mjesec i godinu
        month_str = ""
        year_str = ""
        
        if month_col < len(row):
            month_str = str(row.iloc[month_col]).strip().lower() if pd.notna(row.iloc[month_col]) else ""
        
        # Godina je obično 3 kolone poslije mjeseca
        year_col = month_col + 3
        if year_col < len(row):
            year_val = str(row.iloc[year_col]).strip().lower() if pd.notna(row.iloc[year_col]) else ""
            # Izvuci broj iz "2026.god."
            year_match = re.search(r'(\d{4})', year_val)
            if year_match:
                year_str = year_match.group(1)
        
        # Parsiraj mjesec
        month_num = None
        for bs_month, num in BS_MONTHS.items():
            if bs_month in month_str:
                month_num = num
                break
        
        # Parsiraj godinu
        year_num = int(year_str) if year_str else None
        
        if month_num and year_num:
            return month_num, year_num
    
    # Fallback: probaj iz naziva fajla
    filename = path.stem.lower()
    for bs_month, num in BS_MONTHS.items():
        if bs_month in filename:
            # Probaj naći godinu u filename
            year_match = re.search(r'(20\d{2})', filename)
            year_num = int(year_match.group(1)) if year_match else 2026
            return num, year_num
    
    # Totalni fallback
    print("⚠️  Nije moguće pročitati mjesec/godinu iz Excel-a. Koristim fallback: Februar 2026.")
    return 2, 2026


def _parse_excel_data(path: Path, first_due_date: date) -> list[dict]:
    """
    Parsira Excel fajl i vraća listu ugovora.
    """
    df = pd.read_excel(str(path), sheet_name=0, header=None, dtype=str)
    
    # Nađi početak bloka (red sa "EVIDENCIJA")
    block_start = None
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_start = i
            break
    
    if block_start is None:
        raise ValueError("Nije pronađen blok sa 'EVIDENCIJA' u Excel fajlu.")
    
    # Podatkovni redovi počinju 5 redova iza EVIDENCIJA
    data_start = block_start + 5
    
    orders: dict[str, dict] = {}  # br_ugovora → data
    
    for ri in range(data_start, len(df)):
        row = df.iloc[ri]
        
        def get(col: int) -> str:
            try:
                v = str(row.iloc[col]).strip()
                return "" if v == "nan" or pd.isna(v) else v
            except (IndexError, KeyError):
                return ""
        
        rb = get(1)  # R.br.
        br_ugovora = get(2)  # Br. ugovora
        ime = get(3)  # Ime i prezime
        sifra = get(4)  # Šifra proizvoda
        vrijed = get(5)  # Vrijednost EUR
        br_rata = get(6)  # Broj rata
        preostalo = get(20)  # Preostalo (kolona 20, 0-indeksirano = 19)
        
        # Preskoči prazne/sumarne redove
        if not rb or not br_ugovora or not ime:
            continue
        if "UKUPNO" in rb.upper() or "R." in rb:
            continue
        try:
            int(float(rb))
        except (ValueError, TypeError):
            continue
        
        # Dedupliciraj po broju ugovora
        if br_ugovora in orders:
            continue
        
        vrijed_dec = _safe_decimal(vrijed)
        preostalo_dec = _safe_decimal(preostalo)
        
        orders[br_ugovora] = {
            "br_ugovora": br_ugovora,
            "ime": _normalize_name(ime),
            "sifra": sifra,
            "vrijed_eur": vrijed_dec,
            "vrijed_bam": (vrijed_dec * EUR_TO_BAM).quantize(Decimal("0.01")) if vrijed_dec else None,
            "br_rata": _safe_int(br_rata),
            "preostalo": preostalo_dec,
            "completed": (preostalo_dec is not None and preostalo_dec <= Decimal("0.01")),
        }
    
    return list(orders.values())


# ============================================================================
# GLAVNE FUNKCIJE
# ============================================================================

def delete_existing_historical_data() -> dict:
    """
    Briše postojeće historijske podatke (narudžbe sa contract_number).
    """
    stats = {
        'payments_deleted': 0,
        'installments_deleted': 0,
        'orders_deleted': 0,
    }
    
    with session_scope() as session:
        # Pronađi sve historijske narudžbe
        historical_orders = list(
            session.execute(
                select(Order).where(Order.contract_number.is_not(None))
            ).scalars().all()
        )
        
        if VERBOSE:
            print(f"📊 Pronađeno {len(historical_orders)} historijskih narudžbi")
        
        for order in historical_orders:
            # Obriši prvo uplate
            for installment in order.installments:
                for payment in installment.payments:
                    session.delete(payment)
                    stats['payments_deleted'] += 1
                
                session.delete(installment)
                stats['installments_deleted'] += 1
            
            session.delete(order)
            stats['orders_deleted'] += 1
        
        if VERBOSE:
            print(f"   ✅ Obrisano: {stats['orders_deleted']} narudžbi, "
                  f"{stats['installments_deleted']} rata, "
                  f"{stats['payments_deleted']} uplata")
    
    return stats


def import_with_correct_dates(excel_path: str) -> dict:
    """
    Uvozi podatke sa ispravnim datumima na osnovu mjeseca iz Excel-a.
    """
    path = Path(excel_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")
    
    # 1. Pročitaj mjesec i godinu
    print("\n📅 Čitanje mjeseca i godine iz Excel-a...")
    month_num, year_num = _parse_month_from_excel(path)
    print(f"   Mjesec: {month_num} ({BS_MONTHS.get(month_num, 'nepoznat')})")
    print(f"   Godina: {year_num}")
    
    # Datum prve rate = prvi dan u mjesecu
    # (rate dospijevaju na kraju mjeseca, ali prva rata je od prvog dana)
    first_due_date = date(year_num, month_num, 1)
    print(f"   Datum prve rate: {first_due_date}")
    
    # 2. Parsiraj podatke
    print("\n📊 Parsiranje Excel podataka...")
    orders_data = _parse_excel_data(path, first_due_date)
    print(f"   Pronađeno {len(orders_data)} ugovora")
    
    # 3. Uvezi u bazu
    print("\n📦 Uvoz u bazu...")
    
    stats = {
        'customers_created': 0,
        'customers_existing': 0,
        'orders_created': 0,
        'installments_created': 0,
    }
    
    with session_scope() as session:
        # Kampanja
        campaign = session.execute(
            select(Campaign).where(Campaign.name == HISTORICAL_CAMPAIGN_NAME)
        ).scalars().first()
        
        if campaign is None:
            campaign = Campaign(
                name=HISTORICAL_CAMPAIGN_NAME,
                status=CampaignStatus.ARCHIVED,
                start_date=date(year_num, month_num, 1),
                end_date=date(year_num, month_num + 2 if month_num < 12 else 1, 
                             1 if month_num < 12 else year_num + 1),
            )
            session.add(campaign)
            session.flush()
        
        campaign_id = campaign.id
        
        # Mapa kupaca
        existing_customers: dict[str, int] = {}
        for cust in session.execute(select(Customer)).scalars():
            key = _normalize_name(cust.full_name).lower()
            existing_customers[key] = cust.id
        
        # Uvoz
        for order_data in orders_data:
            name = order_data["ime"]
            name_key = name.lower()
            
            # Kupac
            if name_key not in existing_customers:
                customer = Customer(full_name=name, is_active=True)
                session.add(customer)
                session.flush()
                existing_customers[name_key] = customer.id
                stats['customers_created'] += 1
            else:
                stats['customers_existing'] += 1
            
            customer_id = existing_customers[name_key]
            
            # Provjeri da li ugovor već postoji
            existing_order = session.execute(
                select(Order).where(Order.contract_number == order_data["br_ugovora"])
            ).scalars().first()
            
            if existing_order is not None:
                if VERBOSE:
                    print(f"   ⚠️  Ugovor {order_data['br_ugovora']} već postoji - preskačem")
                continue
            
            price = order_data["vrijed_bam"] or Decimal("0.00")
            status = OrderStatus.COMPLETED if order_data["completed"] else OrderStatus.ACTIVE
            
            # Odredi datum narudžbe (prvi dan mjeseca)
            order_date = first_due_date
            
            order = Order(
                customer_id=customer_id,
                campaign_id=campaign_id,
                product_name_snapshot=order_data["sifra"] or "—",
                unit_price_snapshot=price,
                total_price_snapshot=price,
                installments_count=order_data["br_rata"],
                status=status,
                contract_number=order_data["br_ugovora"],
                order_date=order_date,
                first_due_date=order_date,  # Prva rata dospijeva na kraju mjeseca
                note=f"Uvezeno iz {path.stem}. Originalna vrijednost: {order_data['vrijed_eur']} EUR",
            )
            session.add(order)
            session.flush()
            
            # Generiši rate
            installments = InstallmentService.generate_for_order(order)
            for inst in installments:
                session.add(inst)
            
            stats['orders_created'] += 1
            stats['installments_created'] += len(installments)
            
            if VERBOSE and stats['orders_created'] <= 5:
                print(f"   ✅ {order_data['br_ugovora']}: {name}, "
                      f"{price:.2f} KM, {order_data['br_rata']} rata, "
                      f"prva rata: {first_due_date}")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    """Glavna funkcija."""
    print("\n" + "="*70)
    print("🔧 FIX: Ponovni uvoz sa ispravnim datumima (iz mjeseca u Excel-u)")
    print("="*70)
    
    print(f"\n📁 Excel fajl: {EXCEL_PATH}")
    
    # Provjeri da li fajl postoji
    if not Path(EXCEL_PATH).exists():
        print(f"\n❌ GREŠKA: Fajl nije pronađen: {EXCEL_PATH}")
        sys.exit(1)
    
    # Da li brisati postojeće?
    if DELETE_EXISTING:
        print("\n⚠️  UPOZORENJE: Ovo će obrisati POSTOJEĆE historijske podatke!")
        print("   (narudžbe sa contract_number)")
        response = input("\n   Da li si sigurno da želiš nastaviti? (DA/ne): ").strip().upper()
        if response != 'DA':
            print("   Odustao/la.")
            sys.exit(0)
        
        print("\n🗑️  Brisanje postojećih podataka...")
        delete_stats = delete_existing_historical_data()
    
    # Uvezi nove podatke
    print("\n📥 Pokrećem uvoz sa ispravnim datumima...")
    import_stats = import_with_correct_dates(EXCEL_PATH)
    
    # Sažetak
    print("\n" + "="*70)
    print("📊 SAŽETAK UVOZA")
    print("="*70)
    
    if DELETE_EXISTING:
        print(f"  🗑️  Obrisano narudžbi:    {delete_stats.get('orders_deleted', 0)}")
        print(f"  🗑️  Obrisano rata:        {delete_stats.get('installments_deleted', 0)}")
        print(f"  🗑️  Obrisano uplata:      {delete_stats.get('payments_deleted', 0)}")
        print()
    
    print(f"  ✅ Kreirano kupaca:     {import_stats['customers_created']}")
    print(f"  ℹ️  Već postoji kupaca:  {import_stats['customers_existing']}")
    print(f"  ✅ Kreirano narudžbi:   {import_stats['orders_created']}")
    print(f"  ✅ Kreirano rata:       {import_stats['installments_created']}")
    print("="*70)
    
    print("\n✅ UVOZ ZAVRŠEN!")
    print("\n📝 SLEDEĆI KORACI:")
    print("   1. Zatvori ovu skriptu")
    print("   2. Pokreni aplikaciju: python run.py")
    print("   3. Provjeri stranicu 'Kupci' i 'Rate' - datumi bi trebali biti ispravni")
    print()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
