"""
Testovi za order_service.py.

Testiraju se:
- OrderService.validate_order_input
- OrderService.create_order
- OrderService.delete_order
- OrderService.get_order_details
- OrderService.list_orders
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.database.models import Campaign, CampaignStatus, Customer, Installment, Order, OrderStatus, Payment
from app.services.order_service import OrderService
from app.services.installment_service import InstallmentService


class TestOrderServiceValidateOrderInput:
    """Testovi za OrderService.validate_order_input."""

    def test_valid_input(self):
        """Validan unos → (True, '')."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="199.99",
            installments=5,
        )
        
        assert success is True
        assert error == ""

    def test_missing_customer_id(self):
        """customer_id = None → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=None,
            product_name="Test Proizvod",
            price="199.99",
            installments=5,
        )
        
        assert success is False
        assert "Obavezno odabrati kupca" in error

    def test_empty_product_name(self):
        """Prazno ime proizvoda → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="",
            price="199.99",
            installments=5,
        )
        
        assert success is False
        assert "Obavezno unijeti naziv proizvoda" in error

    def test_whitespace_product_name(self):
        """Samo razmaci u imenu proizvoda → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="   ",
            price="199.99",
            installments=5,
        )
        
        assert success is False
        assert "Obavezno unijeti naziv proizvoda" in error

    def test_price_zero(self):
        """Cijena = 0 → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="0",
            installments=5,
        )
        
        assert success is False
        assert "Cijena mora biti veća od 0" in error

    def test_price_negative(self):
        """Negativna cijena → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="-50",
            installments=5,
        )
        
        assert success is False
        assert "Cijena mora biti veća od 0" in error

    def test_price_invalid_format(self):
        """Nevalidan format cijene → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="abc",
            installments=5,
        )
        
        assert success is False
        assert "Neispravna cijena" in error

    def test_installments_zero(self):
        """Broj rata = 0 → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="100",
            installments=0,
        )
        
        assert success is False
        assert "Broj rata mora biti između 1 i 10" in error

    def test_installments_greater_than_10(self):
        """Broj rata > 10 → ValueError."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="100",
            installments=11,
        )
        
        assert success is False
        assert "Broj rata mora biti između 1 i 10" in error

    def test_price_with_comma(self):
        """Cijena sa zarezom (199,99) → validno."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="199,99",
            installments=5,
        )
        
        assert success is True
        assert error == ""

    def test_installments_boundary_1(self):
        """Broj rata = 1 (donja granica) → validno."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="100",
            installments=1,
        )
        
        assert success is True

    def test_installments_boundary_10(self):
        """Broj rata = 10 (gornja granica) → validno."""
        success, error = OrderService.validate_order_input(
            customer_id=1,
            product_name="Test Proizvod",
            price="100",
            installments=10,
        )
        
        assert success is True


