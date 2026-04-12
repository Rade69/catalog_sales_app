"""
Testovi za price_list_service.py.

Testiraju se:
- PriceListService.list_all
- PriceListService.get_items
- PriceListService.import_from_excel
- PriceListService.delete
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
import pandas as pd

from app.database.models import PriceList, PriceListItem
from app.services.price_list_service import PriceListService


class TestPriceListService:
    """Testovi za PriceListService."""

    def test_list_all_empty(self, db):
        """Dohvatanje svih cjenovnika kada nema cjenovnika."""
        price_lists = PriceListService.list_all()
        assert price_lists == []

    def test_list_all_with_data(self, db):
        """Dohvatanje svih cjenovnika sa podacima."""
        # Kreiraj cjenovnike
        price_list1 = PriceList(name="Cjenovnik 1", source_filename="file1.xlsx")
        price_list2 = PriceList(name="Cjenovnik 2", source_filename="file2.xlsx")
        db.add_all([price_list1, price_list2])
        db.commit()

        price_lists = PriceListService.list_all()
        assert len(price_lists) == 2
        # Treba biti sortirano od najnovijeg
        assert price_lists[0].name == "Cjenovnik 2"
        assert price_lists[1].name == "Cjenovnik 1"

    def test_get_items_empty(self, db):
        """Dohvatanje stavki cjenovnika kada nema stavki."""
        # Kreiraj cjenovnik
        price_list = PriceList(name="Test cjenovnik", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        items, total_count = PriceListService.get_items(price_list.id)
        assert items == []
        assert total_count == 0

    def test_get_items_with_data(self, db):
        """Dohvatanje stavki cjenovnika sa podacima."""
        # Kreiraj cjenovnik
        price_list = PriceList(name="Test cjenovnik", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        # Kreiraj stavke
        items_data = [
            (None, "Proizvod 1", "Brend A", Decimal("100.00"), Decimal("90.00"), 10),
            ("PRD002", "Proizvod 2", "Brend B", Decimal("200.00"), Decimal("180.00"), 20),
            ("PRD003", "Proizvod 3", "Brend C", Decimal("300.00"), None, None),
        ]

        for idx, (code, name, brand, regular_price, discount_price, points) in enumerate(items_data):
            item = PriceListItem(
                price_list_id=price_list.id,
                row_number=idx,
                supplier_code=code,
                name=name,
                brand=brand,
                regular_price=regular_price,
                discount_price=discount_price,
                points=points,
            )
            db.add(item)
        db.commit()

        items, total_count = PriceListService.get_items(price_list.id)

        assert len(items) == 3
        assert total_count == 3
        # Proveri da li su sortirane po row_number
        assert items[0].name == "Proizvod 1"
        assert items[1].name == "Proizvod 2"
        assert items[2].name == "Proizvod 3"

        # Proveri podatke
        assert items[0].brand == "Brend A"
        assert items[0].regular_price == Decimal("100.00")
        assert items[0].discount_price == Decimal("90.00")
        assert items[0].points == 10

        assert items[2].discount_price is None
        assert items[2].points is None

    def test_import_from_excel_basic(self, db):
        """Osnovni test importa iz Excel fajla."""
        # Kreiraj testni Excel fajl
        test_data = pd.DataFrame({
            'Šifra': ['PRD001', 'PRD002', 'PRD003'],
            'Naziv': ['Proizvod 1', 'Proizvod 2', 'Proizvod 3'],
            'Brend': ['Brend A', 'Brend B', 'Brend C'],
            'Cijena': [100.0, 200.0, 300.0],
            'Akcija': [90.0, 180.0, 270.0],
            'Bodovi': [10, 20, 30]
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            # Importuj iz Excel fajla
            imported, skipped = PriceListService.import_from_excel(
                name="Test import",
                excel_path=tmp_path,
            )

            assert imported == 3
            assert skipped == 0

            # Proveri da li je cjenovnik kreiran
            price_lists = PriceListService.list_all()
            assert len(price_lists) == 1
            price_list = price_lists[0]
            assert price_list.name == "Test import"
            assert price_list.source_filename == Path(tmp_path).name

            # Proveri da li su stavke importovane
            items, total_count = PriceListService.get_items(price_list.id)
            assert len(items) == 3
            assert total_count == 3

            # Proveri podatke
            item = next(i for i in items if i.supplier_code == "PRD001")
            assert item.name == "Proizvod 1"
            assert item.brand == "Brend A"
            assert item.regular_price == Decimal("100.00")
            assert item.discount_price == Decimal("90.00")
            assert item.points == 10

        finally:
            # Obriši privremeni fajl
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_from_excel_duplicate_name(self, db):
        """Import sa duplikatnim nazivom cjenovnika."""
        # Prvo kreiraj cjenovnik
        price_list = PriceList(name="Test cjenovnik", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        # Kreiraj testni Excel fajl
        test_data = pd.DataFrame({
            'Šifra': ['PRD001'],
            'Naziv': ['Proizvod 1'],
            'Cijena': [100.0],
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            # Pokušaj import sa istim nazivom
            with pytest.raises(ValueError, match="Cjenovnik sa nazivom 'Test cjenovnik' već postoji."):
                PriceListService.import_from_excel(
                    name="Test cjenovnik",
                    excel_path=tmp_path,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_from_excel_missing_name_column(self, db):
        """Import iz Excel fajla bez kolone za naziv."""
        # Kreiraj testni Excel fajl sa potpuno nepoznatim nazivima kolona
        test_data = pd.DataFrame({
            'Kolona1': ['PRD001'],
            'Kolona2': ['Proizvod 1'],
            'Kolona3': [100.0],
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            with pytest.raises(ValueError, match="Excel fajl ne sadrži kolonu za naziv proizvoda"):
                PriceListService.import_from_excel(
                    name="Test",
                    excel_path=tmp_path,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_from_excel_with_supplier_rows(self, db):
        """Import iz Excel fajla sa redovima za dobavljače."""
        # Kreiraj testni Excel fajl sa redovima za dobavljače
        test_data = pd.DataFrame({
            'Šifra': [None, 'PRD001', 'PRD002', None, 'PRD003'],
            'Naziv': ['Dobavljač 1', 'Proizvod 1', 'Proizvod 2', 'Dobavljač 2', 'Proizvod 3'],
            'Brend': [None, 'Brend A', 'Brend B', None, 'Brend C'],
            'Cijena': [None, 100.0, 200.0, None, 300.0],
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            imported, skipped = PriceListService.import_from_excel(
                name="Test sa dobavljačima",
                excel_path=tmp_path,
            )

            # Očekujemo 3 proizvoda i 2 reda za dobavljače (preskočeno)
            assert imported == 3
            assert skipped == 2

            # Proveri cjenovnik
            price_lists = PriceListService.list_all()
            assert len(price_lists) == 1
            price_list = price_lists[0]

            # Proveri stavke
            items, total_count = PriceListService.get_items(price_list.id)
            assert len(items) == 3
            assert total_count == 3

            # Proveri da li su dobavljači dodeljeni
            item1 = next(i for i in items if i.supplier_code == "PRD001")
            item2 = next(i for i in items if i.supplier_code == "PRD002")
            item3 = next(i for i in items if i.supplier_code == "PRD003")

            assert item1.supplier == "Dobavljač 1"
            assert item2.supplier == "Dobavljač 1"
            assert item3.supplier == "Dobavljač 2"

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_delete_existing_price_list(self, db):
        """Brisanje postojećeg cjenovnika."""
        # Kreiraj cjenovnik sa stavkama
        price_list = PriceList(name="Test za brisanje", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        # Kreiraj stavke
        for i in range(3):
            item = PriceListItem(
                price_list_id=price_list.id,
                row_number=i,
                name=f"Proizvod {i}",
                regular_price=Decimal("100.00"),
            )
            db.add(item)
        db.commit()

        # Proveri da li postoji pre brisanja
        saved_price_list = db.get(PriceList, price_list.id)
        assert saved_price_list is not None

        # Obriši
        PriceListService.delete(price_list.id)

        # Proveri da li je obrisan - moramo koristiti novu sesiju
        # jer db fixture koristi istu sesiju koja je već commit-ovala
        from app.database.database import session_scope
        with session_scope() as new_session:
            saved_price_list = new_session.get(PriceList, price_list.id)
            assert saved_price_list is None

            # Proveri da li su stavke takođe obrisane (cascade)
            from sqlalchemy import select
            items = new_session.execute(
                select(PriceListItem).where(PriceListItem.price_list_id == price_list.id)
            ).scalars().all()
            assert len(items) == 0

    def test_delete_nonexistent_price_list(self, db):
        """Brisanje nepostojećeg cjenovnika."""
        with pytest.raises(ValueError, match="Cjenovnik ID=999 ne postoji."):
            PriceListService.delete(999)

    def test_import_from_excel_empty_rows(self, db):
        """Import iz Excel fajla sa praznim redovima."""
        # Kreiraj testni Excel fajl sa praznim redovima
        test_data = pd.DataFrame({
            'Šifra': ['PRD001', None, 'PRD002', '', 'PRD003'],
            'Naziv': ['Proizvod 1', None, 'Proizvod 2', '', 'Proizvod 3'],
            'Cijena': [100.0, None, 200.0, None, 300.0],
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            imported, skipped = PriceListService.import_from_excel(
                name="Test sa praznim redovima",
                excel_path=tmp_path,
            )

            # Očekujemo 3 proizvoda (prazni redovi se preskaču)
            assert imported == 3
            assert skipped == 0

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_from_excel_with_special_characters(self, db):
        """Import iz Excel fajla sa specijalnim karakterima."""
        # Kreiraj testni Excel fajl sa specijalnim karakterima
        test_data = pd.DataFrame({
            'Šifra': ['PRD-001', 'PRD/002', 'PRD 003'],
            'Naziv': ['Proizvod & Komplet', 'Proizvod "Premium"', 'Proizvod (2024)'],
            'Brend': ['Brend & Co.', 'Brend "Elite"', 'Brend (Pro)'],
            'Cijena': [100.50, 200.75, 300.25],
            'Akcija': [90.45, 180.68, 270.23],
            'Bodovi': [10, 20, 30]
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            imported, skipped = PriceListService.import_from_excel(
                name="Test sa specijalnim karakterima",
                excel_path=tmp_path,
            )

            assert imported == 3
            assert skipped == 0

            # Proveri cjenovnik
            price_lists = PriceListService.list_all()
            assert len(price_lists) == 1
            price_list = price_lists[0]

            # Proveri stavke
            items, total_count = PriceListService.get_items(price_list.id)
            assert len(items) == 3
            assert total_count == 3

            # Proveri da li su specijalni karakteri očuvani
            item1 = next(i for i in items if i.supplier_code == "PRD-001")
            assert item1.name == 'Proizvod & Komplet'
            assert item1.brand == 'Brend & Co.'
            assert item1.regular_price == Decimal("100.50")
            assert item1.discount_price == Decimal("90.45")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_update_price_list_success(self, db):
        """Ažuriranje naziva cjenovnika."""
        # Kreiraj cjenovnik
        price_list = PriceList(name="Originalni naziv", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        # Ažuriraj naziv
        PriceListService.update_price_list(price_list.id, "Novi naziv")

        # Proveri izmenu
        from app.database.database import session_scope
        with session_scope() as session:
            updated = session.get(PriceList, price_list.id)
            assert updated.name == "Novi naziv"

    def test_update_price_list_empty_name(self, db):
        """Ažuriranje cjenovnika sa praznim nazivom."""
        price_list = PriceList(name="Test", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        with pytest.raises(ValueError, match="Naziv cjenovnika je obavezan."):
            PriceListService.update_price_list(price_list.id, "")

    def test_update_price_list_name_too_long(self, db):
        """Ažuriranje cjenovnika sa predugačkim nazivom."""
        price_list = PriceList(name="Test", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        long_name = "A" * 201
        with pytest.raises(ValueError, match="Naziv cjenovnika ne smije biti duži od 200 karaktera."):
            PriceListService.update_price_list(price_list.id, long_name)

    def test_update_price_list_duplicate_name(self, db):
        """Ažuriranje cjenovnika sa nazivom koji već postoji."""
        # Kreiraj dva cjenovnika
        price_list1 = PriceList(name="Cjenovnik 1", source_filename="test1.xlsx")
        price_list2 = PriceList(name="Cjenovnik 2", source_filename="test2.xlsx")
        db.add_all([price_list1, price_list2])
        db.commit()

        with pytest.raises(ValueError, match="Cjenovnik sa nazivom 'Cjenovnik 1' već postoji."):
            PriceListService.update_price_list(price_list2.id, "Cjenovnik 1")

    def test_update_price_list_not_exists(self, db):
        """Ažuriranje nepostojećeg cjenovnika."""
        with pytest.raises(ValueError, match="Cjenovnik ID=999 ne postoji."):
            PriceListService.update_price_list(999, "Novi naziv")

    def test_duplicate_price_list_success(self, db):
        """Dupliciranje cjenovnika sa svim stavkama."""
        # Kreiraj cjenovnik sa stavkama
        price_list = PriceList(name="Original", source_filename="original.xlsx")
        db.add(price_list)
        db.commit()

        # Dodaj stavke
        for i in range(3):
            item = PriceListItem(
                price_list_id=price_list.id,
                row_number=i,
                name=f"Proizvod {i}",
                supplier_code=f"CODE{i}",
                regular_price=Decimal(f"{100 + i * 50}.00"),
                supplier=f"Dobavljač {i % 2}"
            )
            db.add(item)
        db.commit()

        # Dupliciraj
        new_id = PriceListService.duplicate_price_list(price_list.id, "Kopija")

        # Proveri novi cjenovnik
        from app.database.database import session_scope
        with session_scope() as session:
            new_pl = session.get(PriceList, new_id)
            assert new_pl is not None
            assert new_pl.name == "Kopija"
            assert "Copy of original.xlsx" in (new_pl.source_filename or "")

            # Proveri stavke
            from sqlalchemy import select
            items = session.execute(
                select(PriceListItem)
                .where(PriceListItem.price_list_id == new_id)
                .order_by(PriceListItem.row_number)
            ).scalars().all()
            
            assert len(items) == 3
            for i, item in enumerate(items):
                assert item.name == f"Proizvod {i}"
                assert item.supplier_code == f"CODE{i}"
                assert item.regular_price == Decimal(f"{100 + i * 50}.00")
                assert item.supplier == f"Dobavljač {i % 2}"

    def test_duplicate_price_list_empty_name(self, db):
        """Dupliciranje cjenovnika sa praznim nazivom."""
        price_list = PriceList(name="Original", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        with pytest.raises(ValueError, match="Naziv novog cjenovnika je obavezan."):
            PriceListService.duplicate_price_list(price_list.id, "")

    def test_duplicate_price_list_duplicate_name(self, db):
        """Dupliciranje cjenovnika sa nazivom koji već postoji."""
        price_list1 = PriceList(name="Original", source_filename="test.xlsx")
        price_list2 = PriceList(name="Postojeći", source_filename="test2.xlsx")
        db.add_all([price_list1, price_list2])
        db.commit()

        with pytest.raises(ValueError, match="Cjenovnik sa nazivom 'Postojeći' već postoji."):
            PriceListService.duplicate_price_list(price_list1.id, "Postojeći")

    def test_duplicate_price_list_not_exists(self, db):
        """Dupliciranje nepostojećeg cjenovnika."""
        with pytest.raises(ValueError, match="Cjenovnik ID=999 ne postoji."):
            PriceListService.duplicate_price_list(999, "Kopija")

    def test_export_price_list_success(self, db, tmp_path):
        """Izvoženje cjenovnika u Excel fajl."""
        # Kreiraj cjenovnik sa stavkama
        price_list = PriceList(name="Test Export", source_filename="test.xlsx")
        db.add(price_list)
        db.commit()

        # Dodaj stavke
        for i in range(2):
            item = PriceListItem(
                price_list_id=price_list.id,
                row_number=i,
                name=f"Proizvod {i}",
                supplier_code=f"CODE{i}",
                supplier=f"Dobavljač {i}",
                brand=f"Brend {i}",
                regular_price=Decimal(f"{100 + i * 50}.00"),
                discount_price=Decimal(f"{90 + i * 45}.00") if i == 0 else None,
                points=i * 10,
                status="Aktuelno" if i == 0 else "Zastarelo"
            )
            db.add(item)
        db.commit()

        # Izvezi
        output_path = tmp_path / "export_test.xlsx"
        result_path = PriceListService.export_price_list(price_list.id, str(output_path))

        # Proveri da li je fajl kreiran
        assert result_path.exists()
        assert result_path.name == "export_test.xlsx"

        # Pročitaj i proveri sadržaj
        import pandas as pd
        df = pd.read_excel(result_path)
        
        # Proveri strukturu
        expected_columns = ["Rb.", "Firma", "Naziv artikla", "Šifra", "Brend", 
                           "Cijena (EUR)", "Akcijska cijena (EUR)", "Bod", "Status"]
        assert list(df.columns) == expected_columns
        
        # Proveri podatke
        assert len(df) == 3  # 2 stavke + summary red
        
        # Proveri prvu stavku
        assert df.iloc[0]["Rb."] == 1
        assert df.iloc[0]["Firma"] == "Dobavljač 0"
        assert df.iloc[0]["Naziv artikla"] == "Proizvod 0"
        assert df.iloc[0]["Šifra"] == "CODE0"
        assert df.iloc[0]["Brend"] == "Brend 0"
        assert df.iloc[0]["Cijena (EUR)"] == 100.0
        assert df.iloc[0]["Akcijska cijena (EUR)"] == 90.0
        assert df.iloc[0]["Bod"] == 0.0  # Pandas konvertuje u float
        assert df.iloc[0]["Status"] == "Aktuelno"
        
        # Proveri summary red
        assert df.iloc[2]["Firma"] == "UKUPNO"
        assert "Broj stavki: 2" in str(df.iloc[2]["Bod"])
        assert "Cenovnik: Test Export" in str(df.iloc[2]["Status"])

    def test_export_price_list_empty(self, db, tmp_path):
        """Izvoženje praznog cjenovnika."""
        price_list = PriceList(name="Prazan cenovnik", source_filename="empty.xlsx")
        db.add(price_list)
        db.commit()

        output_path = tmp_path / "empty_export.xlsx"
        result_path = PriceListService.export_price_list(price_list.id, str(output_path))

        assert result_path.exists()
        
        import pandas as pd
        df = pd.read_excel(result_path)
        
        # Proveri da li ima samo summary red
        assert len(df) == 1
        assert df.iloc[0]["Firma"] == "UKUPNO"
        assert "Broj stavki: 0" in str(df.iloc[0]["Bod"])
        assert "Cenovnik: Prazan cenovnik" in str(df.iloc[0]["Status"])

    def test_export_price_list_not_exists(self, db, tmp_path):
        """Izvoženje nepostojećeg cjenovnika."""
        output_path = tmp_path / "nonexistent.xlsx"
        
        with pytest.raises(ValueError, match="Cjenovnik ID=999 ne postoji."):
            PriceListService.export_price_list(999, str(output_path))