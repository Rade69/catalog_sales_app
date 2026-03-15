#!/usr/bin/env python3
"""
Uvoz Jul i Avgust 2025 blokova iz:
  SANJA STOJANOVIC-2-jul-avgust (1).ods  (Sheet1)

Razlike od standardnog importera:
- ODS format (engine='odf')
- Kolona 7 je uvijek prazna u data redovima; rate su na kolonama 8-18
- Datumi rata se računaju iz naziva bloka (Jul/Avg 2025)
- Br. rata maks 10, ali iskorištene kolone 8-17
"""

from __future__ import annotations

import calendar
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from sqlalchemy import select

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


ODS_PATH = "/home/radovan/Pictures/sanja/SANJA STOJANOVIC-2-jul-avgust (1).ods"
CAMPAIGN_NAME = "Historijat 2025-2026"

BS_MONTHS = {
    "jan": 1, "januar": 1,
    "feb": 2, "februar": 2,
    "mar": 3, "mart": 3,
    "apr": 4, "april": 4,
    "maj": 5,
    "jun": 6,
    "jul": 7,
    "avg": 8, "avgust": 8, "august": 8,
    "sep": 9, "septembar": 9,
    "okt": 10, "oktobar": 10, "0kt": 10,
    "nov": 11, "novembar": 11,
    "dec": 12, "decembar": 12,
}


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
    except Exception:
        return None


def _safe_int(val, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(str(val).strip()))))
    except Exception:
        return default


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    """Dodaj n mjeseci na (year, month), vrati novi (year, month)."""
    total = month - 1 + n
    return year + total // 12, (total % 12) + 1


def _parse_month_from_str(s: str) -> int | None:
    """Iz stringa poput 'jul', 'AVGUST', '31.avg.', '0OTOBAR' izvuci broj mjeseca."""
    s = str(s).strip().lower()
    # Ukloni cifre i tačke na početku (npr. "31.avg." → "avg")
    s = re.sub(r'^\d+\.?\s*', '', s)
    s = s.rstrip('.').strip()
    # Fix ODS tipfelera: "0otobar" → "oktobar"
    s = s.replace("0ot", "okt")
    for key, num in BS_MONTHS.items():
        if key in s or s in key:
            return num
    return None


def _due_dates_for_block(block_month: int, block_year: int, count: int = 10) -> list[date]:
    """
    Izračunaj datume dospijeća počevši od (block_month, block_year).
    Svaka rata = posljednji dan svakog narednog mjeseca.
    """
    dates = []
    for i in range(count):
        y, m = _add_months(block_year, block_month, i)
        d = _last_day(y, m)
        dates.append(date(y, m, d))
    return dates


def _find_block_starts(df: pd.DataFrame) -> list[int]:
    starts = []
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            starts.append(int(i))
    return starts


def _parse_block_month_year(df: pd.DataFrame, block_start: int) -> tuple[int, int]:
    """Izvuci (month, year) iz saradnik reda (block_start + 1)."""
    row = df.iloc[block_start + 1]
    month_val = str(row.iloc[16]).strip() if len(row) > 16 else ""
    year_val = str(row.iloc[19]).strip() if len(row) > 19 else ""
    m = _parse_month_from_str(month_val)
    year_match = re.search(r'(\d{4})', year_val)
    y = int(year_match.group(1)) if year_match else 2025
    return (m or 7, y)


