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
- `app/services/dashboard_service.py` - Dashboard KPI-jevi
- `app/services/campaign_service.py` - Import kampanja
- `app/services/order_service.py` - Narudžbe
- `app/services/history_import_service.py` - Import istorije

### Dashboard KPI-jevi
1. Ukupan broj kupaca - COUNT(Customer)
2. Aktivne narudžbe - narudžbe sa neplaćenim ratama
3. Ukupan preostali dug - SUM(installment.amount) - SUM(payment.amount)
4. Naplaćeno ovaj mjesec - SUM(payment.amount) WHERE current month
5. Rate koje kasne - COUNT WHERE due_date < danas AND remaining > 0
6. Rate ovog mjeseca - COUNT WHERE due_date IN current month

### Git
- Email: radovan1969@gmail.com
- Grane: master (stable), dev (development)
