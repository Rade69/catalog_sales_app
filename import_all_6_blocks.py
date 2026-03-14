#!/usr/bin/env python3
"""
Uvoz SVIH 6 BLOKOVA iz jednog Excel fajla (Septembar 2025 - Februar 2026).

Ovaj fajl sadrži 6 tabela (po mjesecima):
1. Septembar 2025. (10 ugovora)
2. Oktobar 2025. (20 ugovora)
3. Novembar 2025. (20 ugovora)
4. Decembar 2025. (20 ugovora)
5. Januar 2026. (20 ugovora)
6. Februar 2026. (20 ugovora)

UKUPNO: 110 ugovora, ~1100 rata
"""

from __future__ import annotations

import sys
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from sqlalchemy import select
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
)
from app.services.installment_service import InstallmentService


# ============================================================================
# KONFIGURACIJA
# ============================================================================

EXCEL_PATH = "/home/radovan/Desktop/ASYCUDA_PRO/ostalo/fwdpogodnosti0326cjenovnik02_03_2026_/4-1-11-2-1-3-Sanja-februar 2026. - p.xlsx"
HISTORICAL_CAMPAIGN_NAME = "Historijat 2025-2026"
EUR_TO_BAM = Decimal("1.0")  # NE KONVERTUJ - ostavi u EUR!

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


# ============================================================================
# POMOĆNE FUNKCIJE
# ============================================================================

def _normalize_name(name: str) -> str:
    import unicodedata
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
    except:
        return None


def _safe_int(val, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(str(val).strip()))))
    except:
        return default


def _parse_date_string(date_str: str, reference_year: int) -> date | None:
    """Parsira datum iz formata '28.feb.', '31.jan.', itd."""
    if not date_str or date_str in ("nan", "", "—"):
        return None
    
    date_str = str(date_str).strip().lower()
    
    # Format: "28.feb."
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
            try:
                return date(reference_year, month, day)
            except ValueError:
                return None
    
    return None


def _find_block_starts(df: pd.DataFrame) -> list[int]:
    """Pronađi sve blokove (tabele) u Excel-u."""
    block_starts = []
    
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_starts.append(int(i))
    
    return block_starts


def _parse_block_month(df: pd.DataFrame, block_start: int) -> tuple[int, int]:
    """
    Izvuci mjesec i godinu iz bloka.
    
    Returns:
        (month_num, year_num) npr. (9, 2025) za Septembar 2025
    """
    # Red block_start+1 sadrži informacije o mjesecu (red 4 za prvi blok)
    month_row_idx = block_start + 1
    
    if month_row_idx >= len(df):
        return (9, 2025)  # Fallback
    
    month_row = df.iloc[month_row_idx]
    
    # Kolona 16 (indeks 16) sadrži naziv mjeseca
    # Kolona 19 (indeks 19) sadrži godinu
    month_str = ""
    year_str = ""
    
    if 16 < len(month_row):
        month_val = month_row.iloc[16]
        if pd.notna(month_val):
            month_str = str(month_val).strip().lower()
    
    if 19 < len(month_row):
        year_val = month_row.iloc[19]
        if pd.notna(year_val):
            year_str = str(year_val)
            year_match = re.search(r'(\d{4})', year_str)
            if year_match:
                year_str = year_match.group(1)
            else:
                year_str = ""
    
    # Parsiraj mjesec
    month_num = None
    for bs_month, num in BS_MONTHS.items():
        if bs_month in month_str or month_str in bs_month:
            month_num = num
            break
    
    # Parsiraj godinu
    year_num = int(year_str) if year_str else 2026
    
    print(f"   [DEBUG] month_str='{month_str}', year_str='{year_str}' → ({month_num}, {year_num})")
    
    return (month_num or 9, year_num)


def _parse_due_dates(df: pd.DataFrame, block_start: int, reference_year: int) -> list[date]:
    """Izvuci datume dospijeća rata iz bloka (red 7)."""
    date_row_idx = block_start + 4  # Red 7 za prvi blok
    
    if date_row_idx >= len(df):
        return []
    
    date_row = df.iloc[date_row_idx]
    due_dates = []
    
    # Kolone 7-18 (H-XII) sadrže datume
    for col in range(7, min(19, len(date_row))):
        date_val = date_row.iloc[col]
        if pd.isna(date_val):
            continue
        
        date_str = str(date_val).strip()
        parsed = _parse_date_string(date_str, reference_year)
        
        if parsed:
            due_dates.append(parsed)
    
    return due_dates


