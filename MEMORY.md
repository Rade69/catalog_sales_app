# Project Memory - Kataloška Prodaja

## Verzije

- **v0.29** (2026-03-23) - DTO (Data Transfer Objects) umjesto session.expunge() pattern
- **v0.28** (2026-03-23) - Unit testovi za servise (77 testova, 91% coverage)
- **v0.27** - App ikonica (katalog + EUR znak)
- **v0.26** - Logiranje, auto-backup, Settings, macOS packaging
- **v0.25** (2026-03-13) - Svi iznosi u EUR, parser ispravan, uplate pojednostavljene
- **v0.24** - Dashboard period filter uklonjen, CustomersPage fix extra query, SQLite WAL mode

---

## v0.29 - DTO (DATA TRANSFER OBJECTS)

### Problem
Korišten je krhki `session.expunge()` pattern širom servisa:
```python
for order in orders:
    for inst in order.installments:
        session.expunge(inst)
    session.expunge(order)
```
Svaki novi relationship koji nije expunge-ovan uzrokovao je `DetachedInstanceError`.

### Rješenje
Uvedeni DTO (Data Transfer Object) dataclasses koji kopiraju podatke iz ORM objekata **unutar** `session_scope()` bloka, prije zatvaranja sesije.

### 📁 app/dto.py (NOVI FAJL)

**DTO klase:**
- `CustomerDTO`: id, full_name, phone, city, address, note, is_active
- `ProductDTO`: id, name, normalized_name, brand, model, supplier_code, category, ...
- `CampaignDTO`: id, name, start_date, end_date, status, source_excel_filename, note
- `InstallmentDTO`: id, order_id, installment_number, due_date, amount, status, paid_at, note, **paid_amount**, **remaining_amount**
- `PaymentDTO`: id, installment_id, payment_date, amount, note
- `OrderDTO`: id, customer_id, **customer_name** (denormalizovano), campaign_id, order_date, status, product_name_snapshot, ..., installments: list[InstallmentDTO]
- `PriceListItemDTO`: id, price_list_id, row_number, supplier_code, name, brand, supplier, prices, points, status
- `CampaignPriceDTO`: id, campaign_id, product_id, regular_price, discount_price, points, status_label

**Helper funkcije:**
- `_to_customer_dto()`, `_to_product_dto()`, `_to_campaign_dto()`
- `_to_installment_dto()` - automatski računa paid_amount i remaining_amount
- `_to_payment_dto()`, `_to_order_dto()` - konvertuje i ugniježđene installments
- `_to_price_list_item_dto()`, `_to_campaign_price_dto()`

### 🔧 Ažurirani Servisi

**customer_service.py:**
```python
def list_customers() -> list[CustomerDTO]  # umjesto list[Customer]
def get_customer() -> Optional[CustomerDTO]
def create_customer() -> CustomerDTO
def update_customer() -> CustomerDTO
```

**order_service.py:**
```python
def list_orders() -> List[OrderDTO]  # umjesto List[Order]
def get_order_details() -> Optional[OrderDTO]
def create_order() -> OrderDTO  # vraća DTO sa već generisanim ratama
def get_orders_for_customer() -> List[OrderDTO]
```

**payment_service.py:**
```python
def get_installment() -> InstallmentDTO
def create_payment() -> PaymentDTO
def get_installments_for_payment() -> List[InstallmentDTO]
def get_installment_details() -> Optional[InstallmentDTO]
def get_payments_for_installment() -> List[PaymentDTO]
```

**campaign_service.py:**
```python
def list_campaigns() -> List[CampaignDTO]
def get_campaign_by_name() -> Optional[CampaignDTO]
def create_campaign() -> CampaignDTO
def list_campaign_products() -> List[CampaignPriceDTO]
```

**price_list_service.py:**
```python
def get_items() -> list[PriceListItemDTO]
```

### 🎯 Prednosti

