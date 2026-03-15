#!/usr/bin/env python3
"""
Ispravlja iznose rata za sve ugovore uvezene iz Excel-a.

Problem: Importer je izračunao rate kao price/n (jednaki dijelovi), ali Excel
bilježi stvarno uplaćen iznos po rati koji može biti drugačiji (zaokruživanje,
nejednake uplate). Razlika uzrokuje DJELIMIČNO status umjesto PLAĆENO.

Rješenje: Za svaku ratu koja ima uplatu iz importa, postavi installment.amount
= stvarno uplaćeni iznos. sync_statuses() tada ispravno postavlja status PLAĆENO.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.database import session_scope
from app.database.models import Installment, InstallmentStatus, Order, Payment
from app.services.installment_service import InstallmentService

IMPORT_NOTES = ("Uvezeno iz Excel-a", "Uvezeno iz ODS Jul/Avg 2025")


def fix_installment_amounts() -> dict:
    stats = {"updated": 0, "skipped_no_payment": 0, "skipped_manual": 0}

    with session_scope() as session:
        stmt = (
            select(Installment)
            .options(selectinload(Installment.payments))
            .where(Installment.status == InstallmentStatus.PARTIALLY_PAID)
        )
        partials = list(session.execute(stmt).scalars().all())

        print(f"DJELIMIČNO rata za provjeru: {len(partials)}")
        print()

        for inst in partials:
            if not inst.payments:
                stats["skipped_no_payment"] += 1
                continue

            # Provjeri jesu li SVE uplate iz importa
            all_imported = all(
                any(note in (p.note or "") for note in IMPORT_NOTES)
                for p in inst.payments
            )

            if not all_imported:
                # Ima ručnih uplata — ne diramo
                stats["skipped_manual"] += 1
                continue

            # Postavi iznos rate = stvarno uplaćeni iznos
            total_paid = sum(Decimal(str(p.amount)) for p in inst.payments)
            old_amount = inst.amount
            inst.amount = total_paid
            stats["updated"] += 1

            order = session.get(Order, inst.order_id)
            contract = order.contract_number if order else "?"
            print(
                f"  Ugovor {contract} Rata {inst.installment_number}: "
                f"{old_amount:.2f} → {total_paid:.2f} EUR"
            )

    return stats


def main() -> None:
    print("=" * 60)
    print("FIX: Iznosi rata iz Excel importa")
    print("=" * 60)

    stats = fix_installment_amounts()

    print()
    print("=" * 60)
    print(f"  Ažurirano rata:        {stats['updated']}")
    print(f"  Preskočeno (bez upl.): {stats['skipped_no_payment']}")
    print(f"  Preskočeno (ručne):    {stats['skipped_manual']}")
    print("=" * 60)

    print("\nSinhronizacija statusa...")
    InstallmentService.sync_statuses()
    print("Gotovo!")


if __name__ == "__main__":
    main()
