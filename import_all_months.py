#!/usr/bin/env python3
"""
Uvoz SVIH Excel tabela (svaki mjesec posebno) za kompletnu istoriju kupaca.

Ova skripta:
1. Traži sve Excel fajlove u folderu koji odgovaraju obrascu:
   4-1-11-2-1-3-Sanja-* 202*. - p.xlsx
2. Uvozi svaki fajl posebno
3. Deduplicira po broju ugovora (isti ugovor se ne uvozi dva puta)
4. Kreira kompletnu istoriju kupaca

Korištenje:
    python import_all_months.py
"""

from __future__ import annotations

import sys
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignStatus,
    Customer,
    Installment,
    InstallmentStatus,
    Order,
    OrderStatus,
    Payment,
)
from app.services.installment_service import InstallmentService


# ============================================================================
# KONFIGURACIJA
# ============================================================================

# Folder gdje su Excel fajlovi
EXCEL_FOLDER = "/home/radovan/Desktop/ASYCUDA_PRO/ostalo/"

# Pattern za traženje fajlova
EXCEL_PATTERN = r"4-1-11-2-1-3-Sanja-.*202.*\.xlsx$"

# Naziv kampanje
HISTORICAL_CAMPAIGN_NAME = "Historijat 2025-2026"

EUR_TO_BAM = Decimal("1.95583")

VERBOSE = True


# ============================================================================
# POMOĆNE FUNKCIJE
# ============================================================================

BS_MONTHS = {
    "jan": 1, "januar": 1,
    "feb": 2, "februar": 2,
    "mar": 3, "mart": 3,
    "apr": 4, "april": 4,
    "maj": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8, "august": 8,
    "sep": 9, "septembar": 9,
    "okt": 10, "oktobar": 10,
    "nov": 11, "novembar": 11,
    "dec": 12, "decembar": 12,
}


def _parse_date_from_excel_string(date_str: str, reference_year: int = 2026) -> date | None:
    if not date_str or date_str in ("nan", "", "—"):
        return None
    
    date_str = str(date_str).strip().lower()
    
    # ISO format
    iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if iso_match:
        month = int(iso_match.group(2))
        day = int(iso_match.group(3))
        try:
            return date(reference_year, month, day)
        except ValueError:
            return None
    
    # Format: "28.feb.", "31.avg."
    match = re.match(r'(\d{1,2})\.\s*([a-zčćžđš]+)\.?', date_str)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        
        month = None
        for bs_month, month_num in BS_MONTHS.items():
            if bs_month in month_str or month_str in bs_month:
                month = month_num
                break
        
        if month_str == "avg":
            month = 8
        
        if month:
            year = reference_year
            try:
                return date(year, month, day)
            except ValueError:
                return None
    
    return None


def _normalize_name(name: str) -> str:
    name = name.strip()
    import unicodedata
    name = unicodedata.normalize("NFC", name)
    import re
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
    except:
        return None


def _safe_int(val, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(str(val).strip()))))
    except:
        return default


def _parse_due_dates_from_excel(path: Path) -> list[date]:
    df = pd.read_excel(str(path), header=None, nrows=10, dtype=str)
    
    if 7 >= len(df):
        return []
    
    row = df.iloc[7]
    due_dates = []
    
    for col_idx in range(7, min(19, len(row))):
        date_val = row.iloc[col_idx]
        if pd.isna(date_val):
            continue
        
        date_str = str(date_val).strip()
        parsed_date = _parse_date_from_excel_string(date_str)
        
        if parsed_date:
            due_dates.append(parsed_date)
    
    return due_dates


