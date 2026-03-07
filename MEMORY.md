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
- `app/database/models.py` - SQLAlchemy modeli (datetime.now(UTC))
- `app/gui/main_window.py` - Glavni prozor (sidebar, status bar, backup)
- `app/gui/pages/dashboard_page.py` - Dashboard (KPI, grafovi, tabele, brze akcije)
- `app/gui/widgets/status_badge.py` - Status badge widgeti
- `app/services/dashboard_service.py` - Dashboard KPI-jevi (N+1 query fix)
- `app/services/campaign_service.py` - Import kampanja
- `app/services/order_service.py` - Narudžbe (koristi InstallmentService)
- `app/services/installment_service.py` - Rate (sync_statuses)
- `app/services/history_import_service.py` - Import istorije
- `app/services/payment_service.py` - Uplate (validacija preplate)

### Dashboard KPI-jevi
1. **Ukupan broj kupaca** - COUNT(Customer)
2. **Aktivne narudžbe** - narudžbe sa neplaćenim ratama
3. **Ukupan preostali dug** - SUM(installment.amount) - SUM(payment.amount)
4. **Naplaćeno ovaj mjesec** - SUM(payment.amount) WHERE current month
5. **Rate koje kasne** - COUNT WHERE due_date < danas AND remaining > 0
6. **Rate ovog mjeseca** - COUNT WHERE due_date IN current month

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

#### Backup Dugme
- 💾 Backup baze u sidebar-u
- Kreira backup u `/backup/` folder

#### Prečice
- `Ctrl+N` - Novi unos (Kupci, Narudžbe)

#### Brze Akcije (Dashboard)
- ➕ Nova narudžba → navigira na OrdersPage
- 💳 Evidentiraj uplatu → navigira na PaymentsPage
- 📊 Otvori izvještaj → navigira na ReportsPage