1. **Nema više `DetachedInstanceError`** - podaci su kopirani u obične klase
2. **Nema manualnog `session.expunge()`** - čišći kod
3. **Izračunate vrijednosti u DTO** - `InstallmentDTO.paid_amount` i `remaining_amount` se računaju jednom u servisu
4. **Denormalizacija** - `OrderDTO.customer_name` umjesto `order.customer.full_name` (N+1 fix)
5. **Lakše testiranje** - DTO su obične dataclasses, ne ORM objekti
6. **GUI ne zavisi od SQLAlchemy** - GUI radi sa DTO, ne sa ORM modelima

### 📝 Promjene u GUI-u

Sve stranice sada rade sa DTO:

```python
# Prije (ORM):
order = OrderService.get_order_details(id)
name = order.customer.full_name  # može biti DetachedInstanceError

# Poslije (DTO):
order = OrderService.get_order_details(id)  # vraća OrderDTO
name = order.customer_name  # običan string, uvijek dostupan
```

**Ažurirane stranice:**
- `customers_page.py`: koristi `OrderDTO.customer_name` i `OrderDTO.installments`
- `orders_page.py`: koristi `OrderDTO` i `CampaignDTO`
- `payments_page.py`: koristi `InstallmentDTO` (sa paid_amount, remaining_amount)
- `installments_page.py`: koristi `InstallmentDTO`

### 🧪 Testovi

Ažurirani testovi da rade sa DTO:
- `test_order_service.py`: `test_get_existing_order` koristi `order.customer_name`
- `test_payment_service.py`: `test_get_existing_installment` koristi `installment.order_id`

Svih 77 testova prolazi.

### 📊 Statistika

```
app/dto.py                 +220 linija (novo)
app/services/*.py          -100 linija (uklonjeni expunge)
app/gui/pages/*.py         -50 linija (pojednostavljeno)
```

---

## v0.28 - UNIT TESTOVI

### 📦 Test Infrastruktura
- **requirements-dev.txt**: pytest>=7.4, pytest-cov>=4.1
- **pytest.ini**: konfiguracija sa coverage postavkama
- **tests/conftest.py**: fixture-ovi za in-memory SQLite bazu

### 🧪 Testovi (77 ukupno)

**test_payment_service.py (31 test):**
- `_recalculate_installment_status`: 6 testova (paid, partially_paid, overdue, pending, overpaid, multiple payments)
- `_recalculate_order_status`: 3 testa (completed, active, rollback)
- `create_payment`: 9 testova (full, partial, second payment, validation, edge cases)
- `delete_payment`: 3 testa (revert status, revert order, nonexistent)
- `get_installment`: 2 testa (existing, nonexistent)
- `get_installments_for_payment`: 5 testova (overdue, unpaid, all, by customer, search)
- `get_installment_details`: 1 test
- `get_payments_for_installment`: 2 testa (with payments, empty)

**test_order_service.py (33 testa):**
- `validate_order_input`: 12 testova (valid, missing customer, empty product, price validation, installments validation)
- `create_order`: 9 testova (success, installments count, sum equals total, validations, contract number)
- `delete_order`: 3 testa (success, nonexistent, with payments)
- `get_order_details`: 2 testa (existing, nonexistent)
- `list_orders`: 3 testa (all, filtered, empty)
- `get_orders_for_customer`: 2 testa (with orders, no orders)
- `update_contract_number`: 2 testa (set, set none)

**test_installment_service.py (13 testova):**
- `generate_for_order`: 6 testova (single, multiple, sum equals total, last amount adjusted, due dates, zero count error)
- `sync_statuses`: 7 testova (fully paid, partially paid, overdue, pending, mixed states, overpaid, no installments)

### 📊 Coverage (91% ukupno)
```
installment_service.py:  96% (55 stmt, 2 miss)
order_service.py:        83% (148 stmt, 25 miss)
payment_service.py:      98% (125 stmt, 2 miss)
```

### 🔧 Popravke u Servisima

**order_service.py:**
```python
# Dodato add(inst) za rate
installments = InstallmentService.generate_for_order(order)
for inst in installments:
    session.add(inst)
```

**installment_service.py:**
```python
# sync_statuses sada ažurira i Order status
for order in orders_to_update.values():
    if order.installments and all(inst.status == InstallmentStatus.PAID for inst in order.installments):
        order.status = OrderStatus.COMPLETED
    elif order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.ACTIVE
```