def _parse_excel_data(path: Path, due_dates: list[date]) -> list[dict]:
    df = pd.read_excel(str(path), sheet_name=0, header=None, dtype=str)
    
    block_start = None
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_start = i
            break
    
    if block_start is None:
        return []
    
    data_start = block_start + 5
    orders: dict[str, dict] = {}
    
    for ri in range(data_start, len(df)):
        row = df.iloc[ri]
        
        def get(col: int) -> str:
            try:
                v = str(row.iloc[col]).strip()
                return "" if v == "nan" or pd.isna(v) else v
            except:
                return ""
        
        rb = get(1)
        br_ugovora = get(2)
        ime = get(3)
        sifra = get(4)
        vrijed = get(5)
        br_rata = get(6)
        preostalo = get(20)
        
        if not rb or not br_ugovora or not ime:
            continue
        if "UKUPNO" in rb.upper() or "R." in rb:
            continue
        try:
            int(float(rb))
        except:
            continue
        
        if br_ugovora in orders:
            continue
        
        vrijed_dec = _safe_decimal(vrijed)
        preostalo_dec = _safe_decimal(preostalo)
        
        # Odredi mjesec iz naziva fajla
        filename = path.stem.lower()
        month_num = None
        year_num = None
        
        for bs_month, num in BS_MONTHS.items():
            if bs_month in filename:
                month_num = num
                break
        
        year_match = re.search(r'(20\d{2})', filename)
        if year_match:
            year_num = int(year_match.group(1))
        
        # Datum prve rate = prvi dan mjeseca iz fajla
        if month_num and year_num:
            first_due_date = date(year_num, month_num, 1)
        else:
            first_due_date = due_dates[0] if due_dates else date.today()
        
        orders[br_ugovora] = {
            "br_ugovora": br_ugovora,
            "ime": _normalize_name(ime),
            "sifra": sifra,
            "vrijed_eur": vrijed_dec,
            "vrijed_bam": (vrijed_dec * EUR_TO_BAM).quantize(Decimal("0.01")) if vrijed_dec else None,
            "br_rata": _safe_int(br_rata),
            "preostalo": preostalo_dec,
            "completed": (preostalo_dec is not None and preostalo_dec <= Decimal("0.01")),
            "first_due_date": first_due_date,
            "month": month_num,
            "year": year_num,
        }
    
    return list(orders.values())


