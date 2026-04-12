# AGENTS.md — Kataloška prodaja (catalog_sales_app)

**Čitaj zajedno s globalnim `~/.claude/AGENTS.md`.**

---

## 1. Stack i okruženje

| Komponenta | Detalj |
|------------|--------|
| Jezik | Python 3.x |
| GUI | PySide6 (Qt 6) |
| ORM | SQLAlchemy 2.0 |
| Migracije | Alembic |
| Excel/ODS | pandas, openpyxl, odfpy |
| DB | SQLite (lokalno) |
| Testiranje | pytest, pytest-cov |
| Build | PyInstaller (macOS .app bundle) |

### Osnovne komande

```bash
# Instalacija
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # za testiranje

# Pokretanje aplikacije
python run.py

# Testiranje
pytest  # svi testovi
pytest --cov=app/services  # testovi sa pokrivenošću

# Migracije
alembic revision --autogenerate -m "opis promjene"
alembic upgrade head

# Build za macOS
chmod +x build_macos.sh
./build_macos.sh
```

---

## 2. Arhitektura i organizacija koda

```
app/
├── gui/
│   ├── main_window.py          # Glavni prozor sa navigacijom
│   ├── pages/                  # Jedna stranica po entitetu (customers, orders...)
│   ├── components/             # Dijeljene UI komponente
│   ├── widgets/                # Custom Qt widgeti
│   ├── styles/                 # QSS fajlovi za styling
│   └── workers.py              # QThread workeri za background DB operacije
├── services/                   # Business logika (jedan servis po entitetu)
├── database/                   # DB konekcija, modeli
├── importers/                  # Excel/ODS importeri
├── reports/                    # Generisanje izvještaja (Excel)
├── utils/                      # Pomoćne funkcije (backup, logging, paths)
└── dto.py                      # Data Transfer Objects
```

### Ključni pattern — QThread workeri

**Svi DB upiti idu na background thread.** Nikad blokirati UI thread.

```python
# ✅ Ispravno — background worker
class LoadCustomersWorker(QThread):
    data_loaded = Signal(list)
    def run(self):
        customers = customer_service.get_all()
        self.data_loaded.emit(customers)

# ❌ Pogrešno — blokira UI
def _load_customers(self):
    self.table.setData(customer_service.get_all())  # Ne!
```

Postojeći workeri u `app/gui/workers.py`:
- `LoadDashboardWorker`, `LoadCustomersWorker`, `LoadOrdersWorker`
- `LoadInstallmentsWorker`, `LoadPaymentsWorker`, `LoadCampaignsWorker`
- `LoadCampaignProductsWorker`

### DTO pattern

Koristiti DTO klase iz `dto.py` umjesto direktnog proslijeđivanja SQLAlchemy objekata u GUI.

**Ne koristiti `session.expunge()`** — to je stari anti-pattern ovog projekta. Umjesto toga, konvertuj ORM objekte u DTO prije zatvaranja sesije:

```python
# ✅ Ispravno — DTO pattern
def get_customer(customer_id: int) -> Optional[CustomerDTO]:
    with session_scope() as session:
        customer = session.get(Customer, customer_id)
        if customer is not None:
            return _to_customer_dto(customer)  # Konverzija u DTO
        return None

# ❌ Pogrešno — stari pattern
def get_customer_old(customer_id: int) -> Optional[Customer]:
    with session_scope() as session:
        customer = session.get(Customer, customer_id)
        if customer is not None:
            session.expunge(customer)  # Anti-pattern — ne koristiti!
        return customer
```

### Servisni sloj

Svaki entitet ima svoj servis u `app/services/`. Servisi:
- Sadrže business logiku
- Koriste DTO pattern
- Vraćaju DTO objekte
- Imaju statičke metode (nema potrebe za instanciranjem)

### Database sloj

- `app/database/database.py`: DB konekcija, session management
- `app/database/models.py`: SQLAlchemy ORM modeli
- Sesije se upravljaju preko `session_scope()` context managera

---

## 3. Migracije — uvijek Alembic

```bash
# Kreiraj novu migraciju
alembic revision --autogenerate -m "opis promjene"

# Primijeni migracije
alembic upgrade head

# Vrati migraciju
alembic downgrade -1
```

**Nikad direktno mijenjati SQLite fajl.** Sve promjene sheme idu kroz Alembic migracije.

---

## 4. Testiranje

### Struktura testova
- Testovi su u `tests/` direktorijumu
- Koristi se pytest sa fixture-ima iz `tests/conftest.py`
- Testiraju se samo servisi (business logika), ne GUI