**payment_service.py:**
```python
# Fixed exception handling u validate_order_input
except (ValueError, TypeError, AttributeError, Exception):
    return False, "Neispravna cijena."
```

### 🚀 Pokretanje Testova
```bash
# Svi testovi
pytest

# Sa coverage
coverage run -m pytest
coverage report

# Specifičan fajl
pytest tests/test_payment_service.py -v

# Coverage za specifične servise
coverage report --include="app/services/payment_service.py" -m
```

---

## v0.27 - APP IKONICA

**assets/icon.svg:**
- Vektorska ikonica (1024x1024)
- Tamno plava pozadina (#1e3c72)
- Bijela silueta kataloga
- EUR znak u donjem desnom uglu

**assets/icon.png:**
- 1024x1024 PNG (generisan iz SVG)

**scripts/make_icon.py:**
- Konvertuje SVG → PNG → ICNS (macOS format)
- Kreira iconset folder sa svim veličinama

**build_macos.sh:**
- Automatski generiše ICNS prije PyInstaller builda

**katalog.spec:**
- Referencira assets/icon.icns za .app bundle

---

## v0.25 - DETALJNE PROMJENE

### 🔄 KM → EUR Konverzija
- **Zamijenjene sve KM reference sa EUR** (15+ fajlova)
- Sve kolone, label-e, izvještaji, poruke sada koriste EUR
- Nema više konverzije EUR → KM u parseru

### 📅 Parser - Ispravni Datumi
- **Godina se čita iz zaglavlja bloka** (npr. "Oktobar 2025.god.")
- **Datumi iz kolona** se parseuju sa tom godinom
- **Logika:** Ako je mjesec < block_month → godina+1
- Ignoriše se greška "2023" iz Excel-a (kolone 11, 12)

### 💰 Logika Plaćanja
- **Koriste se kolone "Ukupno" i "Preostalo"** iz Excel-a
- **Ako je Ukupno ≥ Vrijednost** → SVE rate su PLAĆENE
- **Ako je Ukupno > 0** → izračunaj broj plaćenih rata
- **Tolerancija zaokruživanja:** 0.20 EUR

### 💳 Payments Page - Pojednostavljeno
- **Panel za uplate:** Prikazuje samo "Iznos rate"
- **Uklonjena dugmad:** "Uplati puni iznos", "Uplati preostalo"
- **Uklonjeno računanje:** "Preostalo", "Razlika"
- **Filter:** Kad je kupac odabran → prikazuju se samo neplaćene rate
- **Isplaćeni ugovori** (npr. Blac 3 set) se ne prikazuju 10 puta

### 📜 Nove Skripte
- `import_all_6_blocks_final.py` - Uvoz sa ispravnom logikom plaćanja
- `create_payments_from_all_blocks.py` - Kreiranje uplata iz svih blokova
- `backup_database.py` - Backup baze podataka
- `fix_*.py` - Skripte za popravke (datumi, rate, konverzije)

---

## Dokumentacija

Za kompletnu dokumentaciju o arhitekturi, implementiranim funkcionalnostima i tehnologijama, pogledaj:

- **[DOKUMENTACIJA.md](./DOKUMENTACIJA.md)** - Detaljan opis cijele aplikacije

## Brze Reference

### Struktura
```
app/
├── database/     # Modeli i database konfiguracija
├── gui/          # PySide6 interfejs
├── importers/    # Excel importeri
├── services/     # Business logika
├── reports/      # Excel reporti
└── utils/        # Pomoćne klase
```

### Ključni Fajlovi
- `run.py` - Ulazna tačka
- `app/database/models.py` - SQLAlchemy modeli (datetime.now(UTC))
- `app/gui/main_window.py` - Glavni prozor (sidebar sa SVG ikonama, 7 modula)
- `app/gui/icons.py` - SVG ikonice za navigaciju
- `app/gui/pages/dashboard_page.py` - Dashboard (RED1: 4 KPI, RED2: 2 statusa, RED3: 2 tabele)
- `app/gui/pages/campaigns_page.py` - Kampanje: import u modalnom dijalogu
- `app/gui/pages/orders_page.py` - Narudžbe: dropdown kampanja/proizvoda, auto-fill cijene
- `app/gui/pages/price_list_page.py` - Cjenovnik: import sa prepoznavanjem firme, pregled, pretraga
- `app/gui/widgets/status_badge.py` - Status badge widgeti
- `app/services/dashboard_service.py` - get_dashboard_kpis(), get_status_kpis(), tabele rata
- `app/services/campaign_service.py` - Import kampanja, list_campaign_products (expunge fix)
- `app/services/price_list_service.py` - Import cjenovnika sa detekcijom firme (supplier)
- `app/services/order_service.py` - Narudžbe (koristi InstallmentService)
- `app/services/installment_service.py` - Rate (sync_statuses)
- `app/services/history_import_service.py` - Import istorije
- `app/services/payment_service.py` - Uplate (validacija preplate)
- `app/importers/excel_importer.py` - Excel parser: _detect_header_row, no-space matching
- `migrate_supplier.py` - Migracija za dodavanje supplier kolone

### Dashboard - Redizajn (v0.7)

**Layout:**
- **RED 1** - 4 KPI kartice sa ikonicama:
  - 👥 Ukupan broj kupaca
  - 📋 Aktivne narudžbe
  - 💰 Ukupan preostali dug
  - 💳 Naplaćeno ovaj mjesec

- **RED 2** - 2 Status kartice (žuti alert stil):
  - ⚠️ Rate koje kasne
  - 📅 Rate ovog mjeseca

- **RED 3** - 2 Tabele:
  - Rate koje kasne (Kupac, Proizvod, Rata, Plaćeno, Preostalo, Dospijeće)
  - Rate ovog mjeseca (isto + Status badge)

**Uklonjeno:**
- Grafovi (monthly payments, orders by campaign)
- Brze akcije

**Service metode:**
```python
get_dashboard_kpis()      # 4 KPI-ja za RED 1
get_status_kpis()         # 2 statusa za RED 2
get_overdue_installments()    # tabela rata koje kasne
get_current_month_installments()  # tabela rata ovog mjeseca
```

### Statusi Rata (STATUS_CONFIG)
- `paid` → PLAĆENO (zelena #dcfce7)
- `overdue` → KASNI (crvena #fee2e2)
- `partially_paid` → DJELIMIČNO (žuta #fef3c7)
- `pending` → ČEKA (siva #f3f4f6)
- `active` → AKTIVAN (plava #dbeafe)

### Git
- Email: radovan1969@gmail.com
- Grane: master (stable), dev (development)

### Verzije
- **0.5** - Dashboard sa KPI-jevima, grafovima i tabelama
- **0.6** - GUI poboljšanja (badge-ovi, ikonice, prečice, brze akcije)
- **0.7** - Dashboard redizajn (bez grafova, 3 reda: KPI, Status, Tabele)
- **0.8** - Cjenovnik sa supplier kolonom (prepoznavanje firme iz Excel-a)
- **0.9** - Sidebar redizajn (SVG ikonice, Postavke sekcija, backup premješten)
- **0.10** - Table helpers (konzistentan stil tabela, empty state, numeric items)
- **0.11** - Dashboard v2: tamno plavi sidebar/topbar, SVG ikonice na dugmad, delete funkcije
- **0.12** - PaymentsPage redizajn: filteri, panel za uplatu, historija uplata
- **0.13** - Excel izvještaj naplate: format "EVIDENCIJA O UPLATAMA RATA"
- **0.14** - Fix N+1 query u sync_statuses(), uklonjen mrtav kod iz PaymentService
- **0.15** - InstallmentsPage: prava stranica za pregled svih rata (zamjena placeholder-a)
- **0.16** - PaymentsPage: dodano "Obriši uplatu" dugme u historiji uplata
- **0.17** - Sitni bugovi i cleanup (naslov, duplikati, print() linije)
- **0.18** - Dashboard period filter uklonjen, CustomersPage fix extra query, SQLite WAL mode
- **0.19** - ReportsPage pojednostavljeno: samo "Izvještaj naplate — Excel" generator
- **0.20** - CustomersPage redizajn: master-detail sa listom narudžbi kupca
- **0.21** - OrdersPage: dodano polje "Broj ugovora" (contract_number) u formu i tabelu
- **0.22** - Pretraga po broju ugovora u Uplatama i Ratama (PaymentsPage, InstallmentsPage)
- **0.23** - OrdersPage: dva taba (Nova/Pregled), cjenovnik/pogodnosti izvor; Dashboard: header sa datumom, KPI sa ikonicama; CustomersPage: 8 kolona u tabeli (Plaćeno, Preostalo, Završava, Kasni)
- **0.24** - Povećanje fontova za bolju čitljivost: globalno 13px→15px, veći padding u tabelama i inputima, veće KPI vrijednosti (36px)

### SVG Ikonice (icons.py)
**19 ikona:** dashboard, customers, orders, campaigns, payments, reports, settings, backup, pricelist, import, refresh, delete, save, cart, search, credit-card, chart, calendar, alert

**Helper funkcije:**
```python
get_icon(icon_name, color, size) -> QIcon
get_pixmap(icon_name, color, size) -> QPixmap
create_icon_label(icon_name, color, size) -> QLabel
```

### Dashboard - Redizajn v2 (v0.11)

**Sidebar:**
- Gradijent: `#1e3c72` → `#2a5298`
- Širina: 220px
- Backup dugme na dnu (☁️)

**TopBar:**
- Pozadina: `#1f4f9f`
- Naslov: "Prodajni Dashboard"
- Dropdown: "Period: Ovaj mjesec"
- Dugme: "+ Novo izvještaj"

**Content (#f5f7fb, 30px padding):**
- **RED 1** - 4 KPI kartice (border-left boje: plava, svijetlo plava, crvena, zelena)
- **RED 2** - 2 status kartice (crvena za kasne, narandžasta za ovaj mjesec)
- **RED 3** - 2 tabele u cardovima (Uplate po mjesecima, Rate ovog mjeseca)

### Dugmad sa SVG ikonicama
**Kampanje:** 📥 Uvezi pogodnosti, 🔄 Osvježi, 🗑️ Izbriši
**Cjenovnik:** 📥 Uvezi cjenovnik
**Narudžbe:** 💾 Sačuvaj, 🔄 Očisti, 🗑️ Obriši
**Uplate:** 🔍 Pretraži, 🔴 Kasne, 📅 Ovaj mjesec, 💳 Evidentiraj

### Nove Service Metode

**OrderService:**
```python
delete_order(order_id: int) -> bool  # Briše narudžbu + rate + uplate
get_order_details(order_id: int) -> Optional[Order]  # Sa expunge za customer i installments
```

**CampaignService:**
```python
delete_campaign(campaign_id: int) -> bool  # Briše kampanju + CampaignPrice
```

**PaymentService:**
```python
get_installments_for_payment(filter_type, search) -> list
# filter_type: 'overdue', 'month', 'unpaid', 'all'

get_installment_details(installment_id: int)
get_payments_for_installment(installment_id: int) -> list
```

### PaymentsPage Redizajn (v0.12)

**Toolbar:**
- QComboBox: "Svi kupci" (padajući meni za filtriranje po kupcu)
- QLineEdit: Pretraga po kupcu ili artiklu (radi na textChanged)
- Filteri: Sve rate, Kasne, Ovaj mjesec, Neplaćene (svi rade)

**Layout:**
- Lijevo: Tabela rata (Kupac, Artikal, Rata, Dospijeće, Iznos, Plaćeno, Status)
- Desno: Info panel + Forma za uplatu + Historija uplata

**Forma za uplatu:**
- Iznos (QDoubleSpinBox)
- Brza dugmad: "Uplati puni iznos", "Uplati preostalo"
- Datum (QDateEdit)
- Napomena (QTextEdit)
- Dugmad: "💳 Evidentiraj uplatu", "Očisti"

**Service:**
```python
PaymentService.get_installments_for_payment(
    filter_type='overdue|month|unpaid|all',
    search='',
    customer_id=None  # Novo: filtriranje po kupcu
)
PaymentService.delete_payment(payment_id)  # Briše uplatu i ažurira statuse
```

**Napomena:** `Installment.paid_amount` je property bez settera, pa se koristi `_paid_amount_value` za privremeno čuvanje izračunate vrijednosti.

### Excel Izvještaj Naplate (v0.13)

**Fajl:** `app/reports/naplata_report.py`

**Format:** "EVIDENCIJA O UPLATAMA RATA" (originalni izgled)

**Stilovi:**
- Zaglavlje: tamno plava (`#1F3864`)
- Pod-zaglavlje: svjetlo plava (`#BDD7EE`)
- UKUPNO red: još svjetlija (`#D9E1F2`)
- Alternativni redovi: siva (`#F2F2F2`)

**Kolone:**
- R.br., Br. ugovora, Prezime i ime, Šifra proizvoda, Vrijed. (KM), Br. rata
- Rate: I, II, III... (rimski brojevi)
- Datumi: npr. "15.jan.", "15.feb."
- Ukupno (KM), Preostalo (KM)

**Features:**
- Automatsko generisanje datuma iz `installment.due_date`
- Bosanski format brojeva: `1.840,70` (tačka hiljade, zarez decimale)
- Freeze panes na koloni KUPAC (red 6)
- Landscape orijentacija, fit-to-width
- Zaglavlje se ponavlja na svakoj stranici (redovi 4-5)

**GUI:** `reports_page.py` → `_build_naplata_card()`
- Odabir kampanje (dropdown)
- Saradnički broj (input)
- Ime saradnika (input, default: "KRUNIĆ STOJANOVIĆ SANJA")
- Dugme: "📊 Generiraj Excel izvještaj"
- Status poruka sa putanjom do fajla

### Fix DetachedInstanceError
```python
# U create_order() i get_order_details()
session.expunge(order)  # Da objekat ostane upotrebljiv van sesije
```

### Fix N+1 Query (v0.14)

**Problem:** `InstallmentService.sync_statuses()` je pri svakom pokretanju aplikacije
izvršavao **739 dodatnih SQL upita** (jedan po rati za učitavanje uplata).

**Rješenje:** Korištenje `selectinload(Installment.payments)`:

```python
# Prije (N+1 problem):
stmt = select(Installment).order_by(Installment.id)
# Pristup installment.payments okida novi SQL upit za svaku ratu

# Poslije (fix):
stmt = (
    select(Installment)
    .options(selectinload(Installment.payments))  # Učitava sve uplate jednim IN upitom
    .order_by(Installment.id)
)
```

**Rezultat:** 739 upita → 1 upit pri pokretanju aplikacije.

### Uklonjen Mrtav Kod (v0.14)

Iz `app/services/payment_service.py` uklonjeno:
- `InstallmentLookupRow` (dataclass)
- `list_installments()` (~35 linija)
- `build_installment_lookup()` (~20 linija)
- `list_payments()` (~30 linija)

Ove metode se nisu koristile u aktivnom GUI kodu (samo u `payments_page_backup.py`).

### InstallmentsPage (v0.15)

**Fajl:** `app/gui/pages/installments_page.py`

**Layout:**
- **Toolbar:**
  - QComboBox: "Svi kupci" (filter po kupcu)
  - QLineEdit: Pretraga po kupcu ili artiklu
  - Tab dugmad: ⚠ Kasne rate, 📅 Ovaj mjesec, 💳 Sve neplaćene, ☰ Sve rate
  - Dugme: "↻ Osvježi"

- **Lijevo panel:** Tabela rata (7 kolona)
  - Kupac, Artikal, Rata, Dospijeće, Iznos (KM), Plaćeno (KM), Status

- **Desno panel:** Detalji rate (read-only)
  - Ime kupca, artikal, broj rate, dospijeće
  - Status badge (boja po statusu)
  - Iznosi: Rata, Plaćeno, Preostalo

**Statusi i boje:**
```python
_STATUS_COLOR = {
    "pending":        ("#f59e0b", "#fffbeb"),   # žuta
    "partially_paid": ("#3b82f6", "#eff6ff"),   # plava
    "paid":           ("#10b981", "#f0fdf4"),   # zelena
    "overdue":        ("#ef4444", "#fef2f2"),   # crvena
    "cancelled":      ("#9ca3af", "#f9fafb"),   # siva
}

_STATUS_LABEL = {
    "pending":        "Na čekanju",
    "partially_paid": "Djelimično",
    "paid":           "Plaćeno",
    "overdue":        "Kasni",
    "cancelled":      "Otkazano",
}
```

**Service:** Koristi isti `PaymentService.get_installments_for_payment()` kao i `PaymentsPage`.

**Napomena:** Stranica je read-only (samo pregled). Uplata se radi na stranici "Uplate".

### Obriši Uplatu (v0.16)

**Fajl:** `app/gui/pages/payments_page.py`

**Lokacija:** Panel "Historija uplata ove rate" (desni panel)

**Implementacija:**
- History tabela ima 4 stupca: Datum, Iznos (KM), Napomena, [Akcija]
- 4. stupac sadrži 🗑 dugme (28x28px, crveni border)
- Klik na 🗑 → potvrdni dijalog sa iznosom uplate
- Potvrda → `PaymentService.delete_payment(payment_id)`
- Nakon brisanja: automatsko osvježavanje tabele i info panela

**Metoda:**
```python
def _delete_payment(self, payment_id: int, iznos: str) -> None:
    """Briše uplatu nakon potvrde."""
    # Potvrdni dijalog
    # Poziva PaymentService.delete_payment()
    # Osvježava: _show_installment_details() i _load_installments()
```

**Napomena:** `PaymentService.delete_payment()` automatski ažurira:
- Status rate (paid → partially_paid ili overdue)
- Status narudžbe (completed → active)

### Cleanup i WAL Mode (v0.17-v0.18)

**v0.17 — Sitni bugovi:**
- Naslov prozora: "Kataloška prodaja — pregled koncepta" → "Kataloška prodaja"
- Uklonjeno duplo kreiranje `_create_settings_page()`
- Uklonjeni svi `print()` debug pozivi iz `orders_page.py` i `payments_page.py`

**v0.18 — Performance i cleanup:**
- **Dashboard:** Uklonjen `period_combo` dropdown (nije bio implementiran)
- **CustomersPage:** Fix extra query pri kliku na kupca
  - Prije: `list_customers()` se zvao ponovo za svaki klik
  - Sada: `get_customer(customer_id)` — direktan upit po ID-u
- **SQLite WAL mode:**
  ```python
  PRAGMA journal_mode=WAL
  PRAGMA synchronous=NORMAL
  ```
  - Omogućava čitanje tokom pisanja bez blokiranja
  - Bolje performanse pri istovremenom čitanju/pisanju

### Nova Servisna Metoda (v0.18)

**CustomerService:**
```python
@staticmethod
def get_customer(customer_id: int) -> Optional[Customer]:
    """Dohvaća jednog kupca po ID-u."""
```

### ReportsPage Pojednostavljenje (v0.19)

**Prije:** Dva bloka na stranici Izvještaji:
1. "Izvještaji — mjesečne uplate" — tabela + eksport u Excel
2. "Izvještaj naplate — Excel" — kompleksni Excel generator

**Sada:** Samo drugi blok (kompleksni Excel generator)

**Napomena:** `ReportService` i `ExcelReports` ostaju u kodu jer se mogu koristiti u budućnosti.

**Fajlovi:**
- `app/gui/pages/reports_page.py` — samo `_build_naplata_card()`
- `app/reports/naplata_report.py` — generator Excel izvještaja

### CustomersPage Redizajn (v0.20)

**Prije:** Forma lijevo + lista kupaca desno (bez narudžbi)

**Sada:** Master-detail layout (QSplitter)

**Lijevo (1/3, 280-380px):**
- Naslov "Kupci"
- Pretraga (ime, telefon, grad)
- Tabela: Ime i prezime, Grad
- Dugmad: "+ Novi kupac" (primary), "Obriši" (secondary)
- Brojač: "X kupaca"

**Desno (2/3):**
- Placeholder: "← Odaberi kupca iz liste..."
- Kartica kupca (sakrivena dok nema selekcije):
  - **Forma:** Ime, Telefon, Mjesto, Adresa, Napomena
  - **Dugmad:** "💾 Sačuvaj izmjene", "Odustani"
  - **Tabela narudžbi:** Br. ugovora, Artikal, Cijena, Rata, Datum, Status

**Nova Servisna Metoda:**
```python
OrderService.get_orders_for_customer(customer_id: int) -> List[Order]
```

**Prečice:**
- `Ctrl+N` — Novi kupac

**Statusi Narudžbi (boje):**
- Aktivna → zelena (`#059669`)
- Završena → siva (`#6b7280`)
- Otkazana → crvena (`#dc2626`)

### Broj Ugovora (v0.21)

**OrderService:**
```python
OrderService.create_order(
    customer_id, product_name, price, installments,
    campaign_id=None,
    contract_number=None  # NOVO: opciono
)
```

**OrdersPage UI:**
- **Forma:** Red 3 — "Broj ugovora" (opciono, placeholder: "npr. 4-1-11-2-1-3")
- **Tabela:** Stupac 1 — "Br. ugovora"
  - Plava boja (`#1d4ed8`) ako postoji broj
  - "—" ako nema broja

**Model:**
- `Order.contract_number` — VARCHAR, nullable

### Pretraga po Broju Ugovora (v0.22)

**PaymentService:**
```python
PaymentService.get_installments_for_payment(
    filter_type='overdue|month|unpaid|all',
    search='4-1-11',  # Pretražuje: kupac, artikal, contract_number
    customer_id=None
)
```

**UI Placeholder:**
- "🔍 Pretraži po kupcu, artiklu ili br. ugovora..."

**Stranice:**
- `PaymentsPage` (Uplate)
- `InstallmentsPage` (Rate)

### Narudžbe - Broj Rata
```python
# QComboBox umjesto QSpinBox
self.installments_combo = QComboBox()
self.installments_combo.addItems([f"{i} rata" for i in range(1, 11)])
installments = self.installments_combo.currentIndex() + 1
```

### Ključne Implementacije

#### N+1 Query Fix (dashboard_service.py)
```python
# Koristi subquery sa GROUP BY umjesto upita u petlji
paid_sum_subq = select(Payment.installment_id, func.sum(Payment.amount))
    .group_by(Payment.installment_id).subquery()
```

#### Sync Statusa Rata (installment_service.py)
```python
InstallmentService.sync_statuses()  # Poziva se u run.py pri pokretanju
```

#### Detekcija Firme u Cjenovniku (price_list_service.py)
```python
# Red je naziv firme ako ima naziv, ali NEMA šifru, cijenu ili brand
is_supplier_row = (
    name_str
    and is_empty_or_header(supplier_code_val)
    and is_empty_or_header(regular_price_val)
    and (brand_val is None or str(brand_val).strip() in ("", "nan"))
)
if is_supplier_row:
    current_supplier = name_str  # Sačuvaj za naredne proizvode
```

#### Backup Dugme
- 💾 Backup baze u sidebar-u
- Kreira backup u `/backup/` folder

#### Prečice
- `Ctrl+N` - Novi unos (Kupci, Narudžbe)

#### Modalni Import Kampanje
- Import forma premještena iz kartice u modalni dijalog
- Dugme "📥 Import iz Excel-a" u headeru tabele kampanja

#### Sidebar Navigacija (v0.9)
- SVG ikonice umjesto emoji-ja (icons.py)
- Aktivna stavka: plava pozadina, lijeva plava linija, bold tekst
- Hover: tamnija pozadina
- Backup premješten u Postavke sekciju
- 7 modula: Dashboard, Kupci, Narudžbe, Kampanje, Uplate, Izvještaji, Postavke

#### Table Helpers (v0.10)
- `app/gui/table_helpers.py` - zajedničke funkcije za QTableWidget
- `style_table()` - konzistentan stil (visina reda 36px, padding, header, hover)
- `create_numeric_item()` - numeričke ćelije desno poravnate
- `create_status_item()` - status badge widget
- `show_empty_state()` - poruka kad nema podataka ("Nema podataka za prikaz")
- Ažurirane sve stranice: Dashboard, Kupci, Cjenovnik, Kampanje, Narudžbe, Rate, Uplate, Izvještaji
