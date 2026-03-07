from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class MappedColumns:
    """Rezultat mapiranja kolona."""
    code: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    regular_price: Optional[str] = None
    discount_price: Optional[str] = None
    points: Optional[str] = None


@dataclass
class ExcelRow:
    """Podaci iz jednog reda Excel fajla."""
    row_number: int
    supplier_code: Optional[str]
    product_name: str
    brand: Optional[str]
    regular_price: Decimal
    discount_price: Optional[Decimal]
    points: Optional[int] = None


@dataclass
class ImportResult:
    """Rezultat importa kampanje."""
    total_rows: int
    imported_products: int
    new_products: int
    matched_products: int
    skipped_rows: int
    errors: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Mapiranje kolona
# -----------------------------------------------------------------------------

COLUMN_MAPPINGS = {
    "code": [
        "sifra", "šifra", "code", "product code", "article",
        "šifra proizvoda", "sifra proizvoda", "artikal code",
        "sifra artikla", "šifra artikla",
    ],
    "name": [
        "naziv", "artikal", "proizvod", "product name", "description",
        "naziv proizvoda", "name", "product", "artikal naziv",
        "naziv artikla", "naziva artikla",
    ],
    "brand": [
        "brand", "brend", "marka", "manufacturer", "proizvođač"
    ],
    "regular_price": [
        "cijena", "price", "regular price", "mpc", "punoprodajna cijena",
        "redovna cijena", "osnovna cijena", "price regular",
        "km", "mpc km", "km cijena", "cijena km",
        # Fallback za kataloge pogodnosti bez novčane cijene:
        "bod", "bodovi", "boni",
    ],
    "discount_price": [
        "akcija", "discount price", "sale price", "promo price",
        "akcijska cijena", "popust cijena", "promo", "sale"
    ],
    "points": [
        "bod", "bodovi", "boni", "points", "poeni",
    ],
}


def normalize_product_name(name: str) -> str:
    """
    Normalizuje naziv proizvoda za matching.
    
    - lower case
    - trim
    - uklanja duple razmake
    - uklanja većinu specijalnih znakova
    
    Primjer:
        "Philips  Blender 500W  Crni" -> "philips blender 500w crni"
    """
    if not name:
        return ""
    
    # Lower case
    result = name.lower()
    
    # Ukloni specijalne znakove (zadrži slova, brojeve i razmake)
    result = re.sub(r'[^\w\s]', '', result)
    
    # Zamijeni duple razmake sa jednim
    result = re.sub(r'\s+', ' ', result)
    
    # Trim
    result = result.strip()
    
    return result


def _find_column_mapping(
    df_columns: List[str],
    target_mappings: List[str]
) -> Optional[str]:
    """
    Pokušava pronaći kolonu u DataFrame-u koja odgovara jednoj od target mappings.

    Redoslijed pokušaja:
    1. Tačan match po normalizovanom nazivu
    2. Partial match po normalizovanom nazivu
    3. Tačan / partial match po nazivu bez razmaka (npr. "N A Z I V" → "naziv")

    Args:
        df_columns: Lista naziva kolona u DataFrame-u
        target_mappings: Lista mogućih naziva za traženu kolonu

    Returns:
        Naziv kolone iz DataFrame-a ili None
    """
    normalized_df_cols = {
        normalize_product_name(col): col for col in df_columns
    }
    # Verzija bez razmaka — za kolone poput "N A Z I V  A R T I K L A"
    nospace_df_cols = {
        normalize_product_name(col).replace(" ", ""): col for col in df_columns
    }

    # 1. Tačan match
    for target in target_mappings:
        norm_target = normalize_product_name(target)
        if norm_target in normalized_df_cols:
            return normalized_df_cols[norm_target]

    # 2. Partial match (normalni)
    for target in target_mappings:
        norm_target = normalize_product_name(target)
        for norm_col, orig_col in normalized_df_cols.items():
            if norm_target in norm_col or norm_col in norm_target:
                return orig_col

    # 3. Match na kolone sa razmacima između slova (npr. "N A Z I V")
    for target in target_mappings:
        nospace_target = normalize_product_name(target).replace(" ", "")
        if not nospace_target:
            continue
        for nospace_col, orig_col in nospace_df_cols.items():
            if nospace_target in nospace_col or nospace_col in nospace_target:
                return orig_col

    return None


def detect_columns(df: pd.DataFrame) -> MappedColumns:
    """
    Detektuje kolone u Excel fajlu na osnovu mogućih naziva.

    Args:
        df: DataFrame učitan iz Excel fajla

    Returns:
        MappedColumns sa nazivima kolona
    """
    df_columns = [str(col) for col in df.columns.tolist()]

    return MappedColumns(
        code=_find_column_mapping(df_columns, COLUMN_MAPPINGS["code"]),
        name=_find_column_mapping(df_columns, COLUMN_MAPPINGS["name"]),
        brand=_find_column_mapping(df_columns, COLUMN_MAPPINGS["brand"]),
        regular_price=_find_column_mapping(df_columns, COLUMN_MAPPINGS["regular_price"]),
        discount_price=_find_column_mapping(df_columns, COLUMN_MAPPINGS["discount_price"]),
        points=_find_column_mapping(df_columns, COLUMN_MAPPINGS["points"]),
    )


