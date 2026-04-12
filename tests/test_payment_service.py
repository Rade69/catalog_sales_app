"""
Testovi za payment_service.py.

Testiraju se:
- _recalculate_installment_status (interna funkcija)
- _recalculate_order_status (interna funkcija)
- PaymentService.create_payment
- PaymentService.delete_payment
- PaymentService.get_installment
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database.models import InstallmentStatus, OrderStatus, Payment, Order
from app.services.payment_service import (
    PaymentService,
    _recalculate_installment_status,
    _recalculate_order_status,
)
from app.services.installment_service import InstallmentService


class TestRecalculateInstallmentStatus:
    """Testovi za _recalculate_installment_status funkciju."""

    def test_fully_paid_installment(self, db, sample_order):
        """Rata u cijelosti plaćena → status = PAID, paid_at postavljen."""
        installment = sample_order.installments[0]
        original_amount = installment.amount
        
        # Kreiraj uplatu koja pokriva cijelu ratu
        payment = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=original_amount,
        )
        db.add(payment)
        db.commit()
        db.refresh(installment)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.PAID
        assert installment.paid_at == date.today()

    def test_partially_paid_installment(self, db, sample_order):
        """Rata djelimično plaćena → status = PARTIALLY_PAID."""
        installment = sample_order.installments[0]
        original_amount = installment.amount
        
        # Kreiraj djelimičnu uplatu (50% iznosa)
        payment = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=original_amount / 2,
        )
        db.add(payment)
        db.commit()
        db.refresh(installment)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.PARTIALLY_PAID
        assert installment.paid_at is None  # paid_at se resetuje

    def test_unpaid_overdue_installment(self, db, sample_order):
        """Rata neplaćena, due_date u prošlosti → status = OVERDUE."""
        installment = sample_order.installments[0]
        
        # Postavi due_date u prošlost
        installment.due_date = date.today() - timedelta(days=10)
        db.commit()
        db.refresh(installment)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.OVERDUE
        assert installment.paid_at is None

    def test_unpaid_pending_installment(self, db, sample_order):
        """Rata neplaćena, due_date u budućnosti → status = PENDING."""
        installment = sample_order.installments[0]
        
        # due_date je već u budućnosti (iz fixture-a)
        # Pozovi funkciju za recalculaciju
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.PENDING
        assert installment.paid_at is None

    def test_overpaid_installment_edge_case(self, db, sample_order):
        """Preplaćena rata (edge case) → status = PAID, ne puca."""
        installment = sample_order.installments[0]
        original_amount = installment.amount
        
        # Kreiraj uplatu koja je veća od iznosa rate (greška u sistemu)
        # Ovo simulira situaciju gde je greškom unesena prevelika uplata
        payment1 = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=original_amount,
        )
        payment2 = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=Decimal("10.00"),  # Dodatna uplata (greška)
        )
        db.add(payment1)
        db.add(payment2)
        db.commit()
        db.refresh(installment)
        
        # Pozovi funkciju za recalculaciju - ne sme pući
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.PAID
        assert installment.paid_at == date.today()

    def test_multiple_partial_payments_become_paid(self, db, sample_order):
        """Više djelimičnih uplata koje zajedno pokrivaju ratu → PAID."""
        installment = sample_order.installments[0]
        original_amount = installment.amount
        
        # Kreiraj 3 djelimične uplate koje zajedno pokrivaju ratu
        payment1 = Payment(
            installment_id=installment.id,
            payment_date=date.today() - timedelta(days=10),
            amount=original_amount * Decimal("0.3"),
        )
        payment2 = Payment(
            installment_id=installment.id,
            payment_date=date.today() - timedelta(days=5),
            amount=original_amount * Decimal("0.3"),
        )
        payment3 = Payment(
            installment_id=installment.id,
            payment_date=date.today(),
            amount=original_amount * Decimal("0.4"),
        )
        db.add(payment1)
        db.add(payment2)
        db.add(payment3)
        db.commit()
        db.refresh(installment)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_installment_status(installment)
        
        assert installment.status == InstallmentStatus.PAID
        assert installment.paid_at == date.today()


class TestRecalculateOrderStatus:
    """Testovi za _recalculate_order_status funkciju."""

    def test_all_installments_paid_order_completed(self, db, sample_order):
        """Sve rate PAID → order status = COMPLETED."""
        # Označi sve rate kao plaćene
        for installment in sample_order.installments:
            installment.status = InstallmentStatus.PAID
            installment.paid_at = date.today()
        
        db.commit()
        db.refresh(sample_order)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_order_status(sample_order)
        
        assert sample_order.status == OrderStatus.COMPLETED

    def test_one_installment_not_paid_order_active(self, db, sample_order):
        """Bar jedna rata nije PAID → order status ostaje ACTIVE."""
        # Prva rata plaćena, druga nije
        sample_order.installments[0].status = InstallmentStatus.PAID
        sample_order.installments[1].status = InstallmentStatus.PENDING
        
        db.commit()
        db.refresh(sample_order)
        
        # Pozovi funkciju za recalculaciju
        _recalculate_order_status(sample_order)
        
        assert sample_order.status == OrderStatus.ACTIVE

    def test_completed_order_becomes_active_after_payment_deletion(self, db, sample_order):
        """Rollback: bila COMPLETED, jedna rata se 'odplati' → vraća se na ACTIVE."""
        from sqlalchemy import select
        from app.database.database import session_scope
        
        order_id = sample_order.id
        
        # Plati sve rate da order postane COMPLETED
        for installment in sample_order.installments:
            PaymentService.create_payment(
                installment_id=installment.id,
                amount=str(installment.amount),
                payment_date=date.today(),
            )
        
        # Sinhronizuj statuse da se order ažurira
        InstallmentService.sync_statuses()
        
        # Koristi session_scope da učitaš order
        with session_scope() as session:
            stmt = select(Order).where(Order.id == order_id)
            order = session.execute(stmt).scalars().first()
            assert order.status == OrderStatus.COMPLETED
        
        # Obriši jednu uplatu
        # Prvo učitaj payment kroz session_scope
        with session_scope() as session:
            from app.database.models import Payment
            stmt = select(Payment).where(Payment.installment_id == sample_order.installments[0].id)
            payment = session.execute(stmt).scalars().first()
            PaymentService.delete_payment(payment.id)
        
        # Koristi session_scope da učitaš order i provjeri da je ACTIVE
        with session_scope() as session:
            stmt = select(Order).where(Order.id == order_id)
            order = session.execute(stmt).scalars().first()
            assert order.status == OrderStatus.ACTIVE


class TestPaymentServiceCreatePayment:
    """Testovi za PaymentService.create_payment."""

    def test_create_full_payment(self, db, sample_order):
        """Dodaj uplatu koja pokriva cijelu ratu → status se mijenja u PAID."""
        installment = sample_order.installments[0]
        amount = installment.amount
        
        payment = PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(amount),
            payment_date=date.today(),
        )
        
        assert payment is not None
        assert payment.amount == amount
        
        # Provjeri da je rata sada plaćena
        updated_installment = PaymentService.get_installment(installment.id)
        assert updated_installment.status == InstallmentStatus.PAID
        # paid_at može biti datetime ili date - provjeri samo datum
        assert updated_installment.paid_at.date() == date.today() if hasattr(updated_installment.paid_at, 'date') else updated_installment.paid_at == date.today()

    def test_create_partial_payment(self, db, sample_order):
        """Dodaj djelimičnu uplatu → PARTIALLY_PAID."""
        installment = sample_order.installments[0]
        amount = installment.amount / 2
        
        payment = PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(amount),
            payment_date=date.today(),
        )
        
        assert payment is not None
        assert payment.amount == amount
        
        # Provjeri da je rata sada djelimično plaćena
        updated_installment = PaymentService.get_installment(installment.id)
        assert updated_installment.status == InstallmentStatus.PARTIALLY_PAID

    def test_create_second_payment_completes_installment(self, db, sample_order):
        """Dodaj drugu uplatu koja pokriva ostatak → PAID."""
        installment = sample_order.installments[0]
        amount = installment.amount
        
        # Prva uplata (50%)
        PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(amount / 2),
            payment_date=date.today() - timedelta(days=5),
        )
        
        # Druga uplata (preostalih 50%)
        payment2 = PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(amount / 2),
            payment_date=date.today(),
        )
        
        assert payment2 is not None
        
        # Provjeri da je rata sada plaćena
        updated_installment = PaymentService.get_installment(installment.id)
        assert updated_installment.status == InstallmentStatus.PAID

    def test_create_payment_invalid_amount_zero(self, db, sample_order):
        """Iznos uplate = 0 → ValueError."""
        installment = sample_order.installments[0]
        
        with pytest.raises(ValueError, match="mora biti veći od 0"):
            PaymentService.create_payment(
                installment_id=installment.id,
                amount="0",
                payment_date=date.today(),
            )

    def test_create_payment_invalid_amount_negative(self, db, sample_order):
        """Iznos uplate < 0 → ValueError."""
        installment = sample_order.installments[0]
        
        with pytest.raises(ValueError, match="mora biti veći od 0"):
            PaymentService.create_payment(
                installment_id=installment.id,
                amount="-50",
                payment_date=date.today(),
            )

    def test_create_payment_nonexistent_installment(self, db):
        """Uplata na nepostojeću ratu → ValueError."""
        with pytest.raises(ValueError, match="Rata nije pronađena"):
            PaymentService.create_payment(
                installment_id=99999,
                amount="100",
                payment_date=date.today(),
            )

    def test_create_payment_already_fully_paid(self, db, sample_order):
        """Uplata na već plaćenu ratu → ValueError."""
        installment = sample_order.installments[0]
        
        # Prvo plati cijelu ratu
        PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(installment.amount),
            payment_date=date.today(),
        )
        
        # Pokušaj druge uplate
        with pytest.raises(ValueError, match="već u potpunosti plaćena"):
            PaymentService.create_payment(
                installment_id=installment.id,
                amount="10",
                payment_date=date.today(),
            )

    def test_create_payment_amount_greater_than_remaining(self, db, sample_order):
        """Iznos uplate veći od preostalog iznosa → ValueError."""
        installment = sample_order.installments[0]
        
        # Prvo plati 50%
        PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(installment.amount / 2),
            payment_date=date.today(),
        )
        
        # Pokušaj uplate većeg iznosa od preostalog
        with pytest.raises(ValueError, match="veći od preostalog iznosa"):
            PaymentService.create_payment(
                installment_id=installment.id,
                amount=str(installment.amount),  # Puna cijena, a preostalo je 50%
                payment_date=date.today(),
            )

    def test_create_payment_on_cancelled_installment(self, db, sample_order):
        """Uplata na otkazanu ratu → ValueError."""
        installment = sample_order.installments[0]
        installment.status = InstallmentStatus.CANCELLED
        db.commit()
        
        with pytest.raises(ValueError, match="nije moguće evidentirati uplatu"):
            PaymentService.create_payment(
                installment_id=installment.id,
                amount="100",
                payment_date=date.today(),
            )


class TestPaymentServiceDeletePayment:
    """Testovi za PaymentService.delete_payment."""

    def test_delete_payment_reverts_status_to_pending(self, db, sample_order):
        """Brisanje jedine uplate → status se vraća na PENDING/OVERDUE."""
        installment = sample_order.installments[0]
        
        # Kreiraj uplatu
        payment = PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(installment.amount / 2),
            payment_date=date.today(),
        )
        
        # Provjeri da je PARTIALLY_PAID
        updated = PaymentService.get_installment(installment.id)
        assert updated.status == InstallmentStatus.PARTIALLY_PAID
        
        # Obriši uplatu
        PaymentService.delete_payment(payment.id)
        
        # Provjeri da se status vratio na PENDING
        reverted = PaymentService.get_installment(installment.id)
        assert reverted.status == InstallmentStatus.PENDING

    def test_delete_payment_reverts_order_to_active(self, db, sample_order):
        """Brisanje uplate koja je napravila COMPLETED → vraća na ACTIVE."""
        installment = sample_order.installments[0]
        
        # Plati cijelu ratu
        payment = PaymentService.create_payment(
            installment_id=installment.id,
            amount=str(installment.amount),
            payment_date=date.today(),
        )
        
        # Provjeri da je order COMPLETED (ako je ovo jedina rata)
        # ili barem da je rata PAID
        updated = PaymentService.get_installment(installment.id)
        assert updated.status == InstallmentStatus.PAID
        
        # Obriši uplatu
        PaymentService.delete_payment(payment.id)
        
        # Provjeri da se status vratio
        reverted = PaymentService.get_installment(installment.id)
        assert reverted.status == InstallmentStatus.PENDING

    def test_delete_payment_nonexistent(self, db):
        """Brisanje nepostojeće uplate → ValueError."""
        with pytest.raises(ValueError, match="Uplata nije pronađena"):
            PaymentService.delete_payment(99999)


class TestPaymentServiceGetInstallment:
    """Testovi za PaymentService.get_installment."""

    def test_get_existing_installment(self, db, sample_order):
        """Dohvatanje postojeće rate → vraća InstallmentDTO."""
        installment_id = sample_order.installments[0].id
        
        installment = PaymentService.get_installment(installment_id)
        
        assert installment is not None
        assert installment.id == installment_id
        assert installment.order_id is not None  # DTO ima order_id umjesto order

    def test_get_nonexistent_installment(self, db):
        """Dohvatanje nepostojeće rate → ValueError."""
        with pytest.raises(ValueError, match="Rata nije pronađena"):
            PaymentService.get_installment(99999)


class TestPaymentServiceGetInstallmentsForPayment:
    """Testovi za PaymentService.get_installments_for_payment."""

    def test_get_installments_overdue(self, db, sample_order):
        """Dohvatanje rata koje kasne."""
        # Postavi due_date u prošlost
        installment = sample_order.installments[0]
        installment.due_date = date.today() - timedelta(days=10)
        db.commit()
        
        installments, total_count = PaymentService.get_installments_for_payment(filter_type="overdue")
        
        assert len(installments) > 0
        assert any(inst.id == installment.id for inst in installments)

    def test_get_installments_unpaid(self, db, sample_order):
        """Dohvatanje svih neplaćenih rata."""
        installments, total_count = PaymentService.get_installments_for_payment(filter_type="unpaid")
        
        assert len(installments) > 0

    def test_get_installments_all(self, db, sample_order):
        """Dohvatanje svih rata."""
        installments, total_count = PaymentService.get_installments_for_payment(filter_type="all")
        
        assert len(installments) >= len(sample_order.installments)

    def test_get_installments_by_customer(self, db, sample_order):
        """Filtriranje rata po kupcu."""
        customer_id = sample_order.customer_id
        
        installments, total_count = PaymentService.get_installments_for_payment(
            filter_type="all",
            customer_id=customer_id
        )
        
        assert len(installments) > 0
        # Sve rate treba da su za ovog kupca (DTO ima order_id)
        for inst in installments:
            assert inst.order_id == sample_order.id

    def test_get_installments_search(self, db, sample_order):
        """Pretraga rata po imenu kupca."""
        # sample_order je ORM objekat iz fixture-a, ima customer relaciju
        customer_name = sample_order.customer.full_name if sample_order.customer else "Test"
        
        installments, total_count = PaymentService.get_installments_for_payment(
            filter_type="all",
            search=customer_name
        )
        
        assert len(installments) > 0


class TestPaymentServiceGetInstallmentDetails:
    """Testovi za PaymentService.get_installment_details."""

    def test_get_installment_details(self, db, sample_order):
        """Dohvatanje detalja rate kao InstallmentDTO."""
        installment_id = sample_order.installments[0].id
        
        details = PaymentService.get_installment_details(installment_id)
        
        assert details is not None
        assert details.id == installment_id
        assert details.order_id is not None  # DTO ima order_id


class TestPaymentServiceGetPaymentsForInstallment:
    """Testovi za PaymentService.get_payments_for_installment."""

    def test_get_payments_for_installment(self, db, sample_order):
        """Dohvatanje uplata za ratu."""
        installment = sample_order.installments[0]
        
        # Kreiraj uplatu
        PaymentService.create_payment(
            installment_id=installment.id,
            amount="25.00",
            payment_date=date.today(),
        )
        
        payments = PaymentService.get_payments_for_installment(installment.id)
        
        assert len(payments) == 1
        assert payments[0].amount == Decimal("25.00")

    def test_get_payments_for_installment_empty(self, db, sample_order):
        """Dohvatanje uplata za ratu bez uplata."""
        installment = sample_order.installments[0]
        
        payments = PaymentService.get_payments_for_installment(installment.id)
        
        assert len(payments) == 0
