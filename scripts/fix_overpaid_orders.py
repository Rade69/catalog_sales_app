#!/usr/bin/env python3
"""
Ispravlja ugovore gdje je ukupno plaćeno > cijena ugovora.

Uzrok: Importer je za is_fully_paid ugovore kreirao prave uplate (iz Excel
kolona) + lažne uplate (fallback: installment.amount za sve ostale rate).

Algoritam:
  Za svaki preplačeni ugovor, prolazimo kroz uplate sortirane po broju rate.
  Zadržavamo uplate dok tekući zbir < cijena. Prvu uplatu koja bi prešla
  iznos smanjujemo na tačan ostatak. Sve uplate iza brišemo.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.database import session_scope
from app.database.models import Installment, Order, Payment
from app.services.installment_service import InstallmentService

TOLERANCE = Decimal("0.50")  # Smatramo problem ako višak > 50 centi


def fix_overpaid_orders() -> dict:
    stats = {"orders_fixed": 0, "payments_deleted": 0, "payments_adjusted": 0}

    with session_scope() as session:
        # Učitaj sve narudžbe sa ratama i uplatama
        orders = list(session.execute(
            select(Order).options(
                selectinload(Order.installments).selectinload(Installment.payments)
            )
        ).scalars().unique())

        for order in orders:
            total_price = Decimal(str(order.total_price_snapshot))
            if total_price <= Decimal("0"):
                continue

            # Sortiraj rate po broju rate
            sorted_insts = sorted(order.installments, key=lambda i: i.installment_number)

            # Izračunaj ukupno plaćeno
            total_paid = sum(
                sum(Decimal(str(p.amount)) for p in inst.payments)
                for inst in sorted_insts
            )

            if total_paid <= total_price + TOLERANCE:
                continue  # Nema problema

            # --- Ovaj ugovor je preplačen ---
            print(f"Ugovor {order.contract_number}: cijena={total_price:.2f}, "
                  f"plaćeno={total_paid:.2f} (višak={total_paid - total_price:.2f})")

            running = Decimal("0.00")
            order_fixed = False

            for inst in sorted_insts:
                pays = sorted(inst.payments, key=lambda p: p.id)

                for payment in pays:
                    amt = Decimal(str(payment.amount))

                    if running >= total_price:
                        # Sve što dođe poslije je lažna uplata → briši
                        print(f"  Briši: Rata {inst.installment_number}, "
                              f"uplata {amt:.2f} (running={running:.2f})")
                        session.delete(payment)
                        stats["payments_deleted"] += 1
                        order_fixed = True

                    elif running + amt > total_price + Decimal("0.01"):
                        # Ova uplata prelazi iznos → skrati je na ostatak
                        remaining = total_price - running
                        print(f"  Skrati: Rata {inst.installment_number}, "
                              f"{amt:.2f} → {remaining:.2f}")
                        payment.amount = remaining
                        running = total_price
                        stats["payments_adjusted"] += 1
                        order_fixed = True

                    else:
                        running += amt

            if order_fixed:
                stats["orders_fixed"] += 1
                print(f"  ✅ Novo ukupno: {running:.2f} / {total_price:.2f}\n")

    return stats


def main() -> None:
    print("=" * 60)
    print("FIX: Preplačeni ugovori")
    print("=" * 60)
    print()

    stats = fix_overpaid_orders()

    print("=" * 60)
    print(f"  Ispravljeno narudžbi:    {stats['orders_fixed']}")
    print(f"  Obrisano uplata:         {stats['payments_deleted']}")
    print(f"  Prilagođeno uplata:      {stats['payments_adjusted']}")
    print("=" * 60)

    print("\nSinhronizacija statusa...")
    InstallmentService.sync_statuses()
    print("✅ Gotovo!")


if __name__ == "__main__":
    main()
