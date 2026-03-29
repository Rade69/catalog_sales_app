# AGENTS.md — Kataloška prodaja (catalog_sales_app)

**Čitaj zajedno s globalnim `~/.claude/AGENTS.md`.**

---

## 1. Stack

| Komponenta | Detalj |
|------------|--------|
| Jezik | Python 3.x |
| GUI | PySide6 (Qt 6) |
| ORM | SQLAlchemy 2.0 |
| Migracije | Alembic |
| Excel/ODS | pandas, openpyxl, odfpy |
| DB | SQLite (lokalno) |

---

## 2. Arhitektura

```
app/
├── gui/
│   ├── main_window.py
│   ├── pages/          # Jedna stranica po entitetu (customers, orders...)
│   ├── components/     # Dijeljene UI komponente
│   └── workers.py      # QThread workeri za background DB operacije
├── services/           # Business logika (jedan servis po entitetu)
├── database/           # DB konekcija, modeli
├── importers/          # Excel/ODS importeri
├── reports/            # Generisanje izvještaja
└── dto.py              # Data Transfer Objects
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

Postojeći workeri: `LoadDashboardWorker`, `LoadCustomersWorker`, `LoadOrdersWorker`,
`LoadInstallmentsWorker`, `LoadPaymentsWorker`, `LoadCampaignsWorker`, `LoadCampaignProductsWorker`

### DTO pattern

Koristiti DTO klase iz `dto.py` umjesto direktnog proslijeđivanja SQLAlchemy objekata u GUI.
**Ne koristiti `session.expunge()`** — to je stari anti-pattern ovog projekta.

---

## 3. Migracije — uvijek Alembic

```bash
alembic revision --autogenerate -m "opis promjene"
alembic upgrade head
```

**Nikad direktno mijenjati SQLite fajl.**

---

## 4. Zabrane specifične za ovaj projekat

| Zabrana | Razlog |
|---------|--------|
| DB upit direktno u GUI klasi | Mora ići kroz worker + service |
| `session.expunge()` pattern | Zamijenjeno DTO pattern-om |
| Blokirati UI thread | Aplikacija se zamrzava |
| Direktno mijenjati SQLite | Koristiti Alembic migracije |
| `setStyleSheet()` inline u kodu | QSS fajlovi su autoritet |

---

*Ovaj fajl kreira i održava Claude Sonnet kao nadzorni agent.*
