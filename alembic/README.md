# Alembic Migracije - Catalog Sales App

Ovaj folder sadrži Alembic migracije za upravljanje schema-om baze podataka.

## Brzi početak

### Kreiranje nove migracije

Nakon izmjene modela u `app/database/models.py`:

```bash
cd /path/to/catalog_sales_app
alembic migration --autogenerate -m "opis_promjene"
```

Primjeri:
```bash
alembic revision --autogenerate -m "add_customer_email_column"
alembic revision --autogenerate -m "remove_deprecated_table"
alembic revision --autogenerate -m "add_order_status_index"
```

### Primjena migracija

```bash
alembic upgrade head
```

Ovo se **automatski** izvršava pri pokretanju aplikacije kroz `run.py`.

### Pregled historije migracija

```bash
alembic history
```

Za detaljniji prikaz:
```bash
alembic history -v
```

### Trenutno stanje migracija

```bash
alembic current
```

Pokazuje koju migraciju je baza trenutno primijenila.

### Rollback

Rollback na prethodnu migraciju:
```bash
alembic downgrade -1
```

Rollback na specifičnu migraciju:
```bash
alembic downgrade <revision_id>
```

Rollback na početak (uklanja sve tabele):
```bash
alembic downgrade base
```

## SQLite Specifičnosti

### Batch Mode

Ova aplikacija koristi SQLite bazu koja ima ograničenu podršku za `ALTER TABLE` operacije. 
Alembic koristi **batch mode** (`render_as_batch=True`) kao workaround.

U batch mode-u, Alembic:
1. Kreira privremenu tabelu sa novom strukturom
2. Kopira podatke iz stare tabele
3. Briše staru tabelu
4. Preimenuje privremenu tabelu

**Važno:** Neke operacije mogu biti ograničene:
- Dropping kolona iz postojeće tabele može zahtijevati ručnu intervenciju
- Promjena tipa kolone može zahtijevati custom kod u migraciji

### ENUM tipovi u SQLite

SQLite nema native ENUM podršku. SQLAlchemy (i Alembic) čuvaju ENUM vrijednosti kao `TEXT`.
Kada kreirate ENUM u migraciji, Alembic će generisati `CHECK` constraint za validaciju.

## Struktura migracija

```
alembic/
├── env.py              # Konfiguracija migracionog okruženja
├── README.md           # Ovaj fajl
├── script.py.mako      # Template za nove migracije
└── versions/           # Folder sa migracionim fajlovima
    ├── 4369c7de9f8d_initial_schema.py
    └── ...
```

## Konfiguracija

### alembic.ini

Glavni konfiguracijski fajl. Najvažnije postavke:

- `script_location = alembic` - Putanja do migration skripti
- `sqlalchemy.url` - **Ovo je placeholder!** Stvarni URL se generiše dinamički u `env.py`

### env.py

U `env.py` je konfigurisano:
- `target_metadata = Base.metadata` - Automatsko detektovanje promjena modela
- `render_as_batch=True` - SQLite batch mode
- Database URL se čita iz `app.utils.paths.get_db_path()` - isto kao aplikacija

## Uobičajeni scenariji

### Dodavanje nove kolone

1. Dodaj kolonu u model:
```python
class Customer(Base):
    # ... existing fields ...
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```

2. Kreiraj migraciju:
```bash
alembic revision --autogenerate -m "add_customer_email"
```

3. Provjeri generisanu migraciju i primijeni:
```bash
alembic upgrade head
```

### Uklanjanje kolone

1. Ukloni kolonu iz modela
2. Kreiraj migraciju
3. **Pažljivo:** Provjeri migraciju - SQLite batch mode može zahtijevati dodatne provjere

### Promjena tipa kolone

1. Promijeni tip u modelu
2. Kreiraj migraciju
3. **Ručno provjeri:** SQLite može imati problema sa konverzijom tipova

## Troubleshooting

### "Target database is not up to date"

Ako aplikacija prijavi da baza nije ažurna:
```bash
alembic current          # Provjeri trenutnu reviziju
alembic upgrade head     # Primijeni sve migracije
```

### Migracija ne detektuje promjene

Ako `autogenerate` ne detektuje promjene:
1. Provjeri da li su modeli pravilno importovani u `env.py`
2. Pokreni sa `--autogenerate` flagom
3. Ručno napiši migraciju ako je potrebno

### Greška pri rollback-u

Nke migracije nisu reverzibilne. U tom slučaju:
- Napravi backup baze prije migracije
- Ručno kreiraj downgrade migraciju

## Backup prije migracija

Uvijek napravi backup baze prije većih migracija:

```bash
# Linux/macOS
cp data/catalog_sales.db data/catalog_sales.db.backup.$(date +%Y%m%d)

# Ili koristi BackupManager iz aplikacije
```

## Reference

- [Alembic Dokumentacija](https://alembic.sqlalchemy.org/)
- [Alembic Batch Operations](https://alembic.sqlalchemy.org/en/latest/batch.html)
- [SQLAlchemy Core](https://docs.sqlalchemy.org/en/20/core/)
