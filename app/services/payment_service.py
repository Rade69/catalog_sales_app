from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import Campaign, Customer, Installment, InstallmentStatus, Order, OrderStatus, Payment

TWOPLACES = Decimal('0.01')


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _recalculate_installment_status(installment: Installment) -> None:
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
    if order.installments and all(inst.status == InstallmentStatus.PAID for inst in order.installments):
        order.status = OrderStatus.COMPLETED
    elif order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.ACTIVE


@dataclass
class InstallmentLookupRow:
    installment_id: int
    customer_name: str
    product_name: str
    campaign_name: str
    installment_number: int
    installments_count: int
    due_date: date
    status: str
    amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal


class PaymentService:
    @staticmethod
    def list_installments(search_text: str = '', only_open: bool = False) -> list[Installment]:
        with session_scope() as session:
            stmt = (
                select(Installment)
                .options(
                    joinedload(Installment.order).joinedload(Order.customer),
                    joinedload(Installment.order).joinedload(Order.campaign),
                    joinedload(Installment.payments),
                )
                .join(Installment.order)
                .join(Order.customer)
                .join(Order.campaign)
                .order_by(Installment.due_date.asc(), Installment.installment_number.asc())
            )
            search = search_text.strip()
            if search:
                like = f'%{search}%'
                stmt = stmt.where(
                    or_(
                        Customer.full_name.ilike(like),
                        Customer.phone.ilike(like),
                        Customer.city.ilike(like),
                        Order.product_name_snapshot.ilike(like),
                        Order.product_code_snapshot.ilike(like),
                        Order.product_brand_snapshot.ilike(like),
                        Campaign.name.ilike(like),
                    )
                )
            installments = list(session.execute(stmt).unique().scalars().all())
            if only_open:
                installments = [inst for inst in installments if Decimal(str(inst.remaining_amount)) > Decimal('0.00')]
            return installments

    @staticmethod
    def build_installment_lookup(search_text: str = '', only_open: bool = False) -> list[InstallmentLookupRow]:
        rows: list[InstallmentLookupRow] = []
        for inst in PaymentService.list_installments(search_text=search_text, only_open=only_open):
            order = inst.order
            rows.append(
                InstallmentLookupRow(
                    installment_id=inst.id,
                    customer_name=order.customer.full_name,
                    product_name=order.product_name_snapshot,
                    campaign_name=order.campaign.name,
                    installment_number=inst.installment_number,
                    installments_count=order.installments_count,
                    due_date=inst.due_date,
                    status=inst.status.value,
                    amount=_to_decimal(inst.amount),
                    paid_amount=_to_decimal(inst.paid_amount),
                    remaining_amount=_to_decimal(inst.remaining_amount),
                )
            )
        return rows

    @staticmethod
    def get_installment(installment_id: int) -> Installment:
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
            return installment

    @staticmethod
    def list_payments(search_text: str = '') -> list[Payment]:
        with session_scope() as session:
            stmt = (
                select(Payment)
                .options(
                    joinedload(Payment.installment)
                    .joinedload(Installment.order)
                    .joinedload(Order.customer),
                    joinedload(Payment.installment)
                    .joinedload(Installment.order)
                    .joinedload(Order.campaign),
                )
                .join(Payment.installment)
                .join(Installment.order)
                .join(Order.customer)
                .join(Order.campaign)
                .order_by(Payment.payment_date.desc(), Payment.id.desc())
            )
            search = search_text.strip()
            if search:
                like = f'%{search}%'
                stmt = stmt.where(
                    or_(
                        Customer.full_name.ilike(like),
                        Order.product_name_snapshot.ilike(like),
                        Campaign.name.ilike(like),
                        Payment.note.ilike(like),
                    )
                )
            return list(session.execute(stmt).unique().scalars().all())

    @staticmethod
    def create_payment(installment_id: int, amount: str | float | Decimal, payment_date: date, note: str = '') -> Payment:
        amount_decimal = _to_decimal(amount)
        if amount_decimal <= Decimal('0.00'):
            raise ValueError('Iznos uplate mora biti veći od 0.')

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
                    f'Iznos uplate ({amount_decimal:.2f} KM) je veći od preostalog iznosa rate ({remaining_before:.2f} KM).'
                )

            payment = Payment(
                installment_id=installment.id,
                payment_date=payment_date,
                amount=amount_decimal,
                note=note.strip() or None,
            )
            session.add(payment)
            session.flush()
            session.refresh(payment)

            session.refresh(installment)
            _recalculate_installment_status(installment)
            _recalculate_order_status(installment.order)
            session.flush()
            session.refresh(payment)
            return payment

    @staticmethod
    def delete_payment(payment_id: int) -> None:
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
        customer_id: Optional[int] = None
    ) -> list:
        """
        Vraća rate za prikaz u PaymentsPage.

        filter_type:
            'overdue'  — samo rate koje kasne (due_date < danas, remaining > 0)
            'month'    — rate ovog mjeseca
            'unpaid'   — sve neplaćene rate
            'all'      — sve rate
        customer_id:
            None — svi kupci
            int — samo rate za odabranog kupca
        """
        from sqlalchemy import and_, extract, func

        today = date.today()

        with session_scope() as session:
            stmt = (
                select(Installment)
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Installment.order.has(Order.customer_id == Customer.id))
                .options(
                    joinedload(Installment.order).joinedload(Order.customer),
                    joinedload(Installment.payments),
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
                    Order.product_name_snapshot.ilike(like)
                )

            stmt = stmt.order_by(Installment.due_date.asc())

            installments = list(session.execute(stmt).scalars().unique())

            # Izračunaj paid_amount za svaku ratu i sačuvaj u _paid_amount_value
            # (paid_amount je property u modelu i ne može se postaviti direktno)
            for inst in installments:
                paid = sum(
                    (p.amount for p in inst.payments), Decimal("0.00")
                )
                object.__setattr__(inst, '_paid_amount_value', paid)
                session.expunge(inst)

            return installments

    @staticmethod
    def get_installment_details(installment_id: int):
        """Vraća detalje odabrane rate za prikaz u info panelu."""
        with session_scope() as session:
            inst = session.get(
                Installment, installment_id,
                options=[joinedload(Installment.payments)]
            )
            if not inst:
                return None
            paid = sum((p.amount for p in inst.payments), Decimal("0.00"))
            object.__setattr__(inst, '_paid_amount_value', paid)
            session.expunge(inst)
            return inst

    @staticmethod
    def get_payments_for_installment(installment_id: int) -> list:
        """Vraća sve uplate za odabranu ratu."""
        with session_scope() as session:
            payments = list(
                session.execute(
                    select(Payment)
                    .where(Payment.installment_id == installment_id)
                    .order_by(Payment.payment_date.desc())
                ).scalars()
            )
            for p in payments:
                session.expunge(p)
            return payments
