"""
Background workers for DB operations using QThread.

All DB operations are moved off the main thread to prevent UI freezing.
Each worker emits a `finished` signal with DTO data or an `error` signal.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QThread, Signal

from app.services.campaign_service import CampaignService
from app.services.customer_service import CustomerService
from app.services.dashboard_service import DashboardService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService


class BaseWorker(QThread):
    """Base class for all background workers."""

    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._error_callback = None


# -----------------------------------------------------------------------------
# Dashboard Worker
# -----------------------------------------------------------------------------

class LoadDashboardWorker(BaseWorker):
    """Worker za učitavanje dashboard podataka."""

    finished = Signal(object)  # DashboardData DTO

    def run(self) -> None:
        try:
            service = DashboardService()
            data = service.get_all_dashboard_data()
            self.finished.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Customers Worker
# -----------------------------------------------------------------------------

class LoadCustomersWorker(BaseWorker):
    """Worker za učitavanje liste kupaca."""

    finished = Signal(list)  # list[CustomerDTO]

    def __init__(self, search_text: str = "") -> None:
        super().__init__()
        self._search_text = search_text

    def run(self) -> None:
        try:
            customers = CustomerService.list_customers(self._search_text)
            self.finished.emit(customers)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Orders Worker
# -----------------------------------------------------------------------------

class LoadOrdersWorker(BaseWorker):
    """Worker za učitavanje liste narudžbi."""

    finished = Signal(list)  # list[OrderDTO]

    def __init__(self, customer_filter: Optional[int] = None) -> None:
        super().__init__()
        self._customer_filter = customer_filter

    def run(self) -> None:
        try:
            if self._customer_filter:
                orders = OrderService.get_orders_for_customer(self._customer_filter)
            else:
                orders = OrderService.list_orders()
            self.finished.emit(orders)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Installments Worker
# -----------------------------------------------------------------------------

class LoadInstallmentsWorker(BaseWorker):
    """Worker za učitavanje liste rata."""

    finished = Signal(list)  # list[InstallmentDTO]

    def __init__(
        self,
        filter_type: str = "overdue",
        search: str = "",
        customer_id: Optional[int] = None,
    ) -> None:
        super().__init__()
        self._filter_type = filter_type
        self._search = search
        self._customer_id = customer_id

    def run(self) -> None:
        try:
            installments = PaymentService.get_installments_for_payment(
                filter_type=self._filter_type,
                search=self._search,
                customer_id=self._customer_id,
            )
            self.finished.emit(installments)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Payments Worker
# -----------------------------------------------------------------------------

class LoadPaymentsWorker(BaseWorker):
    """Worker za učitavanje liste uplata (historija za ratu)."""

    finished = Signal(list)  # list[PaymentDTO]

    def __init__(self, installment_id: int) -> None:
        super().__init__()
        self._installment_id = installment_id

    def run(self) -> None:
        try:
            payments = PaymentService.get_payments_for_installment(self._installment_id)
            self.finished.emit(payments)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Campaigns Worker
# -----------------------------------------------------------------------------

class LoadCampaignsWorker(BaseWorker):
    """Worker za učitavanje liste kampanja."""

    finished = Signal(list)  # list[CampaignDTO]

    def run(self) -> None:
        try:
            campaigns = CampaignService.list_campaigns()
            self.finished.emit(campaigns)
        except Exception as exc:
            self.error.emit(str(exc))


# -----------------------------------------------------------------------------
# Campaign Products Worker
# -----------------------------------------------------------------------------

class LoadCampaignProductsWorker(BaseWorker):
    """Worker za učitavanje proizvoda kampanje."""

    finished = Signal(list)  # list[CampaignPriceDTO]

    def __init__(self, campaign_id: int) -> None:
        super().__init__()
        self._campaign_id = campaign_id

    def run(self) -> None:
        try:
            products = CampaignService.list_campaign_products(self._campaign_id)
            self.finished.emit(products)
        except Exception as exc:
            self.error.emit(str(exc))
