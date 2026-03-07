from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List

from sqlalchemy import and_, extract, func, select

from app.database.database import session_scope
from app.database.models import (
    Customer,
    Installment,
    Order,
    Payment,
    Product,
)


# -----------------------------------------------------------------------------
# Data klase za Dashboard
# -----------------------------------------------------------------------------

@dataclass
class KpiData:
    """Podaci za KPI karticu."""
    title: str
    value: str
    footer: str = ""
    icon: str = ""


@dataclass
class InstallmentRow:
    """Red za tabelu rata."""
    customer_name: str
    product_name: str
    installment_number: int
    total_installments: int
    amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal
    due_date: date
    status: str


# -----------------------------------------------------------------------------
# Dashboard Service
# -----------------------------------------------------------------------------

class DashboardService:
    """
    Service layer za Dashboard.

    Sadrži sve funkcije potrebne za prikaz KPI-eva i tabela.
    Bez grafova - samo najvažniji podaci.
    """

    # ---------------------------------------------------------------------
    # KPI Functions - RED 1
    # ---------------------------------------------------------------------

    @staticmethod
    def get_total_customers() -> int:
        """Ukupan broj kupaca."""
        with session_scope() as session:
            return session.execute(
                select(func.count(Customer.id))
            ).scalar() or 0

    @staticmethod
    def get_active_orders_count() -> int:
        """
        Broj aktivnih narudžbi.
        Aktivna narudžba = narudžba koja ima barem jednu ratu
        koja nije potpuno plaćena (remaining_amount > 0).
        """
        with session_scope() as session:
            unpaid_installments = (
                select(Installment.order_id)
                .join(Payment, Installment.id == Payment.installment_id, isouter=True)
                .group_by(Installment.order_id, Installment.id, Installment.amount)
                .having(
                    (Installment.amount - func.coalesce(func.sum(Payment.amount), 0)) > 0
                )
            )

            stmt = select(func.count(func.distinct(Order.id))).where(
                Order.id.in_(unpaid_installments)
            )

            return session.execute(stmt).scalar() or 0

    @staticmethod
    def get_total_remaining_debt() -> Decimal:
        """
        Ukupan preostali dug.
        remaining = suma(installment.amount) - suma(payment.amount)
        """
        with session_scope() as session:
            total_installments = session.execute(
                select(func.sum(Installment.amount))
            ).scalar() or Decimal("0.00")

            total_payments = session.execute(
                select(func.sum(Payment.amount))
            ).scalar() or Decimal("0.00")

            remaining = total_installments - total_payments
            return remaining if remaining > 0 else Decimal("0.00")

    @staticmethod
    def get_current_month_payments() -> Decimal:
        """Ukupan iznos naplaćen u tekućem mjesecu."""
        today = date.today()

        with session_scope() as session:
            stmt = select(func.sum(Payment.amount)).where(
                and_(
                    extract('year', Payment.payment_date) == today.year,
                    extract('month', Payment.payment_date) == today.month
                )
            )

            result = session.execute(stmt).scalar()
            return result if result else Decimal("0.00")

    # ---------------------------------------------------------------------
    # Status Kartice - RED 2
    # ---------------------------------------------------------------------

    @staticmethod
    def get_overdue_installments_count() -> int:
        """Broj rata koje kasne (due_date < danas i remaining > 0)."""
        today = date.today()

        with session_scope() as session:
            stmt = select(func.count(Installment.id)).where(
                and_(
                    Installment.due_date < today,
                    (Installment.amount - func.coalesce(
                        select(func.sum(Payment.amount))
                        .where(Payment.installment_id == Installment.id)
                        .correlate(Installment)
                        .scalar_subquery(),
                        0
                    )) > 0
                )
            )

            return session.execute(stmt).scalar() or 0

    @staticmethod
    def get_current_month_installments_count() -> int:
        """Broj rata koje dospijevaju u tekućem mjesecu."""
        today = date.today()

        with session_scope() as session:
            stmt = select(func.count(Installment.id)).where(
                and_(
                    extract('year', Installment.due_date) == today.year,
                    extract('month', Installment.due_date) == today.month
                )
            )

            return session.execute(stmt).scalar() or 0

    # ---------------------------------------------------------------------
    # Glavni KPI-jevi (RED 1)
    # ---------------------------------------------------------------------

    @staticmethod
    def get_dashboard_kpis() -> List[KpiData]:
        """Vraća 4 glavna KPI-ja za dashboard (RED 1)."""
        total_customers = DashboardService.get_total_customers()
        active_orders = DashboardService.get_active_orders_count()
        total_debt = DashboardService.get_total_remaining_debt()
        month_payments = DashboardService.get_current_month_payments()

        return [
            KpiData(
                title="Ukupan broj kupaca",
                value=str(total_customers),
                footer="Baza kupaca",
                icon="👥"
            ),
            KpiData(
                title="Aktivne narudžbe",
                value=str(active_orders),
                footer="Sa neplaćenim ratama",
                icon="📋"
            ),
            KpiData(
                title="Ukupan preostali dug",
                value=f"{total_debt:.2f} KM",
                footer="Aktivna potraživanja",
                icon="💰"
            ),
            KpiData(
                title="Naplaćeno ovaj mjesec",
                value=f"{month_payments:.2f} KM",
                footer="Tekući mjesec",
                icon="💳"
            ),
        ]

    # ---------------------------------------------------------------------
    # Status Kartice (RED 2)
    # ---------------------------------------------------------------------

    @staticmethod
    def get_status_kpis() -> List[KpiData]:
        """Vraća 2 status KPI-ja za dashboard (RED 2)."""
        overdue = DashboardService.get_overdue_installments_count()
        month_installments = DashboardService.get_current_month_installments_count()

        return [
            KpiData(
                title="Rate koje kasne",
                value=str(overdue),
                footer="Prioritet za naplatu",
                icon="⚠️"
            ),
            KpiData(
                title="Rate ovog mjeseca",
                value=str(month_installments),
                footer="Dospijevaju sada",
                icon="📅"
            ),
        ]

    # ---------------------------------------------------------------------
    # Tabela: Rate koje kasne
    # ---------------------------------------------------------------------

    @staticmethod
    def get_overdue_installments(limit: int = 25) -> List[InstallmentRow]:
        """
        Vraća liste rata koje kasne.
        Rata kasni ako: due_date < danas i remaining_amount > 0
        """
        today = date.today()

        with session_scope() as session:
            paid_sum_subq = (
                select(
                    Payment.installment_id,
                    func.sum(Payment.amount).label("paid_amount")
                )
                .group_by(Payment.installment_id)
                .subquery()
            )

            stmt = (
                select(
                    Installment,
                    Order,
                    Customer,
                    Product,
                    func.coalesce(paid_sum_subq.c.paid_amount, 0).label("paid_amount")
                )
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Order.customer_id == Customer.id)
                .outerjoin(Product, Order.product_id == Product.id)
                .outerjoin(paid_sum_subq, Installment.id == paid_sum_subq.c.installment_id)
                .where(
                    and_(
                        Installment.due_date < today,
                        (Installment.amount - func.coalesce(paid_sum_subq.c.paid_amount, 0)) > 0
                    )
                )
                .order_by(Installment.due_date.asc())
                .limit(limit)
            )

            results = session.execute(stmt).all()

            rows: List[InstallmentRow] = []
            for row in results:
                installment = row.Installment
                order = row.Order
                customer = row.Customer
                paid_amount = row.paid_amount or Decimal("0.00")

                remaining = installment.amount - paid_amount

                if remaining <= 0:
                    status = "paid"
                elif paid_amount > 0:
                    status = "partially_paid"
                else:
                    status = "overdue"

                rows.append(InstallmentRow(
                    customer_name=customer.full_name if customer else "N/A",
                    product_name=order.product_name_snapshot,
                    installment_number=installment.installment_number,
                    total_installments=order.installments_count,
                    amount=installment.amount,
                    paid_amount=paid_amount,
                    remaining_amount=remaining if remaining > 0 else Decimal("0.00"),
                    due_date=installment.due_date,
                    status=status
                ))

            return rows

    # ---------------------------------------------------------------------
    # Tabela: Rate za ovaj mjesec
    # ---------------------------------------------------------------------

    @staticmethod
    def get_current_month_installments(limit: int = 25) -> List[InstallmentRow]:
        """Vraća liste rata koje dospijevaju u tekućem mjesecu."""
        today = date.today()

        with session_scope() as session:
            paid_sum_subq = (
                select(
                    Payment.installment_id,
                    func.sum(Payment.amount).label("paid_amount")
                )
                .group_by(Payment.installment_id)
                .subquery()
            )

            stmt = (
                select(
                    Installment,
                    Order,
                    Customer,
                    Product,
                    func.coalesce(paid_sum_subq.c.paid_amount, 0).label("paid_amount")
                )
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Order.customer_id == Customer.id)
                .outerjoin(Product, Order.product_id == Product.id)
                .outerjoin(paid_sum_subq, Installment.id == paid_sum_subq.c.installment_id)
                .where(
                    and_(
                        extract('year', Installment.due_date) == today.year,
                        extract('month', Installment.due_date) == today.month
                    )
                )
                .order_by(Installment.due_date.asc())
                .limit(limit)
            )

            results = session.execute(stmt).all()

            rows: List[InstallmentRow] = []
            for row in results:
                installment = row.Installment
                order = row.Order
                customer = row.Customer
                paid_amount = row.paid_amount or Decimal("0.00")

                remaining = installment.amount - paid_amount

                if remaining <= 0:
                    status = "paid"
                elif paid_amount > 0:
                    status = "partially_paid"
                else:
                    status = "pending"

                rows.append(InstallmentRow(
                    customer_name=customer.full_name if customer else "N/A",
                    product_name=order.product_name_snapshot,
                    installment_number=installment.installment_number,
                    total_installments=order.installments_count,
                    amount=installment.amount,
                    paid_amount=paid_amount,
                    remaining_amount=remaining if remaining > 0 else Decimal("0.00"),
                    due_date=installment.due_date,
                    status=status
                ))

            return rows
