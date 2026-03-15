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

```text
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

### 6. Dashboard

**Backend: `app/services/dashboard_service.py`**
**Frontend: `app/gui/pages/dashboard_page.py`**

Dashboard je početna stranica aplikacije sa pregledom ključnih poslovnih pokazatelja.

**KPI Kartice (6 komada):**

| KPI                   | Opis                                     | Formula                                            |
| --------------------- | ---------------------------------------- | -------------------------------------------------- |
| Ukupan broj kupaca    | Broj svih kupaca u bazi                  | `COUNT(Customer.id)`                               |
| Aktivne narudžbe      | Narudžbe sa neplaćenim ratama            | COUNT gdje EXISTS rata sa `remaining > 0`          |
| Ukupan preostali dug  | Sva nenaplaćena potraživanja             | `SUM(Installment.amount) - SUM(Payment.amount)`    |
| Naplaćeno ovaj mjesec | Uplate u tekućem mjesecu                 | `SUM(Payment.amount)` WHERE year/month = danas     |
| Rate koje kasne       | Neplaćene rate sa dospijećem u prošlosti | COUNT WHERE `due_date < danas` AND `remaining > 0` |
| Rate ovog mjeseca     | Rate sa dospijećem u tekućem mjesecu     | COUNT WHERE year/month = danas                     |

**Grafovi:**

- Uplate po mjesecima (posljednjih 6 mjeseci) - bar chart
- Broj narudžbi po kampanjama - bar chart

**Tabele:**

- Rate koje kasne (kupac, proizvod, rata, iznos, plaćeno, preostalo, dospijeće, status)
- Rate za ovaj mjesec (ista struktura)

**Računanje preostalog iznosa rate:**

```python
paid_amount = SUM(Payment.amount WHERE installment_id = X)
remaining = installment.amount - paid_amount

if remaining <= 0:        status = "paid"
elif paid_amount > 0:     status = "partially_paid"
else:                     status = "overdue/pending"
```

### 7. Izvještaji

- Excel export izvještaja
- Mjesečni pregled uplata
- Pregled po kampanjama

## Ključne Arhitektonske Odluke

### 1. Slojevita Arhitektura

```text
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

---

## Instalacija na macOS — korak po korak

### Preduvjeti

- macOS 11 (Big Sur) ili noviji
- Apple Silicon (M1/M2/M3) ili Intel Mac
- Internetska veza (samo za instalaciju)

---

### Korak 1 — Instaliraj Homebrew (ako već nemaš)

Otvori **Terminal** (`Cmd + Space` → upiši `Terminal`) i pokreni:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Slijedi upute na ekranu. Kad završi, zatvori i ponovo otvori Terminal.

**Provjera:**

```bash
brew --version
```

Treba ispisati nešto poput `Homebrew 4.x.x`.

---

### Korak 2 — Instaliraj Python 3.11

```bash
brew install python@3.11
```

**Provjera:**

```bash
python3.11 --version
```

Treba ispisati `Python 3.11.x`.

---

### Korak 3 — Prekopiraj fajlove aplikacije na Mac

Prenesi cijeli folder `catalog_sales_app` na Mac, npr. u `Dokumenti`:

```text
/Users/ImeKorisnika/Dokumenti/catalog_sales_app/
```

Možeš koristiti USB disk, AirDrop ili Google Drive.

---

### Korak 4 — Otvori Terminal u folderu aplikacije

```bash
cd ~/Dokumenti/catalog_sales_app
```

---

### Korak 5 — Kreiraj virtualno okruženje

```bash
python3.11 -m venv venv
source venv/bin/activate
```

Ispred prompta u Terminalu sada treba pisati `(venv)`.

---

### Korak 6 — Instaliraj Python biblioteke

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

> Ovo može trajati 2–5 minuta. Pandas i PySide6 su veliki paketi.

---

### Korak 7 — Testiraj pokretanje

Provjeri da li aplikacija radi direktno iz Terminala:

```bash
python run.py
```

Treba se otvoriti prozor aplikacije. Zatvori ga i nastavi na sljedeći korak.

---

### Korak 8 — Napravi .app bundle

```bash
chmod +x build_macos.sh
./build_macos.sh
```

Skripta automatski:

- Briše stare buildove
- Pokreće PyInstaller
- Kreira `dist/Kataloška prodaja.app`

> Build traje 3–10 minuta ovisno o brzini Maca.

---

### Korak 9 — Instaliraj .app u Applications

```bash
cp -r "dist/Kataloška prodaja.app" /Applications/
```

Aplikacija je sada dostupna u **Launchpad-u** i folderu **Applications**.

---

### Korak 10 — Prvo pokretanje (Gatekeeper upozorenje)

macOS će pri prvom pokretanju prikazati upozorenje jer aplikacija nije potpisana.

**Rješenje:**

1. Pronađi `Kataloška prodaja` u Applications folderu (Finder)
2. Desni klik (ili `Ctrl + klik`) na ikonu aplikacije
3. Odaberi **Otvori** (Open)
4. U dijalogu klikni **Otvori** ponovo

Nakon toga aplikacija se može pokretati normalno, dvoklikom.

---

### Gdje se čuvaju podaci?

Podaci se čuvaju na standardnoj macOS lokaciji — **ne** unutar .app fajla:

| Tip podataka  | Lokacija                                                          |
| ------------- | ----------------------------------------------------------------- |
| Baza podataka | `~/Library/Application Support/KataloskaProdaja/catalog_sales.db` |
| Backup kopije | `~/Library/Application Support/KataloskaProdaja/backup/`          |
| Log fajlovi   | `~/Library/Application Support/KataloskaProdaja/logs/app.log`     |

Ove putanje su vidljive u aplikaciji na stranici **Postavke**.

---

### Backup podataka

Aplikacija automatski kreira backup baze svaki put kad se pokrene (čuva 7 kopija).

Ručni backup možeš napraviti u aplikaciji: **Postavke → Kreiraj backup sada**.

---

### Ažuriranje aplikacije

Kad dobiješ novu verziju fajlova:

```bash
cd ~/Dokumenti/catalog_sales_app
source venv/bin/activate
pip install -r requirements.txt   # samo ako su se promijenile biblioteke
./build_macos.sh
cp -r "dist/Kataloška prodaja.app" /Applications/
```

> Podaci u bazi se ne mijenjaju pri ažuriranju.

---

### Rješavanje problema

**Aplikacija se ne otvara / ruši pri pokretanju:**

1. Otvori Terminal
2. Pokreni direktno: `python run.py`
3. Pogledaj greške u log fajlu: `~/Library/Application Support/KataloskaProdaja/logs/app.log`

**"python3.11: command not found":**

```bash
# Apple Silicon:
export PATH="/opt/homebrew/bin:$PATH"
# Intel:
export PATH="/usr/local/bin:$PATH"
```

**Greška pri instalaciji biblioteka:**

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Git Repository

- **master** - stabilna verzija (initial commit)
- **dev** - razvojna grana (aktivni razvoj)

## Verzije

- **0.1** - Initial commit (osnovna struktura, CRUD kupci)
- **0.2** - Import kampanja iz Excel-a
- **0.3** - Narudžbe sa automatskim ratama
- **0.4** - Import istorijskih podataka
- **0.5** - Dashboard sa KPI-jevima, grafovima i tabelama

## Autori

- Radovan (<radovan1969@gmail.com>)
