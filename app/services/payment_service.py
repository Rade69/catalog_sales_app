from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import session_scope
from app.database.models import Campaign, Customer, Installment, InstallmentStatus, Order, OrderStatus, Payment
from app.dto import InstallmentDTO, PaymentDTO, _to_installment_dto, _to_payment_dto

TWOPLACES = Decimal('0.01')


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _recalculate_installment_status(installment: Installment) -> None:
    """Ažurira status rate na osnovu uplata."""
    paid_amount = sum((Decimal(str(payment.amount)) for payment in installment.payments), Decimal('0.00'))
    amount = Decimal(str(installment.amount))

    if paid_amount >= amount:
        installment.status = InstallmentStatus.PAID
        installment.paid_at = date.today()
        return

    installment.paid_at = None
    if paid_amount > Decimal('0.00'):
        installment.status = InstallmentStatus.PARTIALLY_PAID
    elif installment.due_date < date.today():
        installment.status = InstallmentStatus.OVERDUE
    else:
        installment.status = InstallmentStatus.PENDING


def _recalculate_order_status(order: Order) -> None:
    """Ažurira status narudžbe na osnovu statusa rata."""
    if order.installments and all(inst.status == InstallmentStatus.PAID for inst in order.installments):
        order.status = OrderStatus.COMPLETED
    elif order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.ACTIVE


