from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import Installment, InstallmentStatus, Order


class InstallmentService:
    @staticmethod
    def generate_for_order(order: Order) -> list[Installment]:
        if order.installments_count < 1:
            raise ValueError("Broj rata mora biti najmanje 1.")

        total = Decimal(str(order.total_price_snapshot))
        count = order.installments_count
        base_amount = (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        installments: list[Installment] = []
        allocated = Decimal("0.00")
        first_due_date = order.first_due_date or date.today()

        for number in range(1, count + 1):
            amount = base_amount
            if number == count:
                amount = total - allocated
            allocated += amount

            installments.append(
                Installment(
                    order=order,
                    installment_number=number,
                    due_date=first_due_date + relativedelta(months=number - 1),
                    amount=amount,
                    status=InstallmentStatus.PENDING,
                )
            )

        return installments

    @staticmethod
    def sync_statuses() -> None:
        """
        Sinhronizuje status svih rata u bazi.
        
        Za svaku ratu izračuna paid_amount i postavi status:
        - paid_amount >= installment.amount → PAID
        - 0 < paid_amount < installment.amount → PARTIALLY_PAID
        - due_date < today AND paid_amount == 0 → OVERDUE
        - inače → PENDING
        """
        today = date.today()
        
        with session_scope() as session:
            # Dohvati sve rate sa uplatama
            stmt = select(Installment).order_by(Installment.id)
            installments = list(session.execute(stmt).scalars().all())
            
            updated_count = 0
            
            for installment in installments:
                # Izračunaj plaćeno
                paid_amount = sum(
                    (payment.amount for payment in installment.payments),
                    Decimal("0.00")
                )
                amount = Decimal(str(installment.amount))
                
                # Odredi novi status
                if paid_amount >= amount:
                    new_status = InstallmentStatus.PAID
                elif paid_amount > Decimal("0.00"):
                    new_status = InstallmentStatus.PARTIALLY_PAID
                elif installment.due_date < today:
                    new_status = InstallmentStatus.OVERDUE
                else:
                    new_status = InstallmentStatus.PENDING
                
                # Ažuriraj ako se status promijenio
                if installment.status != new_status:
                    installment.status = new_status
                    if new_status == InstallmentStatus.PAID:
                        installment.paid_at = date.today()
                    updated_count += 1
            
            # Commit se dešava automatski kroz session_scope
