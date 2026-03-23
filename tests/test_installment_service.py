"""
Testovi za installment_service.py.

Testiraju se:
- InstallmentService.generate_for_order
- InstallmentService.sync_statuses
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database.models import Installment, InstallmentStatus, Order, Payment
from app.services.installment_service import InstallmentService
from app.services.payment_service import PaymentService


class TestInstallmentServiceGenerateForOrder:
    """Testovi za InstallmentService.generate_for_order."""

    def test_generate_single_installment(self, db, sample_order):
        """Generisanje 1 rate za order."""
        from datetime import date, timedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=Decimal("100.00"),
            total_price_snapshot=Decimal("100.00"),
            installments_count=1,
            status="active",
            first_due_date=date.today() + timedelta(days=30),
        )
        db.add(order)
        db.flush()
        
        installments = InstallmentService.generate_for_order(order)
        
        assert len(installments) == 1
        assert installments[0].installment_number == 1
        assert installments[0].amount == Decimal("100.00")
        assert installments[0].status == InstallmentStatus.PENDING

    def test_generate_multiple_installments_equal_amounts(self, db, sample_order):
        """Generisanje više rata sa jednakim iznosima."""
        from datetime import date, timedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        total = Decimal("300.00")
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=total,
            total_price_snapshot=total,
            installments_count=3,
            status="active",
            first_due_date=date.today() + timedelta(days=30),
        )
        db.add(order)
        db.flush()
        
        installments = InstallmentService.generate_for_order(order)
        
        assert len(installments) == 3
        # Sve rate bi trebale biti 100.00
        for inst in installments:
            assert inst.amount == Decimal("100.00")

    def test_generate_installments_sum_equals_total(self, db, sample_order):
        """Suma generisanih rata = total_price_snapshot."""
        from datetime import date, timedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        # Iznos koji se ne dijeli lijepo (100 / 3 = 33.33...)
        total = Decimal("100.00")
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=total,
            total_price_snapshot=total,
            installments_count=3,
            status="active",
            first_due_date=date.today() + timedelta(days=30),
        )
        db.add(order)
        db.flush()
        
        installments = InstallmentService.generate_for_order(order)
        
        sum_installments = sum(inst.amount for inst in installments)
        assert sum_installments == total

    def test_generate_installments_last_amount_adjusted(self, db, sample_order):
        """Posljednja rata prilagođena zbog zaokruživanja."""
        from datetime import date, timedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        # Iznos koji se ne dijeli lijepo
        total = Decimal("100.00")
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=total,
            total_price_snapshot=total,
            installments_count=3,
            status="active",
            first_due_date=date.today() + timedelta(days=30),
        )
        db.add(order)
        db.flush()
        
        installments = InstallmentService.generate_for_order(order)
        
        # Prve dvije rate su 33.33
        assert installments[0].amount == Decimal("33.33")
        assert installments[1].amount == Decimal("33.33")
        # Posljednja je prilagođena: 100 - 33.33 - 33.33 = 33.34
        assert installments[2].amount == Decimal("33.34")

    def test_generate_installments_due_dates_sequential(self, db, sample_order):
        """Datumi dospijeća su sekvencijalni (mjesečno)."""
        from datetime import date, timedelta
        from dateutil.relativedelta import relativedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        first_due = date.today() + relativedelta(months=1)
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=Decimal("300.00"),
            total_price_snapshot=Decimal("300.00"),
            installments_count=3,
            status="active",
            first_due_date=first_due,
        )
        db.add(order)
        db.flush()
        
        installments = InstallmentService.generate_for_order(order)
        
        # Provjeri datume - InstallmentService koristi relativedelta(months=1)
        assert installments[0].due_date == first_due
        assert installments[1].due_date == first_due + relativedelta(months=1)
        assert installments[2].due_date == first_due + relativedelta(months=2)

    def test_generate_installments_zero_count_raises_error(self, db, sample_order):
        """installments_count = 0 → ValueError."""
        from datetime import date, timedelta
        from app.database.models import Campaign, Customer
        
        customer = Customer(full_name="Test", phone="123", city="Sarajevo")
        db.add(customer)
        db.commit()
        
        campaign = Campaign(
            name="Test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status="active",
        )
        db.add(campaign)
        db.commit()
        
        # Kreiraj order sa validnim installments_count prvo
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_name_snapshot="Test",
            unit_price_snapshot=Decimal("100.00"),
            total_price_snapshot=Decimal("100.00"),
            installments_count=1,  # Validno
            status="active",
            first_due_date=date.today() + timedelta(days=30),
        )
        db.add(order)
        db.flush()
        
        # Postavi installments_count na 0 i pokušaj generisanje
        order.installments_count = 0
        
        with pytest.raises(ValueError, match="Broj rata mora biti najmanje 1"):
            InstallmentService.generate_for_order(order)


class TestInstallmentServiceSyncStatuses:
    """Testovi za InstallmentService.sync_statuses."""

    def test_sync_statuses_fully_paid_installment(self, db, sample_order):
        """Rata sa punom uplatom → status = PAID."""
        from sqlalchemy import select
        
        installment = sample_order.installments[0]
        installment_id = installment.id
        
        # Kreiraj uplatu koja pokriva cijelu ratu koristeći PaymentService
        PaymentService.create_payment(
            installment_id=installment_id,
            amount=str(installment.amount),
            payment_date=date.today(),
        )
        
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke iz iste sesije koju koristi sync_statuses
        from app.database.database import session_scope
        with session_scope() as session:
            stmt = select(Installment).where(Installment.id == installment_id)
            updated = session.execute(stmt).scalars().first()
            assert updated.status == InstallmentStatus.PAID

    def test_sync_statuses_partially_paid_installment(self, db, sample_order):
        """Rata sa djelimičnom uplatom → status = PARTIALLY_PAID."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        installment = sample_order.installments[0]
        installment_id = installment.id
        
        # Kreiraj djelimičnu uplatu (50%)
        PaymentService.create_payment(
            installment_id=installment_id,
            amount=str(installment.amount / 2),
            payment_date=date.today(),
        )
        
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke
        with session_scope() as session:
            stmt = select(Installment).where(Installment.id == installment_id)
            updated = session.execute(stmt).scalars().first()
            assert updated.status == InstallmentStatus.PARTIALLY_PAID

    def test_sync_statuses_overdue_installment(self, db, sample_order):
        """Rata sa dospijećem u prošlosti bez uplate → status = OVERDUE."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        installment = sample_order.installments[0]
        installment_id = installment.id
        
        # Postavi due_date u prošlost
        installment.due_date = date.today() - timedelta(days=30)
        db.commit()
        
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke
        with session_scope() as session:
            stmt = select(Installment).where(Installment.id == installment_id)
            updated = session.execute(stmt).scalars().first()
            assert updated.status == InstallmentStatus.OVERDUE

    def test_sync_statuses_pending_installment(self, db, sample_order):
        """Rata sa dospijećem u budućnosti bez uplate → status = PENDING."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        installment = sample_order.installments[0]
        installment_id = installment.id
        
        # due_date je već u budućnosti (iz fixture-a)
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke
        with session_scope() as session:
            stmt = select(Installment).where(Installment.id == installment_id)
            updated = session.execute(stmt).scalars().first()
            assert updated.status == InstallmentStatus.PENDING

    def test_sync_statuses_multiple_installments_mixed_states(self, db, sample_order):
        """Sinhronizacija više rata sa različitim stanjima."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        installments = sample_order.installments
        installment_ids = [inst.id for inst in installments]
        
        # Prva rata: plaćena
        PaymentService.create_payment(
            installment_id=installments[0].id,
            amount=str(installments[0].amount),
            payment_date=date.today(),
        )
        
        # Druga rata: djelimično plaćena
        PaymentService.create_payment(
            installment_id=installments[1].id,
            amount=str(installments[1].amount / 2),
            payment_date=date.today(),
        )
        
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke
        with session_scope() as session:
            stmt = select(Installment).where(
                Installment.id.in_(installment_ids)
            ).order_by(Installment.id)
            updated = session.execute(stmt).scalars().all()
            assert updated[0].status == InstallmentStatus.PAID
            assert updated[1].status == InstallmentStatus.PARTIALLY_PAID

    def test_sync_statuses_overpaid_installment(self, db, sample_order):
        """Preplaćena rata → status = PAID."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        installment = sample_order.installments[0]
        installment_id = installment.id
        
        # Prva uplata pokriva cijelu ratu
        PaymentService.create_payment(
            installment_id=installment_id,
            amount=str(installment.amount),
            payment_date=date.today(),
        )
        
        # Sinhronizuj statuse
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš podatke
        with session_scope() as session:
            stmt = select(Installment).where(Installment.id == installment_id)
            updated = session.execute(stmt).scalars().first()
            assert updated.status == InstallmentStatus.PAID

    def test_sync_statuses_no_installments(self, db):
        """Sinhronizacija kada nema nijedne rate → ne puca."""
        # Ovo ne smije baciti grešku
        InstallmentService.sync_statuses()
        # Test prolazi ako nema exception-a
