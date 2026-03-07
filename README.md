# Catalog Sales App

Minimalni, ali profesionalno postavljen kostur offline desktop aplikacije za katalošku prodaju.

## Pokretanje

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Trenutno uključeno

- SQLite baza preko SQLAlchemy ORM
- profesionalni modeli baze
- PySide6 main window sa lijevim menijem
- dashboard sa KPI karticama
- placeholder stranice za Kupce, Kampanje, Narudžbe, Rate, Uplate i Izvještaje
- servis za rate
- osnovni Excel importer
- backup manager

## Sljedeći realni koraci

1. Kupci CRUD
2. Import kampanje iz Excel fajla
3. Narudžba + automatsko generisanje rata
4. Evidencija uplata
5. Excel izvještaji
