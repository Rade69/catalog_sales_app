from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta

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