def _parse_orders_in_block(df: pd.DataFrame, block_start: int, block_end: int, 
                           due_dates: list[date], month_num: int, year_num: int) -> list[dict]:
    """Parsiraj sve ugovore u bloku."""
    orders = []
    
    # Podatkovni redovi počinju 5 redova iza EVIDENCIJA
    data_start = block_start + 5
    
    seen_contracts = set()
    
    for ri in range(data_start, block_end):
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
        
        # Preskoči nevalidne redove
        if not rb or not br_ugovora or not ime:
            continue
        if "UKUPNO" in rb.upper() or "R." in rb:
            continue
        try:
            int(float(rb))
        except:
            continue
        
        # Preskoči duplikate
        if br_ugovora in seen_contracts:
            continue
        
        seen_contracts.add(br_ugovora)
        
        vrijed_dec = _safe_decimal(vrijed)
        preostalo_dec = _safe_decimal(preostalo)
        
        # Datum prve rate = prvi datum iz due_dates
        first_due_date = due_dates[0] if due_dates else date(year_num, month_num, 1)
        
        orders.append({
            "br_ugovora": br_ugovora,
            "ime": _normalize_name(ime),
            "sifra": sifra,
            "vrijed_eur": vrijed_dec,
            "vrijed_bam": (vrijed_dec * EUR_TO_BAM).quantize(Decimal("0.01")) if vrijed_dec else None,
            "br_rata": _safe_int(br_rata),
            "preostalo": preostalo_dec,
            "completed": (preostalo_dec is not None and preostalo_dec <= Decimal("0.01")),
            "first_due_date": first_due_date,
            "due_dates": due_dates,
            "month": month_num,
            "year": year_num,
        })
    
    return orders


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def import_all_blocks() -> dict:
    """Uvezi svih 6 blokova iz Excel fajla."""
    
    path = Path(EXCEL_PATH)
    
    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")
    
    print(f"\n📂 Uvoz: {path.name}")
    print("="*80)
    
    # Učitaj Excel
    df = pd.read_excel(str(path), header=None, dtype=str)
    print(f"Ukupno redova: {len(df)}")
    
    # Pronađi blokove
    block_starts = _find_block_starts(df)
    print(f"Pronađeno blokova: {len(block_starts)}")
    
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
        
        # Procesuiraj svaki blok
        for idx, block_start in enumerate(block_starts):
            block_end = block_starts[idx + 1] if idx + 1 < len(block_starts) else len(df)
            
            print(f"\n{'='*80}")
            print(f"BLOK {idx + 1}/{len(block_starts)}: Redovi {block_start}-{block_end-1}")
            print("="*80)
            
            # 1. Izvuci mjesec i godinu
            month_num, year_num = _parse_block_month(df, block_start)
            print(f"Mjesec: {month_num} (Godina: {year_num})")
            
            # 2. Izvuci datume dospijeća
            due_dates = _parse_due_dates(df, block_start, year_num)
            print(f"Datumi rata: {len(due_dates)} ({due_dates[0] if due_dates else 'N/A'} ...)")
            
            # 3. Parsiraj ugovore
            orders_data = _parse_orders_in_block(df, block_start, block_end, due_dates, month_num, year_num)
            print(f"Broj ugovora: {len(orders_data)}")
            
            # 4. Uvezi u bazu
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
                    note=f"Uvezeno iz {path.stem} ({order_data['month']}/{order_data['year']}). Svi iznosi u EUR.",
                )
                session.add(order)
                session.flush()
                
                existing_contracts.add(order_data["br_ugovora"])
                
                # Generiši rate sa TAČNIM datumima
                installments = []
                allocated = Decimal("0.00")
                base_amount = (price / order_data["br_rata"]).quantize(Decimal("0.01"))
                
                for i in range(order_data["br_rata"]):
                    amount = base_amount
                    if i == order_data["br_rata"] - 1:
                        amount = price - allocated
                    allocated += amount
                    
                    # Koristi datum iz Excel-a
                    due_date = order_data["due_dates"][i] if i < len(order_data["due_dates"]) else first_due_date
                    
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
                
                if stats['orders_created'] <= 3:
                    print(f"  ✅ {order_data['br_ugovora']}: {name}, {price:.2f} KM, {order_data['br_rata']} rata")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    print("\n" + "="*80)
    print("📦 UVOZ SVIH 6 BLOKOVA IZ JEDNOG EXCEL FAJLA")
    print("Septembar 2025 - Februar 2026")
    print("="*80)
    
    stats = import_all_blocks()
    
    print("\n" + "="*80)
    print("📊 SAŽETAK UVOZA")
    print("="*80)
    print(f"  ✅ Kreirano kupaca:      {stats['customers_created']}")
    print(f"  ℹ️  Već postoji kupaca:   {stats['customers_existing']}")
    print(f"  ✅ Kreirano narudžbi:    {stats['orders_created']}")
    print(f"  ⏭️  Preskočeno (dupli):  {stats['orders_skipped']}")
    print(f"  ✅ Kreirano rata:        {stats['installments_created']}")
    print("="*80)
    
    print("\n✅ UVOZ ZAVRŠEN!")
    print("\n📝 SADA TREBAŠ:")
    print("   1. Pokrenuti aplikaciju: python run.py")
    print("   2. Otići na Uplate")
    print("   3. Odabrati kupca")
    print("   4. Vidjeti SVE njegove rate (od Septembra 2025. do Februara 2026.)")
    print()


if __name__ == "__main__":
    main()
