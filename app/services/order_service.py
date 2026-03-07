from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignStatus,
    Customer,
    Installment,
    InstallmentStatus,
    Order,
    OrderStatus,
)
from datetime import date
from dateutil.relativedelta import relativedelta

from app.services.installment_service import InstallmentService


class OrderService:
    """Service layer za upravljanje narudžbama."""

    @staticmethod
    def list_customers(search_text: str = "") -> List[Customer]:
        """Vraća listu kupaca za dropdown."""
        from sqlalchemy import or_

        with session_scope() as session:
            stmt = select(Customer).order_by(Customer.full_name.asc())
            search = search_text.strip()
            if search:
                like = f"%{search}%"
                stmt = stmt.where(
                    or_(
                        Customer.full_name.ilike(like),
                        Customer.phone.ilike(like),
                        Customer.city.ilike(like),
                    )
                )
            customers = list(session.execute(stmt).scalars().all())
            # Expunge za pristup van sesije
            for c in customers:
                session.expunge(c)
            return customers

    @staticmethod
    def get_default_campaign() -> Optional[Campaign]:
        """Vraća prvu aktivnu kampanju ili bilo koju kampanju."""
        with session_scope() as session:
            stmt = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
            campaign = session.execute(stmt).scalars().first()
            if not campaign:
                stmt = select(Campaign)
                campaign = session.execute(stmt).scalars().first()
            return campaign

    @staticmethod
    def validate_order_input(
        customer_id: Optional[int],
        product_name: str,
        price: str,
        installments: int
    ) -> Tuple[bool, str]:
        """
        Validira unos za narudžbu.
        Vraća (success, error_message).
        """
        if not customer_id:
            return False, "Obavezno odabrati kupca."

        if not product_name or not product_name.strip():
            return False, "Obavezno unijeti naziv proizvoda."

        try:
            price_val = Decimal(price.replace(",", ".").strip())
            if price_val <= 0:
                return False, "Cijena mora biti veća od 0."
        except (ValueError, TypeError, AttributeError):
            return False, "Neispravna cijena."

        if installments < 1 or installments > 10:
            return False, "Broj rata mora biti između 1 i 10."

        return True, ""

    @staticmethod
    def create_order(
        customer_id: int,
        product_name: str,
        price: str,
        installments: int,
        campaign_id: Optional[int] = None
    ) -> Order:
        """
        Kreira novu narudžbu sa automatski generisanim ratama.

        Args:
            customer_id: ID kupca
            product_name: Naziv proizvoda (snapshot)
            price: Cijena kao string (može biti sa zarezom)
            installments: Broj rata (1-10)
            campaign_id: ID kampanje (opciono, koristi se default ako nije navedeno)

        Returns:
            Kreirani Order objekat

        Raises:
            ValueError: Ako validacija ne uspije
        """
        # Validacija
        success, error = OrderService.validate_order_input(
            customer_id, product_name, price, installments
        )
        if not success:
            raise ValueError(error)

        # Parsiranje cijene
        price_decimal = Decimal(price.replace(",", ".").strip())

        with session_scope() as session:
            # Dohvati kampanju
            if campaign_id is None:
                campaign = OrderService.get_default_campaign()
                if campaign is None:
                    raise ValueError(
                        "Nema dostupne kampanje. Kreirajte kampanju prije narudžbe."
                    )
                campaign_id = campaign.id

            # Kreiraj narudžbu
            order = Order(
                customer_id=customer_id,
                campaign_id=campaign_id,
                product_name_snapshot=product_name.strip(),
                unit_price_snapshot=price_decimal,
                total_price_snapshot=price_decimal,
                installments_count=installments,
                status=OrderStatus.ACTIVE,
                first_due_date=date.today() + relativedelta(months=1)
            )

            session.add(order)
            session.flush()  # Dohvati ID prije commita

            # Generiši rate koristeći InstallmentService
            InstallmentService.generate_for_order(order)

            session.refresh(order)
            return order

    @staticmethod
    def list_orders(customer_filter: Optional[int] = None) -> List[Order]:
        """
        Vraća listu svih narudžbi, opciono filtrirano po kupcu.
        """
        with session_scope() as session:
            stmt = select(Order).order_by(Order.order_date.desc())
            if customer_filter:
                stmt = stmt.where(Order.customer_id == customer_filter)
            orders = list(session.execute(stmt).scalars().all())

            # Učitaj relacione podatke
            for order in orders:
                _ = order.customer  # eager load customer
                _ = order.installments  # eager load installments

            return orders

    @staticmethod
    def get_order_details(order_id: int) -> Optional[Order]:
        """
        Vraća detalje narudžbe sa ratama.
        """
        with session_scope() as session:
            order = session.get(Order, order_id)
            if order:
                session.refresh(order, ["customer", "installments"])
            return order
