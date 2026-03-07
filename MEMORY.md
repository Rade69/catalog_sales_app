# Project Memory - Kataloška Prodaja

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
- `app/database/models.py` - SQLAlchemy modeli
- `app/gui/main_window.py` - Glavni prozor
- `app/services/campaign_service.py` - Import kampanja
- `app/services/order_service.py` - Narudžbe
- `app/services/history_import_service.py` - Import istorije

### Git
- Email: radovan1969@gmail.com
- Grane: master (stable), dev (development)
