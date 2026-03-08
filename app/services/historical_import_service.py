"""
HistoricalImportService — uvoz historijskih kupaca i narudžbi iz Excel evidencije.

Parsira strukturu:
  Blokovi po mjesecima, svaki sa kolonama:
    col1=Rb, col2=Br.ugovora, col3=Ime i prezime, col4=Šifra proizvoda,
    col5=Vrijednost EUR, col6=Br.rata, col19=Ukupno uplaćeno, col20=Preostalo
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

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


# Naziv kampanje koja se kreira/koristi za historijske narudžbe
HISTORICAL_CAMPAIGN_NAME = "Historijat 2025-2026"

# Konverzija EUR → BAM (fiksni kurs)
EUR_TO_BAM = Decimal("1.95583")

# Kolone u Excel-u (0-indeksovano)
COL_RB = 1
COL_UGOVOR = 2
COL_IME = 3
COL_SIFRA = 4
COL_VRIJED = 5
COL_RATA = 6
COL_UKUPNO = 19
COL_PREOSTALO = 20


@dataclass
class ImportResult:
    customers_created: int = 0
    customers_existing: int = 0
    orders_created: int = 0
    orders_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _normalize_name(name: str) -> str:
    """Normalizuje ime: strip, title-case, zamijeni višestruke razmake, ukloni dijakritike."""
    # Zamijeni ćirilična slova koja izgledaju latinično
    name = name.strip()
    # Normalizuj unicode (NFC)
    name = unicodedata.normalize("NFC", name)
    # Ukloni višestruke razmake
    name = re.sub(r"\s+", " ", name)
    return name


def _safe_decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "nan"):
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def _safe_int(val, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(str(val).strip()))))
    except (ValueError, TypeError):
        return default


def _parse_excel_blocks(path: Path) -> list[dict]:
    """
    Čita Excel fajl i parsira sve blokove.
    Vraća listu dict-ova sa podacima o ugovorima (deduplicirani po br. ugovora).
    """
    df = pd.read_excel(str(path), sheet_name=0, header=None, dtype=str)

    # Nađi početke blokova (redovi sa "EVIDENCIJA")
    block_starts = []
    for i, row in df.iterrows():
        row_str = " ".join(str(v) for v in row.values if str(v) != "nan")
        if "EVIDENCIJA" in row_str:
            block_starts.append(i)

    orders: dict[str, dict] = {}  # br_ugovora → data

    for bi, start in enumerate(block_starts):
        end = block_starts[bi + 1] if bi + 1 < len(block_starts) else len(df)

        # Podatkovni redovi počinju 5 redova iza EVIDENCIJA markera
        data_start = start + 5

        for ri in range(data_start, end):
            row = df.iloc[ri]

            def get(col: int) -> str:
                try:
                    v = str(row.iloc[col]).strip()
                    return "" if v == "nan" else v
                except (IndexError, KeyError):
                    return ""

            rb = get(COL_RB)
            br_ugovora = get(COL_UGOVOR)
            ime = get(COL_IME)
            sifra = get(COL_SIFRA)
            vrijed = get(COL_VRIJED)
            br_rata = get(COL_RATA)
            preostalo = get(COL_PREOSTALO)

            # Preskoci prazne redove, sumarne i header redove
            if not rb or not br_ugovora or not ime:
                continue
            if "UKUPNO" in rb.upper() or "R." in rb:
                continue
            try:
                int(float(rb))
            except (ValueError, TypeError):
                continue

            # Ako smo već vidjeli ovaj ugovor, preskočimo (uzmemo samo prvu pojavu)
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


class HistoricalImportService:
    """Uvozi historijske kupce i narudžbe iz Excel evidencije rata."""

    @staticmethod
    def preview(excel_path: str) -> dict:
        """
        Analizira fajl i vraća pregled bez uvoza.
        Vraća: {'orders': int, 'customers': int, 'blocks': list[str]}
        """
        path = Path(excel_path)
        parsed = _parse_excel_blocks(path)
        unique_customers = sorted(set(o["ime"] for o in parsed))
        return {
            "orders": len(parsed),
            "customers": len(unique_customers),
            "customer_list": unique_customers,
        }

    @staticmethod
    def import_from_excel(excel_path: str) -> ImportResult:
        """
        Uvozi sve kupce i narudžbe iz Excel fajla evidencije.

        - Kupci se dedupliraju po imenu (case-insensitive).
        - Svaki ugovor se uvozi jednom (duplikati su isti ugovor u više mjeseci).
        - Cijena se čuva u BAM (konverzija EUR * 1.95583).
        - Narudžbe s Preostalo=0 dobijaju status COMPLETED.
        - Koristi se posebna kampanja "Historijat 2025-2026".
        - Installmenti se NE generišu automatski (historijski podaci).
        """
        result = ImportResult()
        path = Path(excel_path)
        parsed = _parse_excel_blocks(path)

        if not parsed:
            result.errors.append("Nije pronađen nijedan ugovor u fajlu.")
            return result

        with session_scope() as session:
            # --- Kampanja ---
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

            # --- Mapa kupaca: normalized_name → customer_id ---
            existing_customers: dict[str, int] = {}
            for cust in session.execute(select(Customer)).scalars():
                key = _normalize_name(cust.full_name).lower()
                existing_customers[key] = cust.id

            # --- Uvoz ---
            for order_data in parsed:
                name = order_data["ime"]
                name_key = name.lower()

                # Kreiraj kupca ako ne postoji
                if name_key not in existing_customers:
                    customer = Customer(full_name=name, is_active=True)
                    session.add(customer)
                    session.flush()
                    existing_customers[name_key] = customer.id
                    result.customers_created += 1
                else:
                    result.customers_existing += 1

                customer_id = existing_customers[name_key]

                # Provjeri da li ugovor već postoji
                existing_order = session.execute(
                    select(Order).where(Order.contract_number == order_data["br_ugovora"])
                ).scalars().first()

                if existing_order is not None:
                    result.orders_skipped += 1
                    continue

                price = order_data["vrijed_bam"] or Decimal("0.00")
                status = OrderStatus.COMPLETED if order_data["completed"] else OrderStatus.ACTIVE

                # Procijeni datum prve rate na osnovu broja ugovora
                # (Sep 2025 = 672xxx, Okt = 672xxx, ..., Feb 2026 = 735969+)
                order_date = _estimate_order_date(order_data["br_ugovora"])

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
                    first_due_date=order_date,
                    note=f"Uvezeno iz historijata. Originalna vrijednost: {order_data['vrijed_eur']} EUR",
                )
                session.add(order)
                result.orders_created += 1

        return result

    @staticmethod
    def generate_installments(excel_path: str) -> tuple[int, int]:
        """
        Generira Installment i Payment zapise za sve historijske narudžbe
        koje još nemaju rate.

        - COMPLETED narudžba → sve rate PAID (dodaje se uplata = iznos rate)
        - ACTIVE narudžba    → rate PENDING/OVERDUE, dodaje se jedna uplata
                               za iznos koji je već plaćen (total - preostalo)

        Vraća: (orders_processed, installments_created)
        """
        path = Path(excel_path)
        preostalo_map: dict[str, Decimal] = {}
        for order_data in _parse_excel_blocks(path):
            # preostalo iz Excela je u EUR → konvertuj u BAM
            pre_eur = order_data["preostalo"]
            if pre_eur is not None:
                preostalo_map[order_data["br_ugovora"]] = (
                    pre_eur * EUR_TO_BAM
                ).quantize(Decimal("0.01"))

        orders_processed = 0
        installments_created = 0

        with session_scope() as session:
            # Sve historijske narudžbe
            all_orders = list(
                session.execute(
                    select(Order).where(Order.contract_number.is_not(None))
                ).scalars().all()
            )

            for order in all_orders:
                # Preskoči ako već ima rata
                existing = session.execute(
                    select(Installment).where(Installment.order_id == order.id)
                ).scalars().first()
                if existing is not None:
                    continue

                # Generiši rate
                installments = InstallmentService.generate_for_order(order)
                for inst in installments:
                    session.add(inst)
                session.flush()

                installments_created += len(installments)
                orders_processed += 1
                total_bam = Decimal(str(order.total_price_snapshot))

                if order.status == OrderStatus.COMPLETED:
                    # Sve rate su plaćene — dodaj uplatu za svaku ratu
                    for inst in installments:
                        inst.status = InstallmentStatus.PAID
                        payment = Payment(
                            installment_id=inst.id,
                            amount=Decimal(str(inst.amount)),
                            payment_date=order.order_date,
                            note="Automatski generisano — historijski uvoz",
                        )
                        session.add(payment)
                else:
                    # ACTIVE — odredi koliko je CIJELIH rata plaćeno
                    # Koristimo preostalo_eur direktno da izbjegnemo EUR→BAM zaokrugljivanje
                    preostalo_bam = preostalo_map.get(order.contract_number)
                    if preostalo_bam is not None and total_bam > Decimal("0.00"):
                        paid_bam = (total_bam - preostalo_bam).quantize(Decimal("0.01"))
                    else:
                        paid_bam = Decimal("0.00")

                    today = date.today()
                    sorted_insts = sorted(installments, key=lambda x: x.installment_number)

                    if paid_bam > Decimal("0.01") and sorted_insts:
                        # Koliko je cijelih rata pokriveno plaćenim iznosom
                        inst_amount = Decimal(str(sorted_insts[0].amount))
                        # Zaokruži na najbliži cijeli broj rata — uklanja EUR/BAM artefakte
                        num_paid = int((paid_bam / inst_amount).quantize(
                            Decimal("1"), rounding="ROUND_HALF_UP"
                        ))
                        num_paid = min(num_paid, len(sorted_insts))

                        for inst in sorted_insts[:num_paid]:
                            inst.status = InstallmentStatus.PAID
                            payment = Payment(
                                installment_id=inst.id,
                                amount=Decimal(str(inst.amount)),
                                payment_date=order.order_date,
                                note="Automatski generisano — historijski uvoz",
                            )
                            session.add(payment)

                    # Neplaćene rate: OVERDUE ako je datum prošao, inače PENDING
                    for inst in installments:
                        if inst.status == InstallmentStatus.PENDING:
                            inst.status = (
                                InstallmentStatus.OVERDUE
                                if inst.due_date < today
                                else InstallmentStatus.PENDING
                            )

        return orders_processed, installments_created


def _estimate_order_date(br_ugovora: str) -> date:
    """
    Procijeni datum narudžbe na osnovu broja ugovora.
    Raspored iz fajla:
      672866-672888  → Septembar/Oktobar 2025
      735882-735901  → Oktobar/Novembar 2025
      735902-735948  → Decembar 2025
      735949-735968  → Januar 2026
      682163-682175  → Februar 2026 (stari ugovori, novi period)
      735969+        → Februar 2026
    """
    try:
        n = int(br_ugovora)
    except (ValueError, TypeError):
        return date(2025, 9, 1)

    if n < 672900:
        return date(2025, 9, 1)
    elif n < 735882:
        return date(2025, 10, 1)
    elif n < 735902:
        return date(2025, 11, 1)
    elif n < 735949:
        return date(2025, 12, 1)
    elif n < 735969:
        return date(2026, 1, 1)
    else:
        return date(2026, 2, 1)
