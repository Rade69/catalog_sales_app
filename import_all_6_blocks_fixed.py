#!/usr/bin/env python3
"""
Uvoz svih 6 blokova sa ISPRAVNIM datumima.

Ključne popravke:
1. Godina se čita iz zaglavlja bloka (npr. "Oktobar 2025.god.")
2. Datumi iz kolona se parseuju sa tom godinom
3. Ako je mjesec u datumu < mjesec bloka, koristi se godina+1
   (npr. Oktobar 2025 + "31.jan." → 31.01.2026)
"""

from __future__ import annotations

import sys
import re
from datetime import date
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
EUR_TO_BAM = Decimal("1.0")  # Ostavi u EUR!

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


def _find_block_starts(df: pd.DataFrame) -> list[int]:
    """Pronađi sve blokove (tabele) u Excel-u."""
    block_starts = []
    
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_starts.append(int(i))
    
    return block_starts


def _parse_block_month_year(df: pd.DataFrame, block_start: int) -> tuple[int, int]:
    """
    Izvuci mjesec i godinu iz bloka.
    
    Returns:
        (month_num, year_num) npr. (10, 2025) za Oktobar 2025
    """
    month_row_idx = block_start + 1
    
    if month_row_idx >= len(df):
        return (9, 2025)
    
    month_row = df.iloc[month_row_idx]
    
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
    
    month_num = None
    for bs_month, num in BS_MONTHS.items():
        if bs_month in month_str or month_str in bs_month:
            month_num = num
            break
    
    year_num = int(year_str) if year_str else 2026
    
    return (month_num or 9, year_num)


def _parse_date_from_column(date_str: str, block_month: int, block_year: int) -> date | None:
    """
    Parsira datum iz kolone (npr. "28.feb.", "31.okt.").
    
    Args:
        date_str: String iz kolone (npr. "28.feb.")
        block_month: Mjesec bloka (npr. 10 za Oktobar)
        block_year: Godina bloka (npr. 2025)
    
    Returns:
        date objekat
    
    Logika:
        - Ako je mjesec u datumu >= block_month → koristi block_year
        - Ako je mjesec u datumu < block_month → koristi block_year + 1
          (npr. Oktobar 2025 + "31.jan." → 31.01.2026)
    """
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
            # Odredi godinu
            if month < block_month:
                # Mjesec je manji → sljedeća godina
                year = block_year + 1
            else:
                # Mjesec je isti ili veći → ista godina
                year = block_year
            
            try:
                return date(year, month, day)
            except ValueError:
                return None
    
    # Pokušaj ISO format (ako je pandas već konvertovao)
    # ALI: Ignoriši godinu iz ISO formata ako je 2023 (greška u Excel-u)
    # Koristi godinu iz bloka
    iso_match = re.match(r'\d{4}-(\d{2})-(\d{2})', date_str)
    if iso_match:
        month = int(iso_match.group(1))
        day = int(iso_match.group(2))
        
        # Odredi godinu na osnovu block_month
        if month < block_month:
            year = block_year + 1
        else:
            year = block_year
        
        try:
            return date(year, month, day)
        except ValueError:
            return None
    
    return None


def _parse_due_dates(df: pd.DataFrame, block_start: int, block_month: int, block_year: int) -> list[date]:
    """Izvuci datume dospijeća rata iz bloka (red 7)."""
    date_row_idx = block_start + 4
    
    if date_row_idx >= len(df):
        return []
    
    date_row = df.iloc[date_row_idx]
    due_dates = []
    
    for col in range(7, min(19, len(date_row))):
        date_val = date_row.iloc[col]
        if pd.isna(date_val):
            continue
        
        date_str = str(date_val).strip()
        parsed = _parse_date_from_column(date_str, block_month, block_year)
        
        if parsed:
            due_dates.append(parsed)
    
    return due_dates


def _parse_orders_in_block(df: pd.DataFrame, block_start: int, block_end: int, 
                           due_dates: list[date], month_num: int, year_num: int) -> list[dict]:
    """Parsiraj sve ugovore u bloku."""
    orders = []
    
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
        
        if not rb or not br_ugovora or not ime:
            continue
        if "UKUPNO" in rb.upper() or "R." in rb:
            continue
        try:
            int(float(rb))
        except:
            continue
        
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
    
    df = pd.read_excel(str(path), header=None, dtype=str)
    print(f"Ukupno redova: {len(df)}")
    
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
        
        existing_customers: dict[str, int] = {}
        for cust in session.execute(select(Customer)).scalars():
            key = _normalize_name(cust.full_name).lower()
            existing_customers[key] = cust.id
        
        existing_contracts: set[str] = set()
        for order in session.execute(
            select(Order).where(Order.contract_number.is_not(None))
        ).scalars():
            existing_contracts.add(order.contract_number)
        
        for idx, block_start in enumerate(block_starts):
            block_end = block_starts[idx + 1] if idx + 1 < len(block_starts) else len(df)
            
            print(f"\n{'='*80}")
            print(f"BLOK {idx + 1}/{len(block_starts)}: Redovi {block_start}-{block_end-1}")
            print("="*80)
            
            month_num, year_num = _parse_block_month_year(df, block_start)
            print(f"Mjesec: {month_num} (Godina: {year_num})")
            
            due_dates = _parse_due_dates(df, block_start, month_num, year_num)
            print(f"Datumi rata: {len(due_dates)} (prvi: {due_dates[0] if due_dates else 'N/A'})")
            
            orders_data = _parse_orders_in_block(df, block_start, block_end, due_dates, month_num, year_num)
            print(f"Broj ugovora: {len(orders_data)}")
            
            for order_data in orders_data:
                name = order_data["ime"]
                name_key = name.lower()
                
                if name_key not in existing_customers:
                    customer = Customer(full_name=name, is_active=True)
                    session.add(customer)
                    session.flush()
                    existing_customers[name_key] = customer.id
                    stats['customers_created'] += 1
                else:
                    stats['customers_existing'] += 1
                
                customer_id = existing_customers[name_key]
                
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
                
                installments = []
                allocated = Decimal("0.00")
                base_amount = (price / order_data["br_rata"]).quantize(Decimal("0.01"))
                
                for i in range(order_data["br_rata"]):
                    amount = base_amount
                    if i == order_data["br_rata"] - 1:
                        amount = price - allocated
                    allocated += amount
                    
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
                    print(f"  ✅ {order_data['br_ugovora']}: {name}, {price:.2f} EUR, {order_data['br_rata']} rata")
                    print(f"      Prva rata: {first_due_date}")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    print("\n" + "="*80)
    print("📦 UVOZ SVIH 6 BLOKOVA SA ISPRAVNIM DATUMIMA")
    print("Datumi se čitaju iz kolona + godina iz zaglavlja")
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
    print("\n📝 SLEDEĆI KORACI:")
    print("   1. Kreiraj uplate: python create_payments_from_all_blocks.py")
    print("   2. Sinhronizuj statuse: python3 -c 'from app.services.installment_service import InstallmentService; InstallmentService.sync_statuses()'")
    print("   3. Pokreni aplikaciju: python run.py")
    print()


if __name__ == "__main__":
    main()