def _parse_orders_in_block(
    df: pd.DataFrame,
    block_start: int,
    block_end: int,
    due_dates: list[date],
    month_num: int,
    year_num: int,
) -> list[dict]:
    """
    Parsiraj ugovore u bloku.

    ODS specifičnost:
      - Kolona 7 je prazna (Timestamp referenca) — preskačemo je
      - Stvarne rate su na kolonama 8..17 (rata 1..10)
      - Ukupno = kolona 19, Preostalo = kolona 20
    """
    orders = []
    data_start = block_start + 5  # 2 header reda + 2 date reda + 1 razmak
    seen_contracts: set[str] = set()

    for ri in range(data_start, block_end):
        row = df.iloc[ri]

        def get(col: int) -> str:
            try:
                v = str(row.iloc[col]).strip()
                return "" if v in ("nan", "NaN") or v == "nan" else v
            except Exception:
                return ""

        rb = get(1)
        br_ugovora = get(2)
        ime = get(3)
        sifra = get(4)
        vrijed = get(5)
        br_rata = get(6)
        ukupno = get(19)
        preostalo = get(20)

        if not rb or not br_ugovora or not ime:
            continue
        if "UKUPNO" in rb.upper() or "R." in rb:
            continue
        try:
            int(float(rb))
        except Exception:
            continue

        # br_ugovora može biti float (614804.0) → normalizuj
        try:
            br_ugovora = str(int(float(br_ugovora)))
        except Exception:
            pass

        if br_ugovora in seen_contracts:
            continue
        seen_contracts.add(br_ugovora)

        vrijed_dec = _safe_decimal(vrijed)
        ukupno_dec = _safe_decimal(ukupno)
        preostalo_dec = _safe_decimal(preostalo)

        is_fully_paid = False
        if vrijed_dec and ukupno_dec:
            if ukupno_dec >= vrijed_dec - Decimal("0.20"):
                is_fully_paid = True
            elif preostalo_dec is not None and preostalo_dec <= Decimal("0.01"):
                is_fully_paid = True

        # Rate su na kolonama 8-17 (rata 1-10)
        payments_by_installment: dict[int, Decimal] = {}
        for col in range(8, 18):
            payment_val = get(col)
            if payment_val:
                amt = _safe_decimal(payment_val)
                if amt and amt > 0:
                    installment_num = col - 7  # col 8 → rata 1
                    payments_by_installment[installment_num] = amt

        first_due_date = due_dates[0] if due_dates else date(year_num, month_num, 1)

        orders.append({
            "br_ugovora": br_ugovora,
            "ime": _normalize_name(ime),
            "sifra": sifra,
            "vrijed_eur": vrijed_dec,
            "ukupno_eur": ukupno_dec,
            "preostalo_eur": preostalo_dec,
            "is_fully_paid": is_fully_paid,
            "payments_by_installment": payments_by_installment,
            "br_rata": _safe_int(br_rata),
            "first_due_date": first_due_date,
            "due_dates": due_dates,
            "month": month_num,
            "year": year_num,
        })

    return orders


