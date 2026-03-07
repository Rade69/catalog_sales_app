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
