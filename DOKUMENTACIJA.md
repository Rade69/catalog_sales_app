# Kataloška Prodaja - Dokumentacija

Desktop aplikacija za upravljanje kataloškom prodajom kućanskih aparata i posuđa.

## Tehnologije

- **Python** - programski jezik
- **PySide6** - GUI framework
- **SQLAlchemy** - ORM za rad sa bazom
- **SQLite** - lokalna baza podataka
- **pandas** - obrada Excel podataka
- **openpyxl** - čitanje/pisanje Excel fajlova
- **python-dateutil** - manipulacija datumima

## Arhitektura Projekta

```
catalog_sales_app/
├── run.py                      # Ulazna tačka aplikacije
├── requirements.txt            # Python dependencije
├── README.md                   # Uputstvo za pokretanje
├── .gitignore                  # Git ignore pravila
├── app/
│   ├── __init__.py
│   ├── database/               # Database layer
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy engine, session_scope()
│   │   └── models.py           # SQLAlchemy modeli (Customer, Product, Order...)
│   ├── gui/                    # Prezentacioni layer (PySide6)
│   │   ├── __init__.py
│   │   ├── main_window.py      # Glavni prozor sa navigacijom
│   │   ├── styles.py           # CSS stilovi za aplikaciju
│   │   ├── pages/              # Stranice aplikacije
│   │   │   ├── dashboard_page.py
│   │   │   ├── customers_page.py    # CRUD za kupce
│   │   │   ├── campaigns_page.py    # Import kampanja iz Excel-a
│   │   │   ├── orders_page.py       # Kreiranje narudžbi
│   │   │   ├── installments_page.py # Pregled rata
│   │   │   ├── payments_page.py     # Evidencija uplata
│   │   │   └── reports_page.py      # Izvještaji
│   │   └── widgets/            # Custom widgeti
│   ├── importers/              # Import moduli
│   │   ├── __init__.py
│   │   ├── excel_importer.py   # Import kampanja iz Excel-a
│   │   └── history_importer.py # Import istorijskih podataka
│   ├── services/               # Business logika
│   │   ├── __init__.py
│   │   ├── customer_service.py      # Operacije nad kupcima
│   │   ├── campaign_service.py      # Import i upravljanje kampanjama
│   │   ├── order_service.py         # Kreiranje narudžbi
│   │   ├── installment_service.py   # Operacije nad ratama
│   │   ├── payment_service.py       # Evidencija uplata
│   │   ├── report_service.py        # Generisanje izvještaja
│   │   └── history_import_service.py # Import istorije
│   ├── reports/              # Report moduli
│   │   ├── __init__.py
│   │   └── excel_reports.py  # Excel izvještaji
│   └── utils/                # Pomoćne klase
│       ├── __init__.py
│       └── backup_manager.py # Backup baze podataka
├── data/                     # SQLite baza podataka
└── backup/                   # Backup fajlovi
```

## Database Modeli

### Customer (Kupac)
```python
id, full_name, phone, city, address, note, is_active
```

### Product (Proizvod)
```python
id, supplier_code, name, normalized_name, brand, model, 
category, unit_of_measure, note, is_active
```

### Campaign (Kampanja)
```python
id, name, start_date, end_date, status, source_excel_filename, note
status: DRAFT | ACTIVE | ARCHIVED
```

### CampaignPrice (Cijena u kampanji)
```python
id, campaign_id, product_id, regular_price, discount_price, 
points, status_label
```

### Order (Narudžba)
```python
id, customer_id, campaign_id, product_id, order_date, status,
product_name_snapshot, unit_price_snapshot, total_price_snapshot,
installments_count, first_due_date, note
status: ACTIVE | COMPLETED | CANCELLED
```

### Installment (Rata)
```python
id, order_id, installment_number, due_date, amount, status, paid_at, note
status: PENDING | PARTIALLY_PAID | PAID | OVERDUE | CANCELLED
```

### Payment (Uplata)
```python
id, installment_id, payment_date, amount, note
```

### ImportSession (Audit import-a)
```python
id, import_type, source_filename, status, rows_total, 
rows_successful, rows_failed, message
```

## Implementirane Funkcionalnosti

### 1. Upravljanje Kupcima (CustomersPage)
- Pregled svih kupaca u tabeli
- Pretraga po imenu, telefonu, mjestu
- Kreiranje novog kupca
- Izmjena podataka o kupcu
- Brisanje kupca (ako nema narudžbi)

