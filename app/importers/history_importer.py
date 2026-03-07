from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class HistoryMappedColumns:
    """Mapirane kolone za history import."""
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_city: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[str] = None
    installments_count: Optional[str] = None
    # Kolone za uplaćene rate (dinamičke)
    payment_columns: List[str] = field(default_factory=list)


@dataclass
class HistoryRow:
    """Parsirani red iz history Excel-a."""
    row_number: int
    customer_name: str
    customer_phone: Optional[str]
    customer_city: Optional[str]
    product_name: str
    price: Decimal
    installments_count: int
    paid_installments: List[int]  # Brojevi uplaćenih rata (1-based)


@dataclass
class HistoryImportResult:
    """Rezultat history importa."""
    total_rows: int
    customers_created: int
    orders_created: int
    installments_created: int
    payments_created: int
    skipped_rows: int
    errors: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# Mapiranje kolona
# -----------------------------------------------------------------------------

HISTORY_COLUMN_MAPPINGS = {
    "customer_name": [
        "kupac", "ime kupca", "kupac ime", "customer", "customer name",
        "ime i prezime", "ime", "prezime", "ime prezime", "naziv kupca"
    ],
    "customer_phone": [
        "telefon", "phone", "tel", "broj telefona", "mobitel", "mob"
    ],
    "customer_city": [
        "mjesto", "grad", "city", "town", "lokacija"
    ],
    "product_name": [
        "proizvod", "artikal", "naziv", "product", "product name",
        "naziv proizvoda", "roba"
    ],
    "price": [
        "cijena", "price", "iznos", "ukupno", "value"
    ],
    "installments_count": [
        "broj rata", "rate", "installments", "br rata", "broj.rata"
    ]
}


def normalize_column_name(name: str) -> str:
    """
    Normalizuje naziv kolone za lakše mapiranje.
    """
    if not name:
        return ""
    
    # Lower case
    result = name.lower()
    
    # Ukloni specijalne znakove
    result = re.sub(r'[^\w\s]', '', result)
    
    # Ukloni duple razmake
    result = re.sub(r'\s+', ' ', result)
    
    # Trim
    return result.strip()


def _find_column_mapping(
    df_columns: List[str],
    target_mappings: List[str]
) -> Optional[str]:
    """
    Pokušava pronaći kolonu u DataFrame-u koja odgovara target mappings.
    """
    # Normalizuj sve kolone
    normalized_df_cols = {
        normalize_column_name(col): col for col in df_columns
    }
    
    # Pokušaj tačan match
    for target in target_mappings:
        normalized_target = normalize_column_name(target)
        if normalized_target in normalized_df_cols:
            return normalized_df_cols[normalized_target]
    
    # Pokušaj partial match
    for target in target_mappings:
        normalized_target = normalize_column_name(target)
        for norm_col, orig_col in normalized_df_cols.items():
            if normalized_target in norm_col or norm_col in normalized_target:
                return orig_col
    
    return None


def _detect_payment_columns(df_columns: List[str]) -> List[str]:
    """
    Detektuje kolone za uplaćene rate (npr. rata1, rata2, ...).
    """
    payment_cols = []
    
    for col in df_columns:
        normalized = normalize_column_name(col)
        
        # Traži obrasce: rata1, rata_1, payment1, payment_1, r1, itd.
        if re.match(r'^(rata|payment|uplata|r)\s*_?\s*\d+$', normalized):
            payment_cols.append(col)
            continue
        
        # Ili samo "rata" sa brojem u nazivu
        if 'rata' in normalized and re.search(r'\d', normalized):
            payment_cols.append(col)
    
    # Sortiraj po broju rate
    def extract_number(col_name: str) -> int:
        numbers = re.findall(r'\d+', normalize_column_name(col_name))
        return int(numbers[0]) if numbers else 0
    
    payment_cols.sort(key=extract_number)
    
    return payment_cols


def detect_history_columns(df: pd.DataFrame) -> HistoryMappedColumns:
    """
    Detektuje kolone u history Excel fajlu.
    """
    df_columns = [str(col) for col in df.columns.tolist()]
    
    payment_cols = _detect_payment_columns(df_columns)
    
    return HistoryMappedColumns(
        customer_name=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["customer_name"]),
        customer_phone=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["customer_phone"]),
        customer_city=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["customer_city"]),
        product_name=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["product_name"]),
        price=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["price"]),
        installments_count=_find_column_mapping(df_columns, HISTORY_COLUMN_MAPPINGS["installments_count"]),
        payment_columns=payment_cols
    )


