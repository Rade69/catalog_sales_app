# Memory File for Crush

## Last Commit Message

```
feat: Implementirano upravljanje cenovnicima i uklonjena autentikacija
```

**Opis:**
- Potpuno implementirana funkcionalnost upravljanja cenovnicima (kreiranje, izmena, duplikacija, export)
- Uklonjena obavezna autentikacija pri pokretanju aplikacije
- Ispravljen `NameError` u `PriceListPage` (QWidget import)

**Promene:**
- Dodata nova funkcionalnost: upravljanje cenovnicima sa edit, duplicate, export
- GUI za cenovnike ažuriran sa novim dugmićima i dialogima
- Uklonjen `require_auth()` poziv iz `run.py`
- Dodat `QWidget` import u `price_list_page.py`

**Test Status:** Svi testovi prolaze.