class TestOrderServiceCreateOrder:
    """Testovi za OrderService.create_order."""

    def test_create_order_success(self, db, sample_customer, sample_campaign):
        """Uspješno kreiranje narudžbe."""
        order = OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Test Proizvod",
            price="100.00",
            installments=3,
            campaign_id=sample_campaign.id,
        )
        
        assert order is not None
        assert order.customer_id == sample_customer.id
        assert order.campaign_id == sample_campaign.id
        assert order.product_name_snapshot == "Test Proizvod"
        assert order.total_price_snapshot == Decimal("100.00")
        assert order.installments_count == 3
        assert order.status == OrderStatus.ACTIVE

    def test_create_order_generates_correct_number_of_installments(self, db, sample_customer, sample_campaign):
        """Broj kreiranih rata odgovara installments_count."""
        from sqlalchemy import select
        
        order = OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Test Proizvod",
            price="300.00",
            installments=5,
            campaign_id=sample_campaign.id,
        )
        
        # Provjeri broj rata u bazi - koristi order.id iz kreiranog order-a
        stmt = select(Installment).where(Installment.order_id == order.id)
        installments = db.execute(stmt).scalars().all()
        
        assert len(installments) == 5
        for i, inst in enumerate(installments, 1):
            assert inst.installment_number == i

    def test_create_order_sum_of_installments_equals_total(self, db, sample_customer, sample_campaign):
        """Suma iznosa rata = total_price_snapshot."""
        from sqlalchemy import select
        
        total = Decimal("299.99")
        
        order = OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Test Proizvod",
            price=str(total),
            installments=3,
            campaign_id=sample_campaign.id,
        )
        
        stmt = select(Installment).where(Installment.order_id == order.id)
        installments = db.execute(stmt).scalars().all()
        
        sum_installments = sum(inst.amount for inst in installments)
        assert sum_installments == total

    def test_create_order_validation_empty_product_name(self, db, sample_customer, sample_campaign):
        """Prazno ime proizvoda → ValueError."""
        with pytest.raises(ValueError, match="Obavezno unijeti naziv proizvoda"):
            OrderService.create_order(
                customer_id=sample_customer.id,
                product_name="",
                price="100",
                installments=3,
                campaign_id=sample_campaign.id,
            )

    def test_create_order_validation_price_zero(self, db, sample_customer, sample_campaign):
        """Cijena = 0 → ValueError."""
        with pytest.raises(ValueError, match="Cijena mora biti veća od 0"):
            OrderService.create_order(
                customer_id=sample_customer.id,
                product_name="Test",
                price="0",
                installments=3,
                campaign_id=sample_campaign.id,
            )

    def test_create_order_validation_installments_out_of_range(self, db, sample_customer, sample_campaign):
        """Broj rata van opsega 1-10 → ValueError."""
        with pytest.raises(ValueError, match="Broj rata mora biti između 1 i 10"):
            OrderService.create_order(
                customer_id=sample_customer.id,
                product_name="Test",
                price="100",
                installments=15,
                campaign_id=sample_campaign.id,
            )

    def test_create_order_no_campaign_available(self, db, sample_customer):
        """Nema dostupne kampanje → ValueError."""
        # Ne kreiraj kampanju u bazi
        
        with pytest.raises(ValueError, match="Nema dostupne kampanje"):
            OrderService.create_order(
                customer_id=sample_customer.id,
                product_name="Test Proizvod",
                price="100",
                installments=3,
                campaign_id=None,  # Nema campaign_id
            )

    def test_create_order_with_contract_number(self, db, sample_customer, sample_campaign):
        """Kreiranje narudžbe sa brojem ugovora."""
        contract_number = "4-1-11-2-1-3-001"
        
        order = OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Test Proizvod",
            price="100.00",
            installments=3,
            campaign_id=sample_campaign.id,
            contract_number=contract_number,
        )
        
        assert order.contract_number == contract_number

    def test_create_order_installment_dates_sequential(self, db, sample_customer, sample_campaign):
        """Datumi dospijeća rata su sekvencijalni (mjesečno)."""
        from dateutil.relativedelta import relativedelta
        
        order = OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Test Proizvod",
            price="300.00",
            installments=3,
            campaign_id=sample_campaign.id,
        )
        
        installments = db.query(Installment).filter(
            Installment.order_id == order.id
        ).all()
        
        # Provjeri da su datumi sekvencijalni
        for i in range(1, len(installments)):
            expected_date = installments[i-1].due_date + relativedelta(months=1)
            assert installments[i].due_date == expected_date


class TestOrderServiceDeleteOrder:
    """Testovi za OrderService.delete_order."""

    def test_delete_order_success(self, db, sample_order):
        """Uspješno brisanje narudžbe."""
        from sqlalchemy import select
        
        order_id = sample_order.id
        
        # Provjeri da postoje rate
        stmt = select(Installment).where(Installment.order_id == order_id)
        installments_before = db.execute(stmt).scalars().all()
        assert len(installments_before) > 0
        
        # Obriši narudžbu
        result = OrderService.delete_order(order_id)
        
        assert result is True
        
        # Provjeri da je narudžba obrisana
        order_stmt = select(Order).where(Order.id == order_id)
        deleted_order = db.execute(order_stmt).scalars().first()
        assert deleted_order is None
        
        # Provjeri da su rate obrisane
        inst_stmt = select(Installment).where(Installment.order_id == order_id)
        installments_after = db.execute(inst_stmt).scalars().all()
        assert len(installments_after) == 0

    def test_delete_order_nonexistent(self, db):
        """Brisanje nepostojeće narudžbe → ValueError."""
        with pytest.raises(ValueError, match="nije pronađena"):
            OrderService.delete_order(99999)

    def test_delete_order_with_payments(self, db, sample_order):
        """Brisanje narudžbe koja ima uplate."""
        from sqlalchemy import select
        
        # Kreiraj uplatu na prvu ratu
        installment = sample_order.installments[0]
        payment = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=Decimal("50.00"),
        )
        db.add(payment)
        db.commit()
        
        order_id = sample_order.id
        
        # Obriši narudžbu
        result = OrderService.delete_order(order_id)
        
        assert result is True
        
        # Provjeri da je uplata obrisana
        payment_stmt = select(Payment).where(Payment.id == payment.id)
        deleted_payment = db.execute(payment_stmt).scalars().first()
        assert deleted_payment is None


class TestOrderServiceGetOrderDetails:
    """Testovi za OrderService.get_order_details."""

    def test_get_existing_order(self, db, sample_order):
        """Dohvatanje postojeće narudžbe kao OrderDTO."""
        order = OrderService.get_order_details(sample_order.id)
        
        assert order is not None
        assert order.id == sample_order.id
        assert order.customer_name is not None  # DTO ima customer_name umjesto customer
        assert len(order.installments) == len(sample_order.installments)

    def test_get_nonexistent_order(self, db):
        """Dohvatanje nepostojeće narudžbe → None."""
        order = OrderService.get_order_details(99999)
        
        assert order is None


class TestOrderServiceListOrders:
    """Testovi za OrderService.list_orders."""

    def test_list_orders_all(self, db, sample_customer, sample_campaign):
        """Lista svih narudžbi."""
        # Kreiraj 3 narudžbe
        for i in range(3):
            OrderService.create_order(
                customer_id=sample_customer.id,
                product_name=f"Proizvod {i}",
                price="100.00",
                installments=2,
                campaign_id=sample_campaign.id,
            )
        
        orders = OrderService.list_orders()
        
        assert len(orders) == 3

    def test_list_orders_filtered_by_customer(self, db, sample_customer, sample_campaign):
        """Filtriranje narudžbi po kupcu."""
        # Kreiraj drugog kupca
        customer2 = Customer(
            full_name="Drugi Kupac",
            phone="062234567",
            city="Banja Luka",
        )
        db.add(customer2)
        db.commit()
        
        # Kreiraj narudžbe za oba kupca
        OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Proizvod 1",
            price="100.00",
            installments=2,
            campaign_id=sample_campaign.id,
        )
        OrderService.create_order(
            customer_id=customer2.id,
            product_name="Proizvod 2",
            price="150.00",
            installments=3,
            campaign_id=sample_campaign.id,
        )
        
        # Filtriraj po prvom kupcu
        orders = OrderService.list_orders(customer_filter=sample_customer.id)
        
        assert len(orders) == 1
        assert orders[0].customer_id == sample_customer.id

    def test_list_orders_empty(self, db):
        """Lista prazna kada nema narudžbi."""
        orders = OrderService.list_orders()
        
        assert len(orders) == 0


class TestOrderServiceGetOrdersForCustomer:
    """Testovi za OrderService.get_orders_for_customer."""

    def test_get_orders_for_customer_with_orders(self, db, sample_customer, sample_campaign):
        """Dohvatanje narudžbi za kupca koji ima narudžbe."""
        # Kreiraj 2 narudžbe
        OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Proizvod 1",
            price="100.00",
            installments=2,
            campaign_id=sample_campaign.id,
        )
        OrderService.create_order(
            customer_id=sample_customer.id,
            product_name="Proizvod 2",
            price="200.00",
            installments=3,
            campaign_id=sample_campaign.id,
        )
        
        orders = OrderService.get_orders_for_customer(sample_customer.id)
        
        assert len(orders) == 2
        # Provjeri da su učitane rate i uplate
        for order in orders:
            assert order.installments is not None

    def test_get_orders_for_customer_no_orders(self, db, sample_customer):
        """Dohvatanje narudžbi za kupca bez narudžbi."""
        orders = OrderService.get_orders_for_customer(sample_customer.id)
        
        assert len(orders) == 0


class TestOrderServiceUpdateContractNumber:
    """Testovi za OrderService.update_contract_number."""

    def test_update_contract_number_success(self, db, sample_order):
        """Ažuriranje broja ugovora."""
        new_contract = "NEW-123-456"
        
        OrderService.update_contract_number(sample_order.id, new_contract)
        
        updated_order = OrderService.get_order_details(sample_order.id)
        assert updated_order.contract_number == new_contract

    def test_update_contract_number_set_none(self, db, sample_order):
        """Postavljanje broja ugovora na None."""
        # Prvo postavi broj ugovora
        OrderService.update_contract_number(sample_order.id, "TEST-123")
        
        # Zatim ga obriši
        OrderService.update_contract_number(sample_order.id, None)
        
        updated_order = OrderService.get_order_details(sample_order.id)
        assert updated_order.contract_number is None