def parse_price(value: Any) -> Optional[Decimal]:
    """
    Parsira vrijednost u Decimal.
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
        
        # Zamijeni zarez sa tačkom
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


def parse_int(value: Any, default: int = 1) -> int:
    """
    Parsira vrijednost u int.
    """
    if value is None or pd.isna(value):
        return default
    
    if isinstance(value, (int, float)):
        return int(value)
    
    if isinstance(value, str):
        value = value.strip()
        # Izvuci broj iz stringa
        numbers = re.findall(r'\d+', value)
        if numbers:
            return int(numbers[0])
    
    return default


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


def parse_payment_value(value: Any) -> bool:
    """
    Provjerava da li je rata uplaćena.
    Vraća True ako vrijednost označava uplatu.
    """
    if value is None or pd.isna(value):
        return False
    
    if isinstance(value, (int, float)):
        return value > 0
    
    if isinstance(value, str):
        value = value.strip().lower()
        # Razne oznake za uplatu
        if value in ('x', 'da', 'yes', '1', 'uplaćeno', 'plaćeno', 'paid'):
            return True
        # Ili ako je broj > 0
        try:
            num = float(value.replace(',', '.'))
            return num > 0
        except ValueError:
            pass
    
    return False


def read_and_clean_history_excel(path: str | Path) -> Tuple[pd.DataFrame, HistoryMappedColumns]:
    """
    Učita history Excel fajl i detektuje kolone.
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Excel fajl nije pronađen: {path}")
    
    # Učitaj Excel
    df = pd.read_excel(path)
    
    # Ukloni potpuno prazne redove
    df = df.dropna(how="all")
    
    # Resetuj index
    df = df.reset_index(drop=True)
    
    # Detektuj kolone
    mapped = detect_history_columns(df)
    
    # Validiraj obavezne kolone
    if not mapped.customer_name:
        raise ValueError(
            "Ne mogu detektovati kolonu sa imenom kupca. "
            f"Dostupne kolone: {list(df.columns)}"
        )
    
    if not mapped.product_name:
        raise ValueError(
            "Ne mogu detektovati kolonu sa nazivom proizvoda. "
            f"Dostupne kolone: {list(df.columns)}"
        )
    
    if not mapped.price:
        raise ValueError(
            "Ne mogu detektovati kolonu sa cijenom. "
            f"Dostupne kolone: {list(df.columns)}"
        )
    
    return df, mapped


def parse_history_row(
    row: pd.Series,
    mapped: HistoryMappedColumns,
    excel_row_number: int
) -> Tuple[Optional[HistoryRow], Optional[str]]:
    """
    Parsira jedan red iz history Excel-a.
    """
    # Kupac (obavezan)
    customer_name = clean_string(row.get(mapped.customer_name) if mapped.customer_name else None)
    if not customer_name:
        return None, "Ime kupca je obavezno"
    
    # Telefon (opciono)
    customer_phone = clean_string(row.get(mapped.customer_phone) if mapped.customer_phone else None)
    
    # Mjesto (opciono)
    customer_city = clean_string(row.get(mapped.customer_city) if mapped.customer_city else None)
    
    # Proizvod (obavezan)
    product_name = clean_string(row.get(mapped.product_name) if mapped.product_name else None)
    if not product_name:
        return None, "Naziv proizvoda je obavezan"
    
    # Cijena (obavezna)
    price = parse_price(row.get(mapped.price) if mapped.price else None)
    if price is None:
        return None, "Cijena nije validna"
    
    if price <= 0:
        return None, "Cijena mora biti veća od 0"
    
    # Broj rata (default 1)
    installments_count = parse_int(
        row.get(mapped.installments_count) if mapped.installments_count else None,
        default=1
    )
    
    if installments_count < 1 or installments_count > 10:
        return None, f"Broj rata mora biti između 1 i 10 (dobijeno: {installments_count})"
    
    # Detektuj uplaćene rate
    paid_installments: List[int] = []
    for i, col in enumerate(mapped.payment_columns):
        value = row.get(col)
        if parse_payment_value(value):
            paid_installments.append(i + 1)  # 1-based index
    
    return HistoryRow(
        row_number=excel_row_number,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_city=customer_city,
        product_name=product_name,
        price=price,
        installments_count=installments_count,
        paid_installments=paid_installments
    ), None


def load_history_excel_data(
    path: str | Path
) -> Tuple[List[HistoryRow], HistoryMappedColumns, List[Dict[str, Any]]]:
    """
    Učita i parsira cijeli history Excel fajl.
    """
    df, mapped = read_and_clean_history_excel(path)
    
    rows: List[HistoryRow] = []
    errors: List[Dict[str, Any]] = []
    
    for idx, row in df.iterrows():
        excel_row_num = idx + 2  # +2 jer Excel broji od 1, a imamo header
        
        parsed, error = parse_history_row(row, mapped, excel_row_num)
        
        if error:
            errors.append({
                "row": excel_row_num,
                "error": error,
                "data": {
                    "customer": clean_string(row.get(mapped.customer_name) if mapped.customer_name else None),
                    "product": clean_string(row.get(mapped.product_name) if mapped.product_name else None),
                }
            })
        else:
            rows.append(parsed)
    
    return rows, mapped, errors