### Pokrivenost
- Coverage je konfigurisan u `pytest.ini`
- Pokriva samo `app/services/` direktorijum
- Izuzeti su `__init__.py` fajlovi i testovi

### Test fixture-i
- `db`: Database session za testove
- `sample_order`, `sample_customer`, itd.: Testni podaci

### Primjer testa
```python
def test_generate_single_installment(self, db, sample_order):
    """Generisanje 1 rate za order."""
    installments = InstallmentService.generate_for_order(order)
    assert len(installments) == 1
    assert installments[0].amount == Decimal("100.00")
```

---

## 5. Build i deployment

### macOS build
- Koristi PyInstaller za kreiranje `.app` bundle-a
- Specifikacija u `katalog.spec`
- Build skripta: `build_macos.sh`
- Ikonica se generiše automatski ako ne postoji

### Backup sistem
- Automatski backup pri pokretanju aplikacije
- Čuva se 7 backup fajlova
- Backup direktorijum: `~/Library/Application Support/Kataloška prodaja/backups/` (macOS)

---

## 6. Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
|---------|--------|
| DB upit direktno u GUI klasi | Mora ići kroz worker + service |
| `session.expunge()` pattern | Zamijenjeno DTO pattern-om |
| Blokirati UI thread | Aplikacija se zamrzava |
| Direktno mijenjati SQLite | Koristiti Alembic migracije |
| `setStyleSheet()` inline u kodu | QSS fajlovi su autoritet |
| Pristup ORM relacijama iz DTO | Denormalizovati podatke u DTO |
| Instanciranje servisa | Servisi imaju statičke metode |

---

## 7. Konvencije i stil

### Imenovanje
- GUI klase: `MainWindow`, `CustomerPage`, `OrderTableWidget`
- Worker klase: `LoadCustomersWorker`, `SaveOrderWorker`
- Service klase: `CustomerService`, `OrderService`
- DTO klase: `CustomerDTO`, `OrderDTO`
- Funkcije: `snake_case`
- Varijable: `snake_case`

### Importi
- Grupisani importi: standard library, third-party, local
- Apsolutni importi unutar `app/` paketa
- Koristiti `from __future__ import annotations`

### Tipovi
- Eksplicitni type hints za sve funkcije
- Koristiti `Optional[T]` umjesto `T | None` (kompatibilnost)
- Decimal za novčane iznose

### Error handling
- Servisi bacaju izuzetke koje handluje GUI
- Workeri emit-uju `error` signal sa porukom
- Logging preko `app.utils.logger`

---

## 8. Važni kontekst

### Historija projekta
- Zamijenjen stari `session.expunge()` pattern sa DTO pattern-om
- GUI je prebačen na PySide6 (Qt 6)
- Implementiran backup sistem
- Dodati Excel/ODS import/export

### Trenutni fokus
- CRUD operacije za sve entitete
- Excel import kampanja i cjenovnika
- Automatsko generisanje rata
- Evidencija uplata
- Excel izvještaji

### Data flow
1. GUI poziva worker
2. Worker poziva service
3. Service radi DB operaciju i vraća DTO
4. Worker emit-uje signal sa DTO
5. GUI ažurira prikaz

---

## 9. Korisni skriptovi

U `scripts/` direktorijumu:
- `backup_database.py`: Manualni backup
- `create_test_data.py`: Generisanje testnih podataka
- `fix_installment_amounts.py`: Popravka iznosa rata
- `fix_overpaid_orders.py`: Popravka preplaćenih narudžbi
- `import_*.py`: Skripte za import historijskih podataka
- `make_icon.py`: Generisanje ikonice za macOS

---

## 10. Problemi i edge case-ovi

### Decimal precision
- Svi novčani iznosi su `Decimal` tipa
- Zaokruživanje na 2 decimale pri prikazu
- U DB se čuvaju kao `Numeric(10, 2)`

### Datumi i vremena
- Datumi bez vremena: `date` tip
- Vremenske oznake: `datetime` sa timezone
- U DB: `Date` za datume, `DateTime` za vremenske oznake

### Statusi
- Kampanje: `draft`, `active`, `archived`
- Narudžbe: `active`, `completed`, `cancelled`
- Rate: `pending`, `partially_paid`, `paid`, `overdue`, `cancelled`

### Import/export
- Podržani formati: Excel (.xlsx), ODS
- Kodiranje: UTF-8
- Datum formati: YYYY-MM-DD

---

*Ovaj fajl kreira i održava Claude Sonnet kao nadzorni agent. Ažurirano: 2026-04-11*