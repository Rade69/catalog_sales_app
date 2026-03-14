#!/usr/bin/env python3
"""
FIX: Kreiraj Payment zapise iz Excel kolona (I, II, III, IV...).

U Excel tabelama, plaćene rate su upisane u kolonama:
- Kolona H (index 7) = Rata I (datum: 28.feb.)
- Kolona I (index 8) = Rata II (datum: 31.mar.)
- Kolona J (index 9) = Rata III (datum: 30.apr.)
- itd.

Ako u koloni postoji broj → rata je plaćena
Ako je prazno → rata nije plaćena

Ova skripta:
1. Učitava Excel fajl
2. Za svaki ugovor, čita kolone I-XII
3. Kreira Payment za svaku ratu gdje postoji iznos
4. Ažurira status rate na PAID
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
    Order,
    Installment,
    InstallmentStatus,
    Payment,
)


# ============================================================================
# KONFIGURACIJA
# ============================================================================

EXCEL_PATH = "/home/radovan/Desktop/ASYCUDA_PRO/ostalo/fwdpogodnosti0326cjenovnik02_03_2026_/4-1-11-2-1-3-Sanja-februar 2026. - p.xlsx"

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

def _find_block_starts(df: pd.DataFrame) -> list[int]:
    """Pronađi sve blokove (tabele) u Excel-u."""
    block_starts = []
    
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_starts.append(int(i))
    
    return block_starts


def _parse_block_month(df: pd.DataFrame, block_start: int) -> tuple[int, int]:
    """Izvuci mjesec i godinu iz bloka."""
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


def _parse_date_string(date_str: str, reference_year: int) -> date | None:
    """Parsira datum iz formata '28.feb.', '31.jan.', itd."""
    if not date_str or date_str in ("nan", "", "—"):
        return None
    
    date_str = str(date_str).strip().lower()
    
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


def _parse_due_dates(df: pd.DataFrame, block_start: int, reference_year: int) -> list[date]:
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
        parsed = _parse_date_string(date_str, reference_year)
        
        if parsed:
            due_dates.append(parsed)
    
    return due_dates


def _parse_payments_from_block(df: pd.DataFrame, block_start: int, block_end: int,
                                due_dates: list[date], reference_year: int) -> list[dict]:
    """
    Parsiraj ugovore i njihove uplate iz bloka.
    
    Za svaki red:
    - Kolona 2 (C) = Br. ugovora
    - Kolona 7-18 (H-XII) = Iznosi uplata za rate I-XII
    """
    data_start = block_start + 5
    orders = []
    
    for ri in range(data_start, block_end):
        row = df.iloc[ri]
        
        def get(col: int):
            try:
                v = row.iloc[col]
                if pd.isna(v):
                    return None
                return str(v).strip()
            except:
                return None
        
        br_ugovora = get(2)
        
        if not br_ugovora:
            continue
        
        # Čitaj uplate iz kolona 7-18 (H-XII)
        payments = []
        for col_idx in range(7, min(19, len(row))):
            payment_val = get(col_idx)
            
            if payment_val and payment_val not in ("nan", "", "—"):
                # Pokušaj parsirati broj
                try:
                    # Zamijeni zarez sa tačkom
                    payment_str = payment_val.replace(",", ".")
                    payment_amount = Decimal(payment_str)
                    
                    if payment_amount > 0:
                        # Rata je plaćena
                        payment_date = due_dates[col_idx - 7] if (col_idx - 7) < len(due_dates) else None
                        
                        payments.append({
                            'installment_number': col_idx - 6,  # 1-based (kolona 7 = rata 1)
                            'amount': payment_amount,
                            'payment_date': payment_date,
                        })
                except:
                    pass
        
        if payments:
            orders.append({
                'br_ugovora': br_ugovora,
                'payments': payments,
            })
    
    return orders


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def create_payments_from_excel() -> dict:
    """Kreiraj Payment zapise iz Excel kolona."""
    
    path = Path(EXCEL_PATH)
    
    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")
    
    print(f"\n📂 Čitanje uplata iz: {path.name}")
    print("="*80)
    
    # Učitaj Excel
    df = pd.read_excel(str(path), header=None, dtype=str)
    print(f"Ukupno redova: {len(df)}")
    
    # Pronađi blokove
    block_starts = _find_block_starts(df)
    print(f"Pronađeno blokova: {len(block_starts)}")
    
    stats = {
        'orders_with_payments': 0,
        'payments_created': 0,
        'installments_updated': 0,
        'orders_skipped': 0,
    }
    
    with session_scope() as session:
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
            print(f"Datumi rata: {len(due_dates)}")
            
            # 3. Parsiraj uplate
            orders_data = _parse_payments_from_block(df, block_start, block_end, due_dates, year_num)
            print(f"Ugovora sa uplatama: {len(orders_data)}")
            
            # 4. Kreiraj Payment zapise
            for order_data in orders_data:
                br_ugovora = order_data['br_ugovora']
                payments = order_data['payments']
                
                # Pronađi narudžbu
                order = session.execute(
                    select(Order)
                    .where(Order.contract_number == br_ugovora)
                    .options(joinedload(Order.installments))
                ).scalars().first()
                
                if not order:
                    print(f"  ⚠️  Ugovor {br_ugovora} nije pronađen - preskačem")
                    stats['orders_skipped'] += 1
                    continue
                
                # Pronađi rate
                installments = {inst.installment_number: inst for inst in order.installments}
                
                # Kreiraj Payment za svaku uplatu
                for payment_data in payments:
                    inst_num = payment_data['installment_number']
                    
                    if inst_num not in installments:
                        continue
                    
                    installment = installments[inst_num]
                    
                    # Provjeri da li već postoji uplata
                    existing_payment = session.execute(
                        select(Payment)
                        .where(Payment.installment_id == installment.id)
                    ).scalars().first()
                    
                    if existing_payment:
                        continue  # Već postoji uplata
                    
                    # Kreiraj uplatu
                    payment = Payment(
                        installment_id=installment.id,
                        payment_date=payment_data['payment_date'] or installment.due_date,
                        amount=payment_data['amount'],
                        note="Automatski kreirano iz Excel-a",
                    )
                    session.add(payment)
                    
                    # Ažuriraj status rate
                    installment.status = InstallmentStatus.PAID
                    installment.paid_at = payment.payment_date
                    
                    stats['payments_created'] += 1
                    stats['installments_updated'] += 1
                
                stats['orders_with_payments'] += 1
                
                if stats['orders_with_payments'] <= 3:
                    print(f"  ✅ {br_ugovora}: {len(payments)} uplata kreirano")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    print("\n" + "="*80)
    print("💳 KREIRANJE UPLATA IZ EXCEL KOLONA")
    print("Čita kolone I, II, III, IV... i kreira Payment zapise")
    print("="*80)
    
    stats = create_payments_from_excel()
    
    print("\n" + "="*80)
    print("📊 SAŽETAK")
    print("="*80)
    print(f"  ✅ Ugovora sa uplatama:  {stats['orders_with_payments']}")
    print(f"  ✅ Kreirano uplata:      {stats['payments_created']}")
    print(f"  ✅ Ažurirano rata:       {stats['installments_updated']}")
    print(f"  ⚠️  Preskočeno ugovora:  {stats['orders_skipped']}")
    print("="*80)
    
    print("\n✅ KREIRANJE UPLATA ZAVRŠENO!")
    print("\n📝 SADA TREBAŠ:")
    print("   1. Pokrenuti aplikaciju: python run.py")
    print("   2. Otići na Uplate")
    print("   3. Odabrati kupca")
    print("   4. Vidjeti koje su rate plaćene (zelene), a koje ne (crvene)")
    print()


if __name__ == "__main__":
    main()
