from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import PriceList, PriceListItem
from app.dto import PriceListItemDTO, _to_price_list_item_dto
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
    "status":         ["status", "stanje", "dostupnost", "aktuelnost"],
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
        # Ova metoda se koristi samo za dohvat osnovnih podataka o cjenovnicima
        # Nema potrebe za DTO jer se koristi interno
        with session_scope() as session:
            return list(
                session.execute(
                    select(PriceList).order_by(PriceList.created_at.desc())
                ).scalars()
            )

    @staticmethod
    def get_items(price_list_id: int, limit: int = 0, offset: int = 0) -> tuple[list[PriceListItemDTO], int]:
        """
        Vraća stavke cjenovnika kao PriceListItemDTO sa paginacijom.
        
        Args:
            price_list_id: ID cjenovnika
            limit: Broj stavki za vraćanje (0 = sve)
            offset: Pomak za paginaciju
            
        Returns:
            Tuple od (lista stavki, ukupan broj stavki)
        """
        with session_scope() as session:
            # Prvo izračunaj ukupan broj stavki
            total_count_result = session.execute(
                select(PriceListItem)
                .where(PriceListItem.price_list_id == price_list_id)
            )
            total_count = len(list(total_count_result.scalars()))
            
            # Zatim dohvati stavke sa paginacijom
            stmt = (
                select(PriceListItem)
                .where(PriceListItem.price_list_id == price_list_id)
                .order_by(PriceListItem.row_number.asc(), PriceListItem.id.asc())
            )
            
            if limit > 0:
                stmt = stmt.limit(limit).offset(offset)
            
            items = list(session.execute(stmt).scalars())
            return [_to_price_list_item_dto(item) for item in items], total_count

    @staticmethod
    def import_from_excel(name: str, excel_path: str) -> tuple[int, int]:
        """
        Uvozi cjenovnik iz Excel fajla.

        Koristi _detect_header_row() za automatsko pronalaženje header reda
        i mapira kolone case-insensitivno, uključujući "N A Z I V" stil.

        Prepoznaje redove sa nazivom firme/dobavljača i povezuje ih sa proizvodima ispod.

        Vraća: (uvezeno, preskočeno)
        Raises: ValueError ako fajl ne sadrži kolonu za naziv.
                ValueError ako cjenovnik s tim imenom već postoji.
        """
        path = Path(excel_path)
        
        # Validacija fajla
        if not path.exists():
            raise ValueError(f"Fajl '{excel_path}' ne postoji.")
        
        # Validacija ekstenzije
        valid_extensions = {'.xlsx', '.xls'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Fajl mora biti Excel fajl (.xlsx ili .xls). Primljen: {path.suffix}")
        
        # Validacija veličine fajla (max 10MB)
        max_size_mb = 10
        max_size_bytes = max_size_mb * 1024 * 1024
        file_size = path.stat().st_size
        if file_size > max_size_bytes:
            raise ValueError(f"Fajl je prevelik. Maksimalna veličina je {max_size_mb}MB. Trenutna veličina: {file_size / (1024*1024):.2f}MB")
        
        # Validacija naziva cjenovnika
        name = name.strip()
        if not name:
            raise ValueError("Naziv cjenovnika ne smije biti prazan.")
        if len(name) > 100:
            raise ValueError("Naziv cjenovnika ne smije biti duži od 100 karaktera.")

        # Automatski pronađi header red (kao u excel_importer)
        header_row = _detect_header_row(path)
        df = pd.read_excel(path, header=header_row, dtype=str)
        df = df.dropna(how="all").reset_index(drop=True)
        
        # Validacija strukture fajla
        if df.empty:
            raise ValueError("Excel fajl je prazan ili ne sadrži podatke.")
        
        # Validacija minimalnog broja kolona
        if len(df.columns) < 2:
            raise ValueError(f"Excel fajl mora imati najmanje 2 kolone. Pronađeno: {len(df.columns)}")

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

        # Trenutni dobavljač/firma - ažurira se kad se naiđe na red sa nazivom firme
        current_supplier: Optional[str] = None
        
        # Set za praćenje duplikata proizvoda unutar istog importa
        imported_product_names = set()

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

                name_str = str(raw_name).strip()

                def get_val(field: str):
                    col = col_mapping.get(field)
                    return row.get(col) if col else None

                # Provjeri da li je ovo red sa nazivom firme
                # Firma red ima: naziv, ali NEMA šifru artikla i NEMA pravu cijenu
                supplier_code_val = get_val("supplier_code")
                regular_price_val = get_val("regular_price")
                brand_val = get_val("brand")
                points_val = get_val("points")

                # Helper funkcija da provjeri da li je vrijednost "prazna" ili header
                def is_empty_or_header(val) -> bool:
                    if val is None:
                        return True
                    s = str(val).strip().lower()
                    # Prazno, nan, ili header oznake poput "km", "bod", "status"
                    if s in ("", "nan", "km", "bod", "bod.", "status", "cijena", "price"):
                        return True
                    return False

                # Red je naziv firme ako:
                # 1. Ima naziv
                # 2. NEMA šifru artikla (ili je NaN/header)
                # 3. NEMA cijenu (ili je NaN/header poput "EUR")
                # 4. NEMA brand (ili je NaN)
                is_supplier_row = (
                    name_str
                    and is_empty_or_header(supplier_code_val)
                    and is_empty_or_header(regular_price_val)
                    and (brand_val is None or str(brand_val).strip() in ("", "nan"))
                )

                if is_supplier_row:
                    # Ovo je naziv firme/dobavljača
                    current_supplier = name_str
                    skipped += 1  # Ne ubrajamo kao proizvod
                    continue

                # Ovo je običan proizvod - dodijeli trenutnu firmu
                def _safe_str(val) -> Optional[str]:
                    if val is None:
                        return None
                    s = str(val).strip()
                    return s if s and s.lower() != "nan" else None
                
                # Validacija duplikata proizvoda unutar istog importa
                if name_str in imported_product_names:
                    skipped += 1
                    continue  # Preskoči duplikat
                
                imported_product_names.add(name_str)
                
                # Validacija cijena
                regular_price = _safe_decimal(get_val("regular_price"))
                discount_price = _safe_decimal(get_val("discount_price"))
                
                if regular_price is not None:
                    if regular_price <= Decimal('0'):
                        raise ValueError(f"Red {idx+1}: Redovna cijena mora biti veća od 0. Vrijednost: {regular_price}")
                    if regular_price > Decimal('100000'):
                        raise ValueError(f"Red {idx+1}: Redovna cijena ne smije biti veća od 100.000. Vrijednost: {regular_price}")
                
                if discount_price is not None:
                    if discount_price <= Decimal('0'):
                        raise ValueError(f"Red {idx+1}: Akcijska cijena mora biti veća od 0. Vrijednost: {discount_price}")
                    if discount_price > Decimal('100000'):
                        raise ValueError(f"Red {idx+1}: Akcijska cijena ne smije biti veća od 100.000. Vrijednost: {discount_price}")
                
                # Validacija da akcijska cijena nije veća od redovne
                if regular_price is not None and discount_price is not None:
                    if discount_price > regular_price:
                        raise ValueError(f"Red {idx+1}: Akcijska cijena ({discount_price}) ne smije biti veća od redovne cijene ({regular_price})")

                item = PriceListItem(
                    price_list_id=price_list.id,
                    row_number=int(idx),  # apsolutna pozicija u Excel-u — čuva originalni redoslijed
                    supplier_code=_safe_str(get_val("supplier_code")),
                    name=name_str,
                    brand=_safe_str(get_val("brand")),
                    supplier=current_supplier,
                    regular_price=regular_price,
                    discount_price=discount_price,
                    points=_safe_int(get_val("points")),
                    status=_safe_str(get_val("status")),
                )
                session.add(item)
                imported += 1

        return imported, skipped

    @staticmethod
    def update_price_list(price_list_id: int, name: str) -> None:
        """Ažurira naziv cjenovnika."""
        if not name or not name.strip():
            raise ValueError("Naziv cjenovnika je obavezan.")
        
        name = name.strip()
        if len(name) > 200:
            raise ValueError("Naziv cjenovnika ne smije biti duži od 200 karaktera.")
        
        with session_scope() as session:
            pl = session.get(PriceList, price_list_id)
            if pl is None:
                raise ValueError(f"Cjenovnik ID={price_list_id} ne postoji.")
            
            # Provjeri da li novi naziv već postoji (osim za ovaj cjenovnik)
            existing = session.execute(
                select(PriceList)
                .where(PriceList.name == name)
                .where(PriceList.id != price_list_id)
            ).scalars().first()
            if existing:
                raise ValueError(f"Cjenovnik sa nazivom '{name}' već postoji.")
            
            pl.name = name

    @staticmethod
    def duplicate_price_list(price_list_id: int, new_name: str) -> int:
        """Duplicira cjenovnik sa svim stavkama."""
        if not new_name or not new_name.strip():
            raise ValueError("Naziv novog cjenovnika je obavezan.")
        
        new_name = new_name.strip()
        if len(new_name) > 200:
            raise ValueError("Naziv cjenovnika ne smije biti duži od 200 karaktera.")
        
        with session_scope() as session:
            # Provjeri da li novi naziv već postoji
            existing = session.execute(
                select(PriceList).where(PriceList.name == new_name)
            ).scalars().first()
            if existing:
                raise ValueError(f"Cjenovnik sa nazivom '{new_name}' već postoji.")
            
            # Dohvati originalni cjenovnik sa stavkama
            original = session.get(PriceList, price_list_id)
            if original is None:
                raise ValueError(f"Cjenovnik ID={price_list_id} ne postoji.")
            
            # Kreiraj novi cjenovnik
            new_price_list = PriceList(
                name=new_name,
                source_filename=f"Copy of {original.source_filename}" if original.source_filename else None
            )
            session.add(new_price_list)
            session.flush()
            
            # Dupliciraj sve stavke
            items = session.execute(
                select(PriceListItem)
                .where(PriceListItem.price_list_id == price_list_id)
                .order_by(PriceListItem.row_number)
            ).scalars().all()
            
            for item in items:
                new_item = PriceListItem(
                    price_list_id=new_price_list.id,
                    row_number=item.row_number,
                    supplier_code=item.supplier_code,
                    name=item.name,
                    brand=item.brand,
                    supplier=item.supplier,
                    regular_price=item.regular_price,
                    discount_price=item.discount_price,
                    points=item.points,
                    status=item.status
                )
                session.add(new_item)
            
            session.flush()
            return new_price_list.id

    @staticmethod
    def delete(price_list_id: int) -> None:
        """Briše cjenovnik i sve stavke (cascade)."""
        with session_scope() as session:
            pl = session.get(PriceList, price_list_id)
            if pl is None:
                raise ValueError(f"Cjenovnik ID={price_list_id} ne postoji.")
            session.delete(pl)

    @staticmethod
    def export_price_list(price_list_id: int, output_path: str | Path) -> Path:
        """Izvozi cjenovnik u Excel fajl."""
        from app.reports.excel_reports import ExcelReports
        
        with session_scope() as session:
            pl = session.get(PriceList, price_list_id)
            if pl is None:
                raise ValueError(f"Cjenovnik ID={price_list_id} ne postoji.")
            
            # Dohvati sve stavke cenovnika
            items = session.execute(
                select(PriceListItem)
                .where(PriceListItem.price_list_id == price_list_id)
                .order_by(PriceListItem.row_number)
            ).scalars().all()
            
            # Pripremi podatke za DataFrame
            rows = []
            for i, item in enumerate(items):
                rows.append({
                    "Rb.": i + 1,
                    "Firma": item.supplier or "",
                    "Naziv artikla": item.name,
                    "Šifra": item.supplier_code or "",
                    "Brend": item.brand or "",
                    "Cijena (EUR)": float(item.regular_price) if item.regular_price else "",
                    "Akcijska cijena (EUR)": float(item.discount_price) if item.discount_price else "",
                    "Bod": item.points if item.points is not None else "",
                    "Status": item.status or ""
                })
            
            # Kreiraj DataFrame
            if rows:
                df = pd.DataFrame(rows)
                # Dodaj summary red
                summary = pd.DataFrame([{
                    "Rb.": "",
                    "Firma": "UKUPNO",
                    "Naziv artikla": "",
                    "Šifra": "",
                    "Brend": "",
                    "Cijena (EUR)": "",
                    "Akcijska cijena (EUR)": "",
                    "Bod": f"Broj stavki: {len(items)}",
                    "Status": f"Cenovnik: {pl.name}"
                }])
                df = pd.concat([df, summary], ignore_index=True)
            else:
                # Kreiraj DataFrame sa samo summary redom za prazan cenovnik
                df = pd.DataFrame([{
                    "Rb.": "",
                    "Firma": "UKUPNO",
                    "Naziv artikla": "",
                    "Šifra": "",
                    "Brend": "",
                    "Cijena (EUR)": "",
                    "Akcijska cijena (EUR)": "",
                    "Bod": "Broj stavki: 0",
                    "Status": f"Cenovnik: {pl.name}"
                }])
            
            # Izvezi u Excel
            return ExcelReports.export_dataframe(df, output_path)
