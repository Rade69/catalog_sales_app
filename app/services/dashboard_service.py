from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, extract, func, select
from sqlalchemy.orm import Session

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    Customer,
    Installment,
    InstallmentStatus,
    Order,
    OrderStatus,
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


@dataclass
class ChartDataPoint:
    """Tačka podataka za graf."""
    label: str
    value: float


@dataclass
class ChartData:
    """Podaci za grafikon."""
    title: str
    labels: List[str]
    values: List[float]


# -----------------------------------------------------------------------------
# Dashboard Service
# -----------------------------------------------------------------------------

class DashboardService:
    """
    Service layer za Dashboard.
    
    Sadrži sve funkcije potrebne za prikaz KPI-eva, tabela i grafova.
    """

    # ---------------------------------------------------------------------
    # KPI Functions
    # ---------------------------------------------------------------------

    @staticmethod
    def get_total_customers() -> int:
        """
        Ukupan broj kupaca.
        """
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
            # Subquery za rate koje nisu plaćene
            unpaid_installments = (
                select(Installment.order_id)
                .join(Payment, Installment.id == Payment.installment_id, isouter=True)
                .group_by(Installment.order_id, Installment.id, Installment.amount)
                .having(
                    (Installment.amount - func.coalesce(func.sum(Payment.amount), 0)) > 0
                )
            )
            
            # Broj narudžbi koje imaju barem jednu neplaćenu ratu
            stmt = select(func.count(func.distinct(Order.id))).where(
                Order.id.in_(unpaid_installments)
            )
            
            return session.execute(stmt).scalar() or 0

    @staticmethod
    def get_total_remaining_debt() -> Decimal:
        """
        Ukupan preostali dug.
        
        Računica:
        - Za svaku ratu: remaining = installment.amount - sum(payments)
        - Suma svih remaining gdje remaining > 0
        """
        with session_scope() as session:
            # Suma svih iznosa rata
            total_installments = session.execute(
                select(func.sum(Installment.amount))
            ).scalar() or Decimal("0.00")
            
            # Suma svih uplata
            total_payments = session.execute(
                select(func.sum(Payment.amount))
            ).scalar() or Decimal("0.00")
            
            remaining = total_installments - total_payments
            
            return remaining if remaining > 0 else Decimal("0.00")

    @staticmethod
    def get_current_month_payments() -> Decimal:
        """
        Ukupan iznos naplaćen u tekućem mjesecu.
        
        Suma svih payment.amount gdje payment_date u tekućem mjesecu.
        """
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

    @staticmethod
    def get_overdue_installments_count() -> int:
        """
        Broj rata koje kasne.
        
        Rata kasni ako:
        - due_date < danas
        - remaining_amount > 0 (nije potpuno plaćena)
        """
        today = date.today()
        
        with session_scope() as session:
            # Broj rata koje kasne i nisu plaćene
            stmt = select(func.count(Installment.id)).where(
                and_(
                    Installment.due_date < today,
                    # remaining_amount > 0
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
        """
        Broj rata koje dospijevaju u tekućem mjesecu.
        """
        today = date.today()
        
        with session_scope() as session:
            stmt = select(func.count(Installment.id)).where(
                and_(
                    extract('year', Installment.due_date) == today.year,
                    extract('month', Installment.due_date) == today.month
                )
            )
            
            return session.execute(stmt).scalar() or 0

    @staticmethod
    def get_all_kpis() -> List[KpiData]:
        """
        Vraća sve KPI podatke za dashboard.
        """
        total_customers = DashboardService.get_total_customers()
        active_orders = DashboardService.get_active_orders_count()
        total_debt = DashboardService.get_total_remaining_debt()
        month_payments = DashboardService.get_current_month_payments()
        overdue = DashboardService.get_overdue_installments_count()
        month_installments = DashboardService.get_current_month_installments_count()
        
        return [
            KpiData(
                title="Ukupan broj kupaca",
                value=str(total_customers),
                footer="Baza kupaca"
            ),
            KpiData(
                title="Aktivne narudžbe",
                value=str(active_orders),
                footer="Sa neplaćenim ratama"
            ),
            KpiData(
                title="Ukupan preostali dug",
                value=f"{total_debt:.2f} KM",
                footer="Aktivna potraživanja"
            ),
            KpiData(
                title="Naplaćeno ovaj mjesec",
                value=f"{month_payments:.2f} KM",
                footer="Tekući mjesec"
            ),
            KpiData(
                title="Rate koje kasne",
                value=str(overdue),
                footer="Prioritet za naplatu"
            ),
            KpiData(
                title="Rate ovog mjeseca",
                value=str(month_installments),
                footer="Dospijevaju sada"
            ),
        ]

    # ---------------------------------------------------------------------
    # Tabela: Rate koje kasne
    # ---------------------------------------------------------------------

    @staticmethod
    def get_overdue_installments(limit: int = 10) -> List[InstallmentRow]:
        """
        Vraća liste rata koje kasne.
        
        Rata kasni ako:
        - due_date < danas
        - remaining_amount > 0
        """
        today = date.today()
        
        with session_scope() as session:
            # Query za rate koje kasne
            stmt = (
                select(
                    Installment,
                    Order,
                    Customer,
                    Product
                )
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Order.customer_id == Customer.id)
                .outerjoin(Product, Order.product_id == Product.id)
                .outerjoin(Payment, Installment.id == Payment.installment_id)
                .where(
                    and_(
                        Installment.due_date < today,
                        # remaining_amount > 0
                        (Installment.amount - func.coalesce(
                            select(func.sum(Payment.amount))
                            .where(Payment.installment_id == Installment.id)
                            .correlate(Installment)
                            .scalar_subquery(),
                            0
                        )) > 0
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
                
                # Računaj plaćeno i preostalo
                paid_amount = session.execute(
                    select(func.sum(Payment.amount))
                    .where(Payment.installment_id == installment.id)
                ).scalar() or Decimal("0.00")
                
                remaining = installment.amount - paid_amount
                
                # Odredi status
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
    def get_current_month_installments(limit: int = 10) -> List[InstallmentRow]:
        """
        Vraća liste rata koje dospijevaju u tekućem mjesecu.
        """
        today = date.today()
        
        with session_scope() as session:
            stmt = (
                select(Installment, Order, Customer, Product)
                .join(Order, Installment.order_id == Order.id)
                .join(Customer, Order.customer_id == Customer.id)
                .outerjoin(Product, Order.product_id == Product.id)
                .outerjoin(Payment, Installment.id == Payment.installment_id)
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
                
                # Računaj plaćeno i preostalo
                paid_amount = session.execute(
                    select(func.sum(Payment.amount))
                    .where(Payment.installment_id == installment.id)
                ).scalar() or Decimal("0.00")
                
                remaining = installment.amount - paid_amount
                
                # Odredi status
                if remaining <= 0:
                    status = "paid"
                elif paid_amount > 0:
                    status = "partially_paid"
                else:
                    status = "pending"
                
                rows.append(InstallmentRow(
                    customer_name=order.customer.full_name if order.customer else "N/A",
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
    # Graf: Uplate po mjesecima (posljednjih 6 mjeseci)
    # ---------------------------------------------------------------------

    @staticmethod
    def get_monthly_payments_chart_data() -> ChartData:
        """
        Podaci za graf: Uplate po mjesecima (posljednjih 6 mjeseci).
        
        Vraća podatke spremne za prikaz grafa.
        """
        today = date.today()
        
        with session_scope() as session:
            labels = []
            values = []
            
            # Posljednjih 6 mjeseci
            for i in range(5, -1, -1):
                # Izračunaj mjesec i godinu
                month_offset = today.month - i
                year = today.year
                if month_offset <= 0:
                    month_offset += 12
                    year -= 1
                
                month_num = month_offset
                
                # Naziv mjeseca
                month_name = date(year, month_num, 1).strftime("%B %Y")
                labels.append(month_name)
                
                # Suma uplata za taj mjesec
                stmt = select(func.sum(Payment.amount)).where(
                    and_(
                        extract('year', Payment.payment_date) == year,
                        extract('month', Payment.payment_date) == month_num
                    )
                )
                
                result = session.execute(stmt).scalar()
                values.append(float(result) if result else 0.0)
            
            return ChartData(
                title="Uplate po mjesecima (posljednjih 6 mjeseci)",
                labels=labels,
                values=values
            )

    # ---------------------------------------------------------------------
    # Graf: Broj narudžbi po kampanjama
    # ---------------------------------------------------------------------

    @staticmethod
    def get_orders_by_campaign_chart_data() -> ChartData:
        """
        Podaci za graf: Broj narudžbi po kampanjama.
        """
        with session_scope() as session:
            stmt = (
                select(Campaign.name, func.count(Order.id))
                .join(Order, Campaign.id == Order.campaign_id)
                .group_by(Campaign.id, Campaign.name)
                .order_by(func.count(Order.id).desc())
            )
            
            results = session.execute(stmt).all()
            
            labels = [row[0] for row in results]
            values = [float(row[1]) for row in results]
            
            return ChartData(
                title="Broj narudžbi po kampanjama",
                labels=labels,
                values=values
            )

    # ---------------------------------------------------------------------
    # Helper: Formatiranje iznosa
    # ---------------------------------------------------------------------

    @staticmethod
    def format_amount(amount: Decimal) -> str:
        """
        Formatira Decimal iznos kao KM string.
        """
        return f"{amount:.2f} KM"
