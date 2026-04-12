# Memory File for Crush

## Last Commit Message

```
v0.41 - Dodata paginacija, editovanje kampanja i cjenovnika, validacije i SQLCipher podrška
```

**Opis:**
- Implementirana paginacija za rate, cjenovnike i uplate
- Editovanje kampanja sa promjenom statusa (draft/active/archived)
- Editovanje, duplikacija i export cjenovnika u Excel
- SQLCipher enkripcija baze (opciono)
- Validacije unosa za kupce, narudžbe, uplate i cjenovnike

**Promene:**
- `app/gui/pagination.py` - Novi PaginationWidget
- `app/gui/base_page.py` - Nova bazna klasa za stranice
- `app/database/database.py` - SQLCipher podrška
- `app/gui/pages/campaigns_page.py` - Dodato editovanje kampanja
- `app/gui/pages/price_list_page.py` - Edit, duplicate, export, paginacija
- `app/gui/pages/installments_page.py` - Paginacija
- `app/gui/pages/payments_page.py` - Paginacija
- `app/services/*.py` - Validacije, limit/offset parametri
- Testovi: `test_campaign_service.py`, `test_customer_service.py`, `test_price_list_service.py`

**Test Status:** Svi testovi prolaze.
