"""
Testovi za customer_service.py.

Testiraju se:
- CustomerService.get_customer
- CustomerService.list_customers
- CustomerService.create_customer
- CustomerService.update_customer
- CustomerService.delete_customer
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database.models import Customer
from app.services.customer_service import CustomerService


class TestCustomerService:
    """Testovi za CustomerService."""

    def test_get_customer_exists(self, db, sample_customer):
        """Dohvatanje postojećeg kupca."""
        customer_dto = CustomerService.get_customer(sample_customer.id)
        
        assert customer_dto is not None
        assert customer_dto.id == sample_customer.id
        assert customer_dto.full_name == sample_customer.full_name
        assert customer_dto.phone == sample_customer.phone
        assert customer_dto.city == sample_customer.city

    def test_get_customer_not_exists(self, db):
        """Dohvatanje nepostojećeg kupca."""
        customer_dto = CustomerService.get_customer(99999)
        assert customer_dto is None

    def test_list_customers_empty(self, db):
        """Lista kupaca kada nema kupaca."""
        customers = CustomerService.list_customers()
        assert customers == []

    def test_list_customers_with_data(self, db):
        """Lista kupaca sa podacima."""
        # Kreiraj nekoliko kupaca
        customers_data = [
            ("Ana Anić", "061111111", "Sarajevo"),
            ("Boris Borić", "062222222", "Mostar"),
            ("Cvita Cvitić", "063333333", "Zenica"),
        ]
        
        for name, phone, city in customers_data:
            customer = Customer(
                full_name=name,
                phone=phone,
                city=city,
                is_active=True,
            )
            db.add(customer)
        db.commit()
        
        customers = CustomerService.list_customers()
        
        assert len(customers) == 3
        # Proveri da li su sortirani po imenu
        assert customers[0].full_name == "Ana Anić"
        assert customers[1].full_name == "Boris Borić"
        assert customers[2].full_name == "Cvita Cvitić"

    def test_list_customers_search(self, db):
        """Pretraga kupaca."""
        customers_data = [
            ("Ana Anić", "061111111", "Sarajevo"),
            ("Boris Borić", "062222222", "Mostar"),
            ("Cvita Cvitić", "063333333", "Zenica"),
        ]
        
        for name, phone, city in customers_data:
            customer = Customer(
                full_name=name,
                phone=phone,
                city=city,
                is_active=True,
            )
            db.add(customer)
        db.commit()
        
        # Pretraga po imenu
        customers = CustomerService.list_customers("Ana")
        assert len(customers) == 1
        assert customers[0].full_name == "Ana Anić"
        
        # Pretraga po telefonu
        customers = CustomerService.list_customers("062")
        assert len(customers) == 1
        assert customers[0].full_name == "Boris Borić"
        
        # Pretraga po gradu
        customers = CustomerService.list_customers("Mostar")
        assert len(customers) == 1
        assert customers[0].full_name == "Boris Borić"

    def test_create_customer_success(self, db):
        """Kreiranje novog kupca."""
        customer_dto = CustomerService.create_customer(
            full_name="Test Kupac",
            phone="061123456",
            city="Sarajevo",
            address="Testna 1",
            note="Test napomena",
        )
        
        assert customer_dto.id is not None
        assert customer_dto.full_name == "Test Kupac"
        assert customer_dto.phone == "061123456"
        assert customer_dto.city == "Sarajevo"
        assert customer_dto.address == "Testna 1"
        assert customer_dto.note == "Test napomena"
        assert customer_dto.is_active is True
        
        # Proveri da li je stvarno sačuvan u bazi
        customer = db.get(Customer, customer_dto.id)
        assert customer is not None
        assert customer.full_name == "Test Kupac"

    def test_create_customer_empty_name(self, db):
        """Kreiranje kupca bez imena."""
        with pytest.raises(ValueError, match="Ime i prezime je obavezno."):
            CustomerService.create_customer(full_name="")

    def test_create_customer_whitespace_name(self, db):
        """Kreiranje kupca sa samo whitespace u imenu."""
        with pytest.raises(ValueError, match="Ime i prezime je obavezno."):
            CustomerService.create_customer(full_name="   ")

    def test_create_customer_optional_fields(self, db):
        """Kreiranje kupca sa opcionim poljima."""
        customer_dto = CustomerService.create_customer(
            full_name="Test Kupac",
            phone="",  # prazno
            city="",   # prazno
        )
        
        assert customer_dto.full_name == "Test Kupac"
        assert customer_dto.phone is None  # prazni stringovi se konvertuju u None
        assert customer_dto.city is None
        assert customer_dto.address is None
        assert customer_dto.note is None

    def test_update_customer_success(self, db, sample_customer):
        """Ažuriranje postojećeg kupca."""
        customer_dto = CustomerService.update_customer(
            customer_id=sample_customer.id,
            full_name="Ažurirano Ime",
            phone="064444444",
            city="Banja Luka",
            address="Nova adresa",
            note="Nova napomena",
        )
        
        assert customer_dto.id == sample_customer.id
        assert customer_dto.full_name == "Ažurirano Ime"
        assert customer_dto.phone == "064444444"
        assert customer_dto.city == "Banja Luka"
        assert customer_dto.address == "Nova adresa"
        assert customer_dto.note == "Nova napomena"
        
        # Proveri da li je stvarno ažuriran u bazi
        db.refresh(sample_customer)
        assert sample_customer.full_name == "Ažurirano Ime"

    def test_update_customer_not_exists(self, db):
        """Ažuriranje nepostojećeg kupca."""
        with pytest.raises(ValueError, match="Kupac nije pronađen."):
            CustomerService.update_customer(
                customer_id=99999,
                full_name="Test",
            )

    def test_update_customer_empty_name(self, db, sample_customer):
        """Ažuriranje kupca sa praznim imenom."""
        with pytest.raises(ValueError, match="Ime i prezime je obavezno."):
            CustomerService.update_customer(
                customer_id=sample_customer.id,
                full_name="",
            )

    def test_delete_customer_success(self, db, sample_customer):
        """Brisanje kupca (hard delete)."""
        # Sačuvaj ID pre brisanja
        customer_id = sample_customer.id
        
        # Metoda vraća None ako je uspešno
        CustomerService.delete_customer(customer_id)
        
        # Proveri da li je kupac zaista obrisan
        db.expire_all()
        deleted_customer = db.get(Customer, customer_id)
        assert deleted_customer is None
        
        # Proveri da li se ne pojavljuje u listi
        customers = CustomerService.list_customers()
        customer_ids = [c.id for c in customers]
        assert customer_id not in customer_ids

    def test_delete_customer_not_exists(self, db):
        """Brisanje nepostojećeg kupca."""
        with pytest.raises(ValueError, match="Kupac nije pronađen."):
            CustomerService.delete_customer(99999)

    def test_delete_already_deleted_customer(self, db, sample_customer):
        """Brisanje već obrisanog kupca."""
        # Prvo obriši kupca
        CustomerService.delete_customer(sample_customer.id)
        db.commit()
        
        # Pokušaj ponovo da obrišeš - treba da baci grešku jer kupac više ne postoji
        with pytest.raises(ValueError, match="Kupac nije pronađen."):
            CustomerService.delete_customer(sample_customer.id)

    def test_customer_dto_structure(self, db, sample_customer):
        """Provera strukture CustomerDTO."""
        customer_dto = CustomerService.get_customer(sample_customer.id)
        
        # Proveri da li DTO ima sva očekivana polja
        assert hasattr(customer_dto, 'id')
        assert hasattr(customer_dto, 'full_name')
        assert hasattr(customer_dto, 'phone')
        assert hasattr(customer_dto, 'city')
        assert hasattr(customer_dto, 'address')
        assert hasattr(customer_dto, 'note')
        assert hasattr(customer_dto, 'is_active')
        
        # Proveri tipove
        assert isinstance(customer_dto.id, int)
        assert isinstance(customer_dto.full_name, str)
        assert isinstance(customer_dto.is_active, bool)