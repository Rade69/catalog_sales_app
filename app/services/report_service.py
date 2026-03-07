from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import extract, select
from sqlalchemy.orm import joinedload

from app.database.database import session_scope
from app.database.models import Installment, Order, Payment
from app.reports.excel_reports import ExcelReports


@dataclass
class MonthlyPaymentsReport:
    year: int
    month: int
    total_paid: Decimal
    payments_count: int
    dataframe: pd.DataFrame


class ReportService:
    @staticmethod
    def get_monthly_payments_report(year: int, month: int) -> MonthlyPaymentsReport:
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
                .where(extract("year", Payment.payment_date) == year)
                .where(extract("month", Payment.payment_date) == month)
                .order_by(Payment.payment_date.desc(), Payment.id.desc())
            )
            payments = list(session.execute(stmt).scalars().all())

            rows: list[dict[str, object]] = []
            total_paid = Decimal("0.00")
            for payment in payments:
                installment = payment.installment
                order = installment.order
                customer = order.customer
                amount = Decimal(str(payment.amount))
                total_paid += amount
                rows.append(
                    {
                        "Datum uplate": payment.payment_date.strftime("%d.%m.%Y"),
                        "Kupac": customer.full_name,
                        "Artikal": order.product_name_snapshot,
                        "Kampanja": order.campaign.name if order.campaign else "",
                        "Rata": f"{installment.installment_number}/{order.installments_count}",
                        "Iznos uplate (KM)": float(amount),
                        "Napomena": payment.note or "",
                    }
                )

        dataframe = pd.DataFrame(rows)
        return MonthlyPaymentsReport(
            year=year,
            month=month,
            total_paid=total_paid,
            payments_count=len(payments),
            dataframe=dataframe,
        )

    @staticmethod
    def export_monthly_payments_report(year: int, month: int, output_path: str | Path) -> Path:
        report = ReportService.get_monthly_payments_report(year, month)
        if report.dataframe.empty:
            report.dataframe = pd.DataFrame(
                [{
                    "Info": "Za odabrani mjesec nema evidentiranih uplata.",
                    "Ukupan iznos uplaćenih sredstava (KM)": float(report.total_paid),
                }]
            )
        else:
            summary = pd.DataFrame(
                [{
                    "Datum uplate": "",
                    "Kupac": "UKUPNO",
                    "Artikal": "",
                    "Kampanja": "",
                    "Rata": "",
                    "Iznos uplate (KM)": float(report.total_paid),
                    "Napomena": f"Broj uplata: {report.payments_count}",
                }]
            )
            report.dataframe = pd.concat([report.dataframe, summary], ignore_index=True)
        return ExcelReports.export_dataframe(report.dataframe, output_path)
