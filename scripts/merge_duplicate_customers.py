#!/usr/bin/env python3
"""
Spaja duplikate kupaca koji se razlikuju samo u dijakritičkim znakovima.

Logika odabira koji zapis zadržati:
  1. Preferuj ime s dijakritičkim znacima (ispravan pravopis)
  2. Ako oba/nijedan nemaju dijakritike, zadrži onaj s više narudžbi
  3. Prebaci sve narudžbe duplikata na zadržanog kupca
  4. Obriši duplikat iz baze
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import Customer, Order


def normalize(name: str) -> str:
    """Ukloni dijakritike i whitespace za poređenje."""
    n = name.strip()
    n = unicodedata.normalize("NFD", n)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", n).lower()


def has_diacritics(name: str) -> bool:
    """Vraća True ako ime sadrži dijakritičke znake (č, ć, š, ž, đ...)."""
    normalized = unicodedata.normalize("NFD", name)
    return any(unicodedata.category(c) == "Mn" for c in normalized)


def pick_keeper(group: list[Customer], order_counts: dict[int, int]) -> Customer:
    """Odaberi koji zapis kupca zadržati."""
    # Sortiraj: (1) ima dijakritike, (2) više narudžbi, (3) veći ID (noviji)
    return sorted(
        group,
        key=lambda c: (
            has_diacritics(c.full_name),    # True > False
            order_counts.get(c.id, 0),      # više narudžbi bolje
        ),
        reverse=True,
    )[0]


def merge_duplicates(dry_run: bool = False) -> dict:
    stats = {"merged_groups": 0, "orders_moved": 0, "customers_deleted": 0}

    with session_scope() as session:
        customers = list(session.execute(select(Customer)).scalars().all())
        orders = list(session.execute(select(Order)).scalars().all())

        order_counts: dict[int, int] = {}
        for o in orders:
            order_counts[o.customer_id] = order_counts.get(o.customer_id, 0) + 1

        # Grupiši po normalizovanom imenu
        groups: dict[str, list[Customer]] = {}
        for c in customers:
            key = normalize(c.full_name)
            groups.setdefault(key, []).append(c)

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Pronađeno {len(dupes)} grupe duplikata\n")

        for group in dupes.values():
            keeper = pick_keeper(group, order_counts)
            to_delete = [c for c in group if c.id != keeper.id]

            total_before = sum(order_counts.get(c.id, 0) for c in group)
            print(f"  ✅ ZADRŽI  ID={keeper.id:3d}  \"{keeper.full_name}\"  ({order_counts.get(keeper.id,0)} narudžbi)")
            for dup in to_delete:
                n = order_counts.get(dup.id, 0)
                print(f"  🗑️  OBRIŠI  ID={dup.id:3d}  \"{dup.full_name}\"  ({n} narudžbi) → prebaci na ID={keeper.id}")

            if not dry_run:
                for dup in to_delete:
                    # Prebaci sve narudžbe
                    dup_orders = session.execute(
                        select(Order).where(Order.customer_id == dup.id)
                    ).scalars().all()
                    for o in dup_orders:
                        o.customer_id = keeper.id
                        stats["orders_moved"] += 1

                    session.flush()
                    session.delete(dup)
                    stats["customers_deleted"] += 1

            stats["merged_groups"] += 1
            print(f"  → Ukupno narudžbi poslije: {total_before}\n")

    return stats


def main() -> None:
    print("=" * 60)
    print("SPAJANJE DUPLIKATA KUPACA")
    print("=" * 60)
    print()

    stats = merge_duplicates(dry_run=False)

    print("=" * 60)
    print(f"  Spojeno grupa:        {stats['merged_groups']}")
    print(f"  Prebačeno narudžbi:   {stats['orders_moved']}")
    print(f"  Obrisano duplikata:   {stats['customers_deleted']}")
    print("=" * 60)
    print("\n✅ Gotovo!")


if __name__ == "__main__":
    main()
