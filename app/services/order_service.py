from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignStatus,
    Customer,
    Installment,
    Order,
    OrderStatus,
)
from datetime import date
from dateutil.relativedelta import relativedelta

from app.dto import OrderDTO, CustomerDTO, CampaignDTO, _to_order_dto, _to_customer_dto, _to_campaign_dto
from app.services.installment_service import InstallmentService


class OrderService:
    """Service layer za upravljanje narudžbama."""

    @staticmethod
    def has_active_campaign() -> bool:
        """Vraća True ako postoji barem jedna aktivna kampanja."""
        with session_scope() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
            ).scalars().first()
            return campaign is not None

    @staticmethod
    def list_customers(search_text: str = "") -> List[CustomerDTO]:
        """Vraća listu CustomerDTO za dropdown."""
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
            return [_to_customer_dto(c) for c in customers]

    @staticmethod
    def get_default_campaign() -> Optional[CampaignDTO]:
        """Vraća prvu aktivnu kampanju ili bilo koju kampanju kao CampaignDTO."""
        with session_scope() as session:
            stmt = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
            campaign = session.execute(stmt).scalars().first()
            if not campaign:
                stmt = select(Campaign)
                campaign = session.execute(stmt).scalars().first()
            return _to_campaign_dto(campaign) if campaign else None

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
        except (ValueError, TypeError, AttributeError, Exception):
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
        campaign_id: Optional[int] = None,
        contract_number: Optional[str] = None,
    ) -> OrderDTO:
        """
        Kreira novu narudžbu sa automatski generisanim ratama i vraća OrderDTO.

        Args:
            customer_id: ID kupca
            product_name: Naziv proizvoda (snapshot)
            price: Cijena kao string (može biti sa zarezom)
            installments: Broj rata (1-10)
            campaign_id: ID kampanje (opciono, koristi se default ako nije navedeno)
            contract_number: Broj ugovora (opciono)

        Returns:
            OrderDTO kreirane narudžbe

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
                first_due_date=date.today() + relativedelta(months=1),
                contract_number=contract_number.strip() if contract_number else None,
            )

            session.add(order)
            session.flush()

            # Generiši rate koristeći InstallmentService i dodaj ih u sesiju
            installments = InstallmentService.generate_for_order(order)
            for inst in installments:
                session.add(inst)

            session.flush()

            # Konvertuj u DTO prije zatvaranja sesije
            return _to_order_dto(order)

    @staticmethod
    def list_orders(customer_filter: Optional[int] = None) -> List[OrderDTO]:
        """
        Vraća listu svih narudžbi kao OrderDTO, opciono filtrirano po kupcu.
        """
        with session_scope() as session:
            stmt = (
                select(Order)
                .options(
                    selectinload(Order.customer),
                    selectinload(Order.installments),
                )
                .order_by(Order.order_date.desc())
            )
            if customer_filter:
                stmt = stmt.where(Order.customer_id == customer_filter)
            orders = list(session.execute(stmt).scalars().all())
            return [_to_order_dto(order, include_installment_order_data=True) for order in orders]

    @staticmethod
    def get_order_details(order_id: int) -> Optional[OrderDTO]:
        """
        Vraća detalje narudžbe sa ratama kao OrderDTO.
        """
        with session_scope() as session:
            stmt = (
                select(Order)
                .options(
                    joinedload(Order.customer),
                    selectinload(Order.installments),
                )
                .where(Order.id == order_id)
            )
            order = session.execute(stmt).unique().scalar_one_or_none()

            if order is not None:
                return _to_order_dto(order, include_installment_order_data=True)
            return None

    @staticmethod
    def delete_order(order_id: int) -> bool:
        """
        Briše narudžbu i sve pripadajuće rate i uplate.

        Args:
            order_id: ID narudžbe za brisanje

        Returns:
            True ako je brisanje uspješno

        Raises:
            ValueError: Ako narudžba ne postoji
        """
        with session_scope() as session:
            order = session.get(Order, order_id)
            if order is None:
                raise ValueError(f"Narudžba #{order_id} nije pronađena.")

            # Prvo obriši sve uplate povezane sa ratama
            for installment in order.installments:
                for payment in installment.payments:
                    session.delete(payment)

            # Zatim obriši sve rate
            for installment in order.installments:
                session.delete(installment)

            # Na kraju obriši narudžbu
            session.delete(order)

            return True

    @staticmethod
    def get_orders_for_customer(customer_id: int) -> List[OrderDTO]:
        """
        Vraća sve narudžbe za odabranog kupca kao OrderDTO,
        sortirano od najnovije ka najstarijoj.
        """
        with session_scope() as session:
            stmt = (
                select(Order)
                .options(
                    selectinload(Order.installments).selectinload(Installment.payments)
                )
                .where(Order.customer_id == customer_id)
                .order_by(Order.order_date.desc())
            )
            orders = list(session.execute(stmt).scalars().all())
            return [_to_order_dto(order, include_installment_order_data=True) for order in orders]

    @staticmethod
    def update_contract_number(order_id: int, contract_number: Optional[str]) -> None:
        """
        Ažurira broj ugovora za narudžbu.

        Args:
            order_id: ID narudžbe
            contract_number: Novi broj ugovora (ili None za brisanje)
        """
        with session_scope() as session:
            order = session.get(Order, order_id)
            if order:
                order.contract_number = contract_number
                session.commit()