### 2. Import Kampanja (CampaignsPage)
**Backend: `app/importers/excel_importer.py` + `app/services/campaign_service.py`**

- Detekcija kolona u Excel fajlu (fuzzy matching)
  - Šifra: sifra, šifra, code, product code, article...
  - Naziv: naziv, artikal, proizvod, product name...
  - Brand: brand, brend, marka...
  - Cijena: cijena, price, regular price, mpc...
  - Akcija: akcija, discount price, sale price...

- Normalizacija naziva proizvoda
  - Lowercase, trim, uklanjanje duplih razmaka
  - Uklanjanje specijalnih znakova

- Matching proizvoda (4-stepeni algoritam)
  1. Match po supplier_code (tačan)
  2. Match po normalized_name (tačan)
  3. Match po normalized_name + brand
  4. Kreiranje novog proizvoda

- Kreiranje kampanje sa datumima
- Generisanje CampaignPrice zapisa
- Logovanje grešaka po redovima
- Audit trail (ImportSession, ImportProductMatch)

### 3. Kreiranje Narudžbi (OrdersPage)
**Backend: `app/services/order_service.py`**

- Dropdown za odabir kupca
- Unos naziva proizvoda
- Unos cijene
- Odabir broja rata (1-10)
- Validacija unosa
- Kreiranje Order zapisa sa snapshot podacima
- Automatsko generisanje Installment zapisa
- Korekcija zadnje rate zbog zaokruživanja
- Postavljanje statusa rate na PENDING
- Due date = mjesečno od datuma kreiranja

### 4. Import Istorijskih Podataka
**Backend: `app/importers/history_importer.py` + `app/services/history_import_service.py`**

- Detekcija kolona za istoriju
  - Kupac: kupac, ime kupca, customer...
  - Telefon: telefon, phone, tel...
  - Mjesto: mjesto, grad, city...
  - Proizvod: proizvod, artikal, naziv...
  - Cijena: cijena, price, iznos...
  - Broj rata: broj rata, rate, installments...
  - Rate: rata1, rata2, uplata_1, payment_1...

- Kreiranje kupaca (ako ne postoje)
- Kreiranje proizvoda (ako ne postoje)
- Kreiranje narudžbi (status = COMPLETED)
- Generisanje rata
- Označavanje uplaćenih rata (kreiranje Payment zapisa)
- Detekcija uplate: x, da, yes, 1, broj > 0

### 5. Rate i Uplate
- Pregled svih rata sa statusima
- Evidencija uplata (cijele i djelimične)
- Praćenje preostalih iznosa
- Statusi: PENDING, PAID, OVERDUE

### 6. Izvještaji
- Excel export izvještaja
- Mjesečni pregled uplata
- Pregled po kampanjama

## Ključne Arhitektonske Odluke

### 1. Slojevita Arhitektura
```
GUI (PySide6)
    ↓
Services (Business Logic)
    ↓
Database (SQLAlchemy)
```

- GUI ne sadrži poslovnu logiku
- Svi database pozivi idu kroz service layer
- Service layer koristi `session_scope()` context manager

### 2. Session Management
```python
@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- Automatski commit/rollback
- Expunge za objekte koji se vraćaju GUI-u

### 3. Snapshot Pattern za Narudžbe
- `product_name_snapshot` - naziv proizvoda u trenutku narudžbe
- `unit_price_snapshot` - cijena u trenutku narudžbe
- Istorija ostaje tačna čak i kad se katalog promijeni

### 4. Matching Algoritam
- Hijerarhijski pristup (od najpreciznijeg ka najopštijem)
- Logovanje svakog match-a za audit
- Podrška za ručne korekcije

### 5. Import bez Zaustavljanja
- Greške se loguju po redovima
- Validni redovi se procesuiraju
- Summary sa statistikom na kraju

## Pokretanje Aplikacije

```bash
cd /home/radovan/Desktop/sanja_aplikacija/catalog_sales_app
python run.py
```

## Git Repository

- **master** - stabilna verzija (initial commit)
- **dev** - razvojna grana (aktivni razvoj)

## Verzije

- **0.1** - Initial commit (osnovna struktura, CRUD kupci)
- **0.2** - Import kampanja iz Excel-a
- **0.3** - Narudžbe sa automatskim ratama
- **0.4** - Import istorijskih podataka

## Autori

- Radovan (radovan1969@gmail.com)