def find_excel_files(folder: str) -> list[Path]:
    """Pronađi sve Excel fajlove koji odgovaraju pattern-u."""
    folder_path = Path(folder)
    
    if not folder_path.exists():
        print(f"❌ Folder nije pronađen: {folder}")
        return []
    
    excel_files = []
    for file in folder_path.rglob("*.xlsx"):
        if re.search(EXCEL_PATTERN, file.name, re.IGNORECASE):
            excel_files.append(file)
    
    # Sortiraj po datumu (najstariji prvi)
    def extract_date_from_filename(path: Path) -> tuple:
        filename = path.stem.lower()
        month_num = 0
        year_num = 0
        
        for bs_month, num in BS_MONTHS.items():
            if bs_month in filename:
                month_num = num
                break
        
        year_match = re.search(r'(20\d{2})', filename)
        if year_match:
            year_num = int(year_match.group(1))
        
        return (year_num, month_num)
    
    excel_files.sort(key=extract_date_from_filename)
    
    return excel_files


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def import_all_files() -> dict:
    """Uvezi sve Excel fajlove."""
    
    print("\n🔍 Traženje Excel fajlova...")
    excel_files = find_excel_files(EXCEL_FOLDER)
    
    if not excel_files:
        print(f"❌ Nisu pronađeni Excel fajlovi u: {EXCEL_FOLDER}")
        print(f"   Pattern: {EXCEL_PATTERN}")
        return {}
    
    print(f"✅ Pronađeno {len(excel_files)} fajlova:")
    for f in excel_files:
        print(f"   • {f.name}")
    print()
    
    stats = {
        'customers_created': 0,
        'customers_existing': 0,
        'orders_created': 0,
        'orders_skipped': 0,
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
                start_date=date(2025, 9, 1),
                end_date=date(2026, 2, 28),
            )
            session.add(campaign)
            session.flush()
        
        campaign_id = campaign.id
        
        # Mapa kupaca
        existing_customers: dict[str, int] = {}
        for cust in session.execute(select(Customer)).scalars():
            key = _normalize_name(cust.full_name).lower()
            existing_customers[key] = cust.id
        
        # Mapa postojećih ugovora
        existing_contracts: set[str] = set()
        for order in session.execute(
            select(Order).where(Order.contract_number.is_not(None))
        ).scalars():
            existing_contracts.add(order.contract_number)
        
        # Uvezi svaki fajl
        for excel_path in excel_files:
            print(f"\n📂 Uvoz: {excel_path.name}")
            print(f"   {'='*60}")
            
            # Parsiraj datume
            due_dates = _parse_due_dates_from_excel(excel_path)
            if not due_dates:
                print(f"   ⚠️  Nisu pronađeni datumi - preskačem")
                continue
            
            reference_year = due_dates[0].year
            print(f"   📅 Referentna godina: {reference_year}")
            
            # Parsiraj podatke
            orders_data = _parse_excel_data(excel_path, due_dates)
            print(f"   📊 Pronađeno {len(orders_data)} ugovora")
            
            # Uvezi
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
                    if VERBOSE:
                        print(f"   + Novi kupac: {name}")
                else:
                    stats['customers_existing'] += 1
                
                customer_id = existing_customers[name_key]
                
                # Ugovor - preskoči ako već postoji
                if order_data["br_ugovora"] in existing_contracts:
                    stats['orders_skipped'] += 1
                    continue
                
                price = order_data["vrijed_bam"] or Decimal("0.00")
                status = OrderStatus.COMPLETED if order_data["completed"] else OrderStatus.ACTIVE
                
                first_due_date = order_data["first_due_date"]
                
                order = Order(
                    customer_id=customer_id,
                    campaign_id=campaign_id,
                    product_name_snapshot=order_data["sifra"] or "—",
                    unit_price_snapshot=price,
                    total_price_snapshot=price,
                    installments_count=order_data["br_rata"],
                    status=status,
                    contract_number=order_data["br_ugovora"],
                    order_date=first_due_date,
                    first_due_date=first_due_date,
                    note=f"Uvezeno iz {excel_path.stem}.",
                )
                session.add(order)
                session.flush()
                
                existing_contracts.add(order_data["br_ugovora"])
                
                # Generiši rate sa datumima
                installments = []
                allocated = Decimal("0.00")
                base_amount = (price / order_data["br_rata"]).quantize(Decimal("0.01"))
                
                for i in range(order_data["br_rata"]):
                    amount = base_amount
                    if i == order_data["br_rata"] - 1:
                        amount = price - allocated
                    allocated += amount
                    
                    due_date = due_dates[i] if i < len(due_dates) else first_due_date
                    
                    installment = Installment(
                        order=order,
                        installment_number=i + 1,
                        due_date=due_date,
                        amount=amount,
                        status=InstallmentStatus.PENDING,
                    )
                    installments.append(installment)
                    session.add(installment)
                
                stats['orders_created'] += 1
                stats['installments_created'] += len(installments)
                
                if VERBOSE and stats['orders_created'] <= 3:
                    print(f"   ✅ {order_data['br_ugovora']}: {name}, {price:.2f} KM")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    print("\n" + "="*70)
    print("📦 UVOZ SVIH MJESECI - KOMPLETNA ISTORIJA KUPACA")
    print("="*70)
    
    stats = import_all_files()
    
    print("\n" + "="*70)
    print("📊 SAŽETAK UVOZA")
    print("="*70)
    print(f"  ✅ Kreirano kupaca:     {stats.get('customers_created', 0)}")
    print(f"  ℹ️  Već postoji kupaca:  {stats.get('customers_existing', 0)}")
    print(f"  ✅ Kreirano narudžbi:   {stats.get('orders_created', 0)}")
    print(f"  ⏭️  Preskočeno (dupli): {stats.get('orders_skipped', 0)}")
    print(f"  ✅ Kreirano rata:       {stats.get('installments_created', 0)}")
    print("="*70)
    
    print("\n✅ UVOZ ZAVRŠEN!")
    print("\n📝 SADA TREBAŠ:")
    print("   1. Pokrenuti aplikaciju: python run.py")
    print("   2. Otići na Uplate")
    print("   3. Odabrati kupca")
    print("   4. Vidjeti SVE njegove rate (iz svih mjeseci)")
    print()


if __name__ == "__main__":
    main()