def _detect_header_row(path: Path) -> int:
    """
    Traži red koji sadrži header kolona u Excel fajlu.

    Skenira prvih 15 redova i pronalazi prvi koji ima bar 2 prepoznate
    ključne riječi (naziv, cijena, šifra, brend, bod...).

    Returns:
        Indeks header reda (0-based), default 0.
    """
    df_probe = pd.read_excel(path, header=None, nrows=15)

    all_keywords: set = set()
    for keywords in COLUMN_MAPPINGS.values():
        for kw in keywords:
            norm = normalize_product_name(kw)
            all_keywords.add(norm)
            all_keywords.add(norm.replace(" ", ""))

    for i, row in df_probe.iterrows():
        cell_values = [str(v).strip() for v in row.values if not pd.isna(v) and str(v).strip()]
        if len(cell_values) < 2:
            continue

        matches = 0
        for cell in cell_values:
            norm = normalize_product_name(cell)
            nospace = norm.replace(" ", "")
            if norm in all_keywords or nospace in all_keywords:
                matches += 1
                continue
            # Partial match
            for kw in all_keywords:
                if kw and (kw in norm or norm in kw or kw in nospace or nospace in kw):
                    matches += 1
                    break

        if matches >= 2:
            return int(i)  # type: ignore[arg-type]

    return 0


def parse_price(value: Any) -> Optional[Decimal]:
    """
    Parsira vrijednost u Decimal.
    
    Prihvaća: int, float, string sa tačkom ili zarezom.
    """
    if value is None or pd.isna(value):
        return None
    
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        
        # Zamijeni zarez sa tačkom ako postoji
        value = value.replace(",", ".")
        
        # Ukloni valutu i druge znakove
        value = re.sub(r'[^\d.]', '', value)
        
        if not value:
            return None
        
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None
    
    return None


def clean_string(value: Any) -> Optional[str]:
    """
    Čisti string vrijednost.
    """
    if value is None or pd.isna(value):
        return None
    
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    
    return str(value)


def read_and_clean_excel(path: str | Path) -> Tuple[pd.DataFrame, MappedColumns]:
    """
    Učita Excel fajl i detektuje kolone.
    
    Args:
        path: Putanja do Excel fajla
    
    Returns:
        Tuple (DataFrame, MappedColumns)
    
    Raises:
        FileNotFoundError: Ako fajl ne postoji
        ValueError: Ako ne može detektovati obavezne kolone
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")

    # Automatski pronađi red sa header-om (neke tabele imaju naslov u prvim redovima)
    header_row = _detect_header_row(path)

    # Učitaj Excel sa ispravnim header redom
    df = pd.read_excel(path, header=header_row)

    # Ukloni potpuno prazne redove
    df = df.dropna(how="all")

    # Resetuj index
    df = df.reset_index(drop=True)

    # Detektuj kolone
    mapped = detect_columns(df)
    
    # Validiraj obavezne kolone
    if not mapped.name:
        raise ValueError(
            "Ne mogu detektovati kolonu sa nazivom proizvoda. "
            f"Dostupne kolone: {list(df.columns)}"
        )
    
    if not mapped.regular_price:
        raise ValueError(
            "Ne mogu detektovati kolonu sa cijenom. "
            f"Dostupne kolone: {list(df.columns)}"
        )
    
    return df, mapped


def parse_excel_row(
    row: pd.Series,
    mapped: MappedColumns,
    excel_row_number: int
) -> Tuple[Optional[ExcelRow], Optional[str]]:
    """
    Parsira jedan red iz Excel-a u ExcelRow objekat.
    
    Args:
        row: pandas Series koji predstavlja red
        mapped: Mapirane kolone
        excel_row_number: Broj reda u Excel-u (1-based)
    
    Returns:
        Tuple (ExcelRow ili None, error_message ili None)
    """
    # Naziv proizvoda (obavezan)
    product_name = clean_string(row.get(mapped.name) if mapped.name else None)
    if not product_name:
        return None, "Naziv proizvoda je obavezan"
    
    # Šifra (opciono)
    supplier_code = clean_string(row.get(mapped.code) if mapped.code else None)
    
    # Brand (opciono)
    brand = clean_string(row.get(mapped.brand) if mapped.brand else None)
    
    # Redovna cijena (obavezna)
    regular_price = parse_price(row.get(mapped.regular_price) if mapped.regular_price else None)
    if regular_price is None:
        return None, "Cijena nije validna"
    
    if regular_price <= 0:
        return None, "Cijena mora biti veća od 0"
    
    # Akcijska cijena (opciono)
    discount_price = parse_price(row.get(mapped.discount_price) if mapped.discount_price else None)

    # Bodovi (opciono)
    points: Optional[int] = None
    if mapped.points:
        raw_points = row.get(mapped.points)
        if raw_points is not None and not pd.isna(raw_points):
            try:
                points = int(float(str(raw_points).strip()))
            except (ValueError, TypeError):
                points = None

    return ExcelRow(
        row_number=excel_row_number,
        supplier_code=supplier_code,
        product_name=product_name,
        brand=brand,
        regular_price=regular_price,
        discount_price=discount_price,
        points=points,
    ), None


def load_excel_data(path: str | Path) -> Tuple[List[ExcelRow], MappedColumns, List[Dict[str, Any]]]:
    """
    Učita i parsira cijeli Excel fajl.
    
    Args:
        path: Putanja do Excel fajla
    
    Returns:
        Tuple (lista ExcelRow, MappedColumns, lista grešaka)
    """
    df, mapped = read_and_clean_excel(path)
    
    rows: List[ExcelRow] = []
    errors: List[Dict[str, Any]] = []
    
    for idx, row in df.iterrows():
        excel_row_num = idx + 2  # +2 jer Excel broji od 1, a imamo header
        
        parsed, error = parse_excel_row(row, mapped, excel_row_num)
        
        if error:
            errors.append({
                "row": excel_row_num,
                "error": error,
                "data": {
                    "code": clean_string(row.get(mapped.code) if mapped.code else None),
                    "name": clean_string(row.get(mapped.name) if mapped.name else None),
                    "brand": clean_string(row.get(mapped.brand) if mapped.brand else None),
                }
            })
        else:
            rows.append(parsed)
    
    return rows, mapped, errors
