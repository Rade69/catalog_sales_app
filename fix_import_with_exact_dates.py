#!/usr/bin/env python3
"""
FIX: Uvoz sa TAČNIM datumima rata iz Excel zaglavlja.

Ova skripta:
1. Čita datume dospijeća iz Excel zaglavlja (red 7, kolone H-XII)
   Primjer: "28.feb.", "31.mar.", "30.apr.", ...
2. Koristi te datume za dospijeće rata
3. Prva rata = datum iz kolone "I" (npr. 28.02.2026)
4. Druga rata = datum iz kolone "II" (npr. 31.03.2026)
5. itd.

Korištenje:
    python fix_import_with_exact_dates.py
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
    Payment,
)
from app.services.installment_service import InstallmentService


# ============================================================================
# KONFIGURACIJA
# ============================================================================

EXCEL_PATH = "/home/radovan/Desktop/ASYCUDA_PRO/ostalo/fwdpogodnosti0326cjenovnik02_03_2026_/4-1-11-2-1-3-Sanja-februar 2026. - p.xlsx"
HISTORICAL_CAMPAIGN_NAME = "Historijat 2025-2026"
EUR_TO_BAM = Decimal("1.95583")
DELETE_EXISTING = True
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
    """
    Parsira datum iz Excel stringa npr. "28.feb.", "31.mar.", "30.apr.", "31.avg."
    
    Args:
        date_str: String iz Excel-a (npr. "28.feb.")
        reference_year: Godina koju koristimo ako nije navedena
    
    Returns:
        date objekat ili None
    """
    if not date_str or date_str in ("nan", "", "—"):
        return None
    
    date_str = str(date_str).strip().lower()
    
    # Pokušaj parseovati ISO format prvo (ako je pandas već konvertovao)
    # npr. "2023-06-30 00:00:00" → ovo su greške iz Excel-a, ignoriši godinu
    iso_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if iso_match:
        # Uzmi samo dan i mjesec, godinu zamijeni sa reference_year
        month = int(iso_match.group(2))
        day = int(iso_match.group(3))
        try:
            return date(reference_year, month, day)
        except ValueError:
            return None
    
    # Pokušaj parseovati format: "28.feb.", "31.avg."
    match = re.match(r'(\d{1,2})\.\s*([a-zčćžđš]+)\.?', date_str)
    if match:
        day = int(match.group(1))
        month_str = match.group(2)
        
        # Nađi mjesec - podrži i "avg" za august
        month = None
        for bs_month, month_num in BS_MONTHS.items():
            if bs_month in month_str or month_str in bs_month:
                month = month_num
                break
        
        # Posebno za "avg" → august (8)
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


def _parse_due_dates_from_excel(path: Path) -> list[date]:
    """
    Čita datume dospijeća iz Excel zaglavlja (red 7).
    
    Format:
    - Kolona H (index 7): "28.feb." ← Rata I
    - Kolona I (index 8): "31.mar." ← Rata II
    - Kolona J (index 9): "30.apr." ← Rata III
    - ...
    
    Returns:
        Lista datum aza svaku ratu (max 12)
    """
    df = pd.read_excel(str(path), header=None, nrows=10, dtype=str)
    
    # Red 7 (indeks 7) sadrži datume
    if 7 >= len(df):
        print("⚠️  Nije pronađen red 7 sa datumima. Koristim fallback.")
        return []
    
    row = df.iloc[7]
    
    due_dates = []
    
    # Kolone 7-18 (H-XII) sadrže datume za rate I-XII
    for col_idx in range(7, min(19, len(row))):
        date_val = row.iloc[col_idx]
        if pd.isna(date_val):
            continue
        
        date_str = str(date_val).strip()
        
        # Parsiraj datum
        parsed_date = _parse_date_from_excel_string(date_str)
        
        if parsed_date:
            due_dates.append(parsed_date)
            if VERBOSE and len(due_dates) <= 3:
                print(f"   Kolona {col_idx}: '{date_str}' → {parsed_date}")
        else:
            if VERBOSE:
                print(f"   Kolona {col_idx}: '{date_str}' → nije prepoznato")
    
    if VERBOSE:
        print(f"   Ukupno datuma: {len(due_dates)}")
    
    return due_dates


def _parse_excel_data(path: Path, due_dates: list[date]) -> list[dict]:
    """
    Parsira Excel fajl i vraća listu ugovora.
    """
    df = pd.read_excel(str(path), sheet_name=0, header=None, dtype=str)
    
    # Nađi početak bloka
    block_start = None
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_start = i
            break
    
    if block_start is None:
        raise ValueError("Nije pronađen blok sa 'EVIDENCIJA'.")
    
    data_start = block_start + 5
    orders: dict[str, dict] = {}
    
    for ri in range(data_start, len(df)):
        row = df.iloc[ri]
        
        def get(col: int) -> str:
            try:
                v = str(row.iloc[col]).strip()
                return "" if v == "nan" or pd.isna(v) else v
            except (IndexError, KeyError):
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
        except (ValueError, TypeError):
            continue
        
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


def delete_existing_historical_data() -> dict:
    stats = {'payments_deleted': 0, 'installments_deleted': 0, 'orders_deleted': 0}
    
    with session_scope() as session:
        historical_orders = list(session.execute(
            select(Order).where(Order.contract_number.is_not(None))
        ).scalars().all())
        
        for order in historical_orders:
            for installment in order.installments:
                for payment in installment.payments:
                    session.delete(payment)
                    stats['payments_deleted'] += 1
                session.delete(installment)
                stats['installments_deleted'] += 1
            session.delete(order)
            stats['orders_deleted'] += 1
    
    return stats


def import_with_exact_dates(excel_path: str) -> dict:
    path = Path(excel_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")
    
    # 1. Pročitaj datume iz Excel-a
    print("\n📅 Čitanje datuma dospijeća iz Excel zaglavlja...")
    due_dates = _parse_due_dates_from_excel(path)
    
    if not due_dates:
        print("⚠️  Nisu pronađeni datumi! Koristim fallback: 28.02.2026 + mjesečno.")
        from dateutil.relativedelta import relativedelta
        base_date = date(2026, 2, 28)
        due_dates = [base_date + relativedelta(months=i) for i in range(12)]
    
    # Odredi godinu iz prvog datuma
    reference_year = due_dates[0].year if due_dates else 2026
    print(f"   Referentna godina: {reference_year}")
    
    # 2. Parsiraj podatke
    print("\n📊 Parsiranje Excel podataka...")
    orders_data = _parse_excel_data(path, due_dates)
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
                start_date=due_dates[0] if due_dates else date.today(),
                end_date=due_dates[-1] if len(due_dates) > 11 else date.today(),
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
            
            if name_key not in existing_customers:
                customer = Customer(full_name=name, is_active=True)
                session.add(customer)
                session.flush()
                existing_customers[name_key] = customer.id
                stats['customers_created'] += 1
            else:
                stats['customers_existing'] += 1
            
            customer_id = existing_customers[name_key]
            
            existing_order = session.execute(
                select(Order).where(Order.contract_number == order_data["br_ugovora"])
            ).scalars().first()
            
            if existing_order is not None:
                if VERBOSE:
                    print(f"   ⚠️  Ugovor {order_data['br_ugovora']} već postoji - preskačem")
                continue
            
            price = order_data["vrijed_bam"] or Decimal("0.00")
            status = OrderStatus.COMPLETED if order_data["completed"] else OrderStatus.ACTIVE
            
            # Datum prve rate = prvi datum iz Excel-a
            first_due_date = due_dates[0] if due_dates else date.today()
            
            order = Order(
                customer_id=customer_id,
                campaign_id=campaign_id,
                product_name_snapshot=order_data["sifra"] or "—",
                unit_price_snapshot=price,
                total_price_snapshot=price,
                installments_count=order_data["br_rata"],
                status=status,
                contract_number=order_data["br_ugovora"],
                order_date=first_due_date,  # Dan preuzimanja = dan prve rate
                first_due_date=first_due_date,
                note=f"Uvezeno iz {path.stem}. Datumi iz Excel zaglavlja.",
            )
            session.add(order)
            session.flush()
            
            # Generiši rate sa TAČNIM datumima iz Excel-a
            installments = []
            allocated = Decimal("0.00")
            base_amount = (price / order_data["br_rata"]).quantize(Decimal("0.01"))
            
            for i in range(order_data["br_rata"]):
                amount = base_amount
                if i == order_data["br_rata"] - 1:
                    amount = price - allocated
                allocated += amount
                
                # Koristi datum iz Excel-a ako postoji
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
            
            if VERBOSE and stats['orders_created'] <= 5:
                print(f"   ✅ {order_data['br_ugovora']}: {name}, {price:.2f} KM, "
                      f"{order_data['br_rata']} rata")
                for inst in installments[:3]:
                    print(f"      Rata {inst.installment_number}: {inst.amount:.2f} KM, "
                          f"Dospijeće: {inst.due_date}")
    
    return stats


# ============================================================================
# GLAVNA FUNKCIJA
# ============================================================================

def main() -> None:
    print("\n" + "="*70)
    print("🔧 FIX: Uvoz sa TAČNIM datumima iz Excel zaglavlja")
    print("="*70)
    print(f"\n📁 Excel fajl: {EXCEL_PATH}")
    
    if not Path(EXCEL_PATH).exists():
        print(f"\n❌ GREŠKA: Fajl nije pronađen: {EXCEL_PATH}")
        sys.exit(1)
    
    if DELETE_EXISTING:
        print("\n⚠️  UPOZORENJE: Ovo će obrisati POSTOJEĆE historijske podatke!")
        response = input("\n   Da li si sigurno da želiš nastaviti? (DA/ne): ").strip().upper()
        if response != 'DA':
            print("   Odustao/la.")
            sys.exit(0)
        
        print("\n🗑️  Brisanje postojećih podataka...")
        delete_stats = delete_existing_historical_data()
        print(f"   ✅ Obrisano: {delete_stats['orders_deleted']} narudžbi, "
              f"{delete_stats['installments_deleted']} rata, "
              f"{delete_stats['payments_deleted']} uplata")
    
    print("\n📥 Pokrećem uvoz sa tačnim datumima...")
    import_stats = import_with_exact_dates(EXCEL_PATH)
    
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
    print("   1. Pokreni aplikaciju: python run.py")
    print("   2. Provjeri stranicu 'Rate' - datumi bi trebali biti kao u Excel-u")
    print()


if __name__ == "__main__":
    main()
