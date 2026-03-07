from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import PriceList, PriceListItem
from app.importers.excel_importer import _detect_header_row


COLUMN_MAP: dict[str, list[str]] = {
    "row_number":     ["rb", "redni br", "redni broj", "#", "no", "r.b.", "r.br."],
    "supplier_code":  ["šifra", "sifra", "šifra artikla", "sifra artikla", "code", "id",
                       "art", "artikal br", "product code", "šif"],
    "name":           ["naziv", "naziv artikla", "naziva artikla", "artikal", "proizvod",
                       "product", "name", "product name", "opis", "item"],
    "brand":          ["brend", "brand", "marka", "proizvođač"],
    "regular_price":  ["cijena", "mpc", "price", "regular price", "regular",
                       "osnovna cijena", "rrp", "km"],
    "discount_price": ["akcija", "discount", "sale", "discount price",
                       "sale price", "akcijska cijena", "promo"],
    "points":         ["bod", "bodovi", "points", "pts", "poeni"],
}


def _safe_decimal(val) -> Optional[Decimal]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return Decimal(str(val).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def _map_columns(df_columns: list[str]) -> dict[str, str]:
    """
    Mapira kolone DataFrame-a na logička polja.
    Normalizacija: lower + strip + ukloni višestruke razmake.
    Također pokušava match bez razmaka (za "N A Z I V  A R T I K L A" stil).
    """
    def norm(s: str) -> str:
        import re
        return re.sub(r"\s+", " ", s.lower().strip())

    normalized = {norm(c): c for c in df_columns}
    nospace = {norm(c).replace(" ", ""): c for c in df_columns}

    mapping: dict[str, str] = {}
    for field, aliases in COLUMN_MAP.items():
        for alias in aliases:
            n = norm(alias)
            if n in normalized:
                mapping[field] = normalized[n]
                break
            # partial match
            for nc, orig in normalized.items():
                if n in nc or nc in n:
                    mapping[field] = orig
                    break
            if field in mapping:
                break
            # no-space match (za "N A Z I V" stil)
            ns = n.replace(" ", "")
            if ns and ns in nospace:
                mapping[field] = nospace[ns]
                break
    return mapping


class PriceListService:

    @staticmethod
    def list_all() -> list[PriceList]:
        """Vraća listu svih cjenovnika, od najnovijeg."""
        with session_scope() as session:
            price_lists = list(
                session.execute(
                    select(PriceList).order_by(PriceList.created_at.desc())
                ).scalars()
            )
            for pl in price_lists:
                session.expunge(pl)
            return price_lists

    @staticmethod
    def get_items(price_list_id: int) -> list[PriceListItem]:
        """Vraća stavke cjenovnika, u originalnom redoslijedu."""
        with session_scope() as session:
            items = list(
                session.execute(
                    select(PriceListItem)
                    .where(PriceListItem.price_list_id == price_list_id)
                    .order_by(PriceListItem.row_number.asc(), PriceListItem.id.asc())
                ).scalars()
            )
            for item in items:
                session.expunge(item)
            return items

    @staticmethod
    def import_from_excel(name: str, excel_path: str) -> tuple[int, int]:
        """
        Uvozi cjenovnik iz Excel fajla.

        Koristi _detect_header_row() za automatsko pronalaženje header reda
        i mapira kolone case-insensitivno, uključujući "N A Z I V" stil.

        Vraća: (uvezeno, preskočeno)
        Raises: ValueError ako fajl ne sadrži kolonu za naziv.
                ValueError ako cjenovnik s tim imenom već postoji.
        """
        path = Path(excel_path)

        # Automatski pronađi header red (kao u excel_importer)
        header_row = _detect_header_row(path)
        df = pd.read_excel(path, header=header_row, dtype=str)
        df = df.dropna(how="all").reset_index(drop=True)

        col_mapping = _map_columns([str(c) for c in df.columns])

        if "name" not in col_mapping:
            available = list(df.columns)
            raise ValueError(
                "Excel fajl ne sadrži kolonu za naziv proizvoda.\n"
                f"Dostupne kolone: {available}"
            )

        filename = path.name
        imported = 0
        skipped = 0

        with session_scope() as session:
            # Provjeri duplikat
            existing = session.execute(
                select(PriceList).where(PriceList.name == name)
            ).scalars().first()
            if existing:
                raise ValueError(f"Cjenovnik sa nazivom '{name}' već postoji.")

            price_list = PriceList(name=name, source_filename=filename)
            session.add(price_list)
            session.flush()

            for idx, row in df.iterrows():
                raw_name = row.get(col_mapping["name"])
                if raw_name is None or str(raw_name).strip() in ("", "nan"):
                    skipped += 1
                    continue

                def get_val(field: str):
                    col = col_mapping.get(field)
                    return row.get(col) if col else None

                item = PriceListItem(
                    price_list_id=price_list.id,
                    row_number=_safe_int(get_val("row_number")) or (int(idx) + 1),
                    supplier_code=(
                        str(get_val("supplier_code")).strip()
                        if get_val("supplier_code") and str(get_val("supplier_code")).strip() not in ("", "nan")
                        else None
                    ),
                    name=str(raw_name).strip(),
                    brand=(
                        str(get_val("brand")).strip()
                        if get_val("brand") and str(get_val("brand")).strip() not in ("", "nan")
                        else None
                    ),
                    regular_price=_safe_decimal(get_val("regular_price")),
                    discount_price=_safe_decimal(get_val("discount_price")),
                    points=_safe_int(get_val("points")),
                )
                session.add(item)
                imported += 1

        return imported, skipped

    @staticmethod
    def delete(price_list_id: int) -> None:
        """Briše cjenovnik i sve stavke (cascade)."""
        with session_scope() as session:
            pl = session.get(PriceList, price_list_id)
            if pl is None:
                raise ValueError(f"Cjenovnik ID={price_list_id} ne postoji.")
            session.delete(pl)