def import_jul_avgust() -> dict:
    path = Path(ODS_PATH)
    if not path.exists():
        raise FileNotFoundError(f"ODS fajl nije pronađen: {path}")

    print(f"\n📂 Uvoz: {path.name}")
    print("=" * 70)

    df = pd.read_excel(str(path), sheet_name="Sheet1", engine="odf", header=None)
    print(f"Ukupno redova: {len(df)}")

    block_starts = _find_block_starts(df)
    print(f"Pronađeno blokova: {len(block_starts)}")

    stats = {
        "customers_created": 0,
        "customers_existing": 0,
        "orders_created": 0,
        "orders_skipped": 0,
        "installments_created": 0,
        "payments_created": 0,
    }

    with session_scope() as session:
        # Nađi ili kreiraj kampanju
        campaign = session.execute(
            select(Campaign).where(Campaign.name == CAMPAIGN_NAME)
        ).scalars().first()

        if campaign is None:
            campaign = Campaign(
                name=CAMPAIGN_NAME,
                status=CampaignStatus.ARCHIVED,
                start_date=date(2025, 7, 1),
                end_date=date(2026, 2, 28),
            )
            session.add(campaign)
            session.flush()

        campaign_id = campaign.id

        # Učitaj postojeće kupce i ugovore
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

            print(f"\n{'=' * 70}")
            month_num, year_num = _parse_block_month_year(df, block_start)
            due_dates = _due_dates_for_block(month_num, year_num, count=10)

            print(f"BLOK {idx + 1}: {month_num}/{year_num}  (redovi {block_start}-{block_end-1})")
            print(f"Datumi rata: {due_dates[0]} ... {due_dates[-1]}")

            orders_data = _parse_orders_in_block(
                df, block_start, block_end, due_dates, month_num, year_num
            )
            print(f"Ugovora u bloku: {len(orders_data)}")

            for order_data in orders_data:
                name = order_data["ime"]
                name_key = name.lower()

                if name_key not in existing_customers:
                    customer = Customer(full_name=name, is_active=True)
                    session.add(customer)
                    session.flush()
                    existing_customers[name_key] = customer.id
                    stats["customers_created"] += 1
                else:
                    stats["customers_existing"] += 1

                customer_id = existing_customers[name_key]

                if order_data["br_ugovora"] in existing_contracts:
                    print(f"  ⏭️  Preskočeno (duplikat): {order_data['br_ugovora']}")
                    stats["orders_skipped"] += 1
                    continue

                price = order_data["vrijed_eur"] or Decimal("0.00")
                status = OrderStatus.COMPLETED if order_data["is_fully_paid"] else OrderStatus.ACTIVE
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
                    note=(
                        f"Uvezeno iz {path.stem} ({order_data['month']}/{order_data['year']}). "
                        f"Ukupno: {order_data['ukupno_eur']} EUR, "
                        f"Preostalo: {order_data['preostalo_eur']} EUR"
                    ),
                )
                session.add(order)
                session.flush()
                existing_contracts.add(order_data["br_ugovora"])

                # Kreiraj rate
                installments = []
                allocated = Decimal("0.00")
                br_rata = order_data["br_rata"]
                base_amount = (price / br_rata).quantize(Decimal("0.01")) if br_rata else price

                for i in range(br_rata):
                    amount = base_amount
                    if i == br_rata - 1:
                        amount = price - allocated
                    allocated += amount

                    due_date = order_data["due_dates"][i] if i < len(order_data["due_dates"]) else first_due_date

                    if order_data["is_fully_paid"]:
                        inst_status = InstallmentStatus.PAID
                    elif (i + 1) in order_data["payments_by_installment"]:
                        inst_status = InstallmentStatus.PAID
                    else:
                        inst_status = InstallmentStatus.PENDING

                    installment = Installment(
                        order=order,
                        installment_number=i + 1,
                        due_date=due_date,
                        amount=amount,
                        status=inst_status,
                    )
                    installments.append(installment)
                    session.add(installment)

                session.flush()

                # Kreiraj uplate SAMO za rate s eksplicitnom vrijednosti iz Excel kolona
                pbi = order_data["payments_by_installment"]
                for i, installment in enumerate(installments):
                    rata_num = i + 1
                    if rata_num in pbi:
                        payment = Payment(
                            installment_id=installment.id,
                            payment_date=installment.due_date,
                            amount=pbi[rata_num],
                            note="Uvezeno iz ODS Jul/Avg 2025",
                        )
                        session.add(payment)
                        stats["payments_created"] += 1

                stats["orders_created"] += 1
                stats["installments_created"] += len(installments)

                paid_info = "ISPLAĆENO" if order_data["is_fully_paid"] else f"aktivan ({len(pbi)}/{br_rata} rata)"
                print(
                    f"  ✅ {order_data['br_ugovora']}: {name}, "
                    f"{price:.2f} EUR, {br_rata} rata — {paid_info}"
                )

    return stats


def main() -> None:
    print("\n" + "=" * 70)
    print("📦 UVOZ JUL I AVGUST 2025")
    print("   SANJA STOJANOVIC-2-jul-avgust (1).ods")
    print("=" * 70)

    stats = import_jul_avgust()

    print("\n" + "=" * 70)
    print("📊 SAŽETAK")
    print("=" * 70)
    print(f"  ✅ Kreirano kupaca:    {stats['customers_created']}")
    print(f"  ℹ️  Već postoji:        {stats['customers_existing']}")
    print(f"  ✅ Kreirano narudžbi:  {stats['orders_created']}")
    print(f"  ⏭️  Preskočeno:         {stats['orders_skipped']}")
    print(f"  ✅ Kreirano rata:      {stats['installments_created']}")
    print(f"  ✅ Kreirano uplata:    {stats['payments_created']}")
    print("=" * 70)

    print("\n🔄 Sinhronizacija statusa...")
    InstallmentService.sync_statuses()
    print("✅ Gotovo! Pokreni: python run.py")


if __name__ == "__main__":
    main()