class PaymentService:
    @staticmethod
    def get_installment(installment_id: int) -> InstallmentDTO:
        """Vraća InstallmentDTO sa svim podacima o rati."""
        with session_scope() as session:
            installment = session.execute(
                select(Installment)
                .options(
                    joinedload(Installment.order).joinedload(Order.customer),
                    joinedload(Installment.order).joinedload(Order.campaign),
                    joinedload(Installment.payments),
                )
                .where(Installment.id == installment_id)
            ).unique().scalar_one_or_none()
            if installment is None:
                raise ValueError('Rata nije pronađena.')
            return _to_installment_dto(installment, include_order_data=True)

    @staticmethod
    def create_payment(installment_id: int, amount: str | float | Decimal, payment_date: date, note: str = '') -> PaymentDTO:
        """Kreira novu uplatu i vraća PaymentDTO."""
        amount_decimal = _to_decimal(amount)
        
        # Validacija iznosa
        if amount_decimal <= Decimal('0.00'):
            raise ValueError('Iznos uplate mora biti veći od 0.')
        
        if amount_decimal > Decimal('100000'):
            raise ValueError('Iznos uplate ne smije biti veći od 100.000.')
        
        # Validacija decimalnih mjesta
        if abs(amount_decimal.as_tuple().exponent) > 2:
            raise ValueError('Iznos uplate može imati najviše 2 decimalna mjesta.')
        
        # Validacija datuma
        today = date.today()
        one_year_ago = date(today.year - 1, today.month, today.day)
        
        if payment_date > today:
            raise ValueError('Datum uplate ne smije biti u budućnosti.')
        
        if payment_date < one_year_ago:
            raise ValueError('Datum uplate ne smije biti stariji od 1 godine.')
        
        # Validacija napomene
        note = note.strip()
        if note and len(note) > 500:
            raise ValueError('Napomena ne smije biti duža od 500 karaktera.')

        with session_scope() as session:
            installment = session.execute(
                select(Installment)
                .options(joinedload(Installment.order), joinedload(Installment.payments))
                .where(Installment.id == installment_id)
            ).unique().scalar_one_or_none()
            if installment is None:
                raise ValueError('Rata nije pronađena.')
            if installment.status == InstallmentStatus.CANCELLED:
                raise ValueError('Na otkazanu ratu nije moguće evidentirati uplatu.')

            remaining_before = _to_decimal(installment.remaining_amount)
            if remaining_before <= Decimal('0.00'):
                raise ValueError('Odabrana rata je već u potpunosti plaćena.')
            if amount_decimal > remaining_before:
                raise ValueError(
                    f'Iznos uplate ({amount_decimal:.2f} EUR) je veći od preostalog iznosa rate ({remaining_before:.2f} EUR).'
                )

            payment = Payment(
                installment_id=installment.id,
                payment_date=payment_date,
                amount=amount_decimal,
                note=(note.strip() if note else None) or None,
            )
            session.add(payment)
            session.flush()
            session.refresh(payment)

            session.refresh(installment)
            _recalculate_installment_status(installment)
            _recalculate_order_status(installment.order)
            session.flush()
            session.refresh(payment)
            return _to_payment_dto(payment)

    @staticmethod
    def delete_payment(payment_id: int) -> None:
        """Briše uplatu i ažurira statuse rate i narudžbe."""
        with session_scope() as session:
            payment = session.execute(
                select(Payment)
                .options(
                    joinedload(Payment.installment)
                    .joinedload(Installment.order),
                    joinedload(Payment.installment)
                    .joinedload(Installment.payments),
                )
                .where(Payment.id == payment_id)
            ).unique().scalar_one_or_none()
            if payment is None:
                raise ValueError('Uplata nije pronađena.')

            installment = payment.installment
            order = installment.order
            session.delete(payment)
            session.flush()
            session.refresh(installment)
            _recalculate_installment_status(installment)
            _recalculate_order_status(order)
            session.flush()

    @staticmethod
    def get_installments_for_payment(
        filter_type: str = "overdue",
        search: str = "",
        customer_id: Optional[int] = None,
        limit: int = 0,
        offset: int = 0,
    ) -> tuple[List[InstallmentDTO], int]:
        """
        Vraća listu InstallmentDTO za prikaz u PaymentsPage.

        filter_type:
            'overdue'  — samo rate koje kasne (due_date < danas, remaining > 0)
            'month'    — rate ovog mjeseca
            'unpaid'   — sve neplaćene rate
            'all'      — sve rate
        customer_id:
            None — svi kupci
            int — samo rate za odabranog kupca
        limit, offset:
            Paginacija - limit=0 vraća sve
        """
        from sqlalchemy import and_, extract, func

        today = date.today()

        with session_scope() as session:
            stmt = (
                select(Installment)
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Order.customer_id == Customer.id)
                .options(
                    selectinload(Installment.order).selectinload(Order.customer),
                    selectinload(Installment.payments),
                )
            )

            # Filter po tipu
            remaining_expr = (
                Installment.amount - func.coalesce(
                    select(func.sum(Payment.amount))
                    .where(Payment.installment_id == Installment.id)
                    .correlate(Installment)
                    .scalar_subquery(),
                    0
                )
            )

            if filter_type == "overdue":
                stmt = stmt.where(
                    and_(Installment.due_date < today, remaining_expr > 0)
                )
            elif filter_type == "month":
                stmt = stmt.where(
                    and_(
                        extract('year', Installment.due_date) == today.year,
                        extract('month', Installment.due_date) == today.month,
                    )
                )
            elif filter_type == "unpaid":
                stmt = stmt.where(remaining_expr > 0)
            # 'all' — bez filtera

            # Filter po kupcu
            if customer_id is not None:
                stmt = stmt.where(Customer.id == customer_id)

            # Search
            if search:
                like = f"%{search}%"
                stmt = stmt.where(
                    Customer.full_name.ilike(like) |
                    Order.product_name_snapshot.ilike(like) |
                    Order.contract_number.ilike(like)
                )

            stmt = stmt.order_by(Installment.due_date.asc())

            # Brojanje ukupnog broja stavki
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = session.execute(count_stmt).scalar() or 0

            # Primijeni paginaciju ako je limit > 0
            if limit > 0:
                stmt = stmt.limit(limit).offset(offset)

            installments = list(session.execute(stmt).scalars().unique())
            # Uključi denormalizovane podatke o narudžbi i kupcu
            installments_dto = [_to_installment_dto(inst, include_order_data=True) for inst in installments]
            return installments_dto, total_count

    @staticmethod
    def get_installment_details(installment_id: int) -> Optional[InstallmentDTO]:
        """Vraća InstallmentDTO sa detaljima odabrane rate."""
        with session_scope() as session:
            inst = session.get(
                Installment, installment_id,
                options=[
                    selectinload(Installment.order).selectinload(Order.customer),
                    selectinload(Installment.payments),
                ]
            )
            if not inst:
                return None
            return _to_installment_dto(inst, include_order_data=True)

    @staticmethod
    def get_payments_for_installment(installment_id: int) -> List[PaymentDTO]:
        """Vraća listu PaymentDTO za odabranu ratu."""
        with session_scope() as session:
            payments = list(
                session.execute(
                    select(Payment)
                    .where(Payment.installment_id == installment_id)
                    .order_by(Payment.payment_date.desc())
                ).scalars()
            )
            return [_to_payment_dto(p) for p in payments]
