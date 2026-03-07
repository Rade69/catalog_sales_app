from __future__ import annotations

from sqlalchemy import func, or_, select

from app.database.database import session_scope
from app.database.models import Customer


class CustomerService:
    @staticmethod
    def list_customers(search_text: str = "") -> list[Customer]:
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
    def create_customer(
        full_name: str,
        phone: str = "",
        city: str = "",
        address: str = "",
        note: str = "",
    ) -> Customer:
        full_name = full_name.strip()
        if not full_name:
            raise ValueError("Ime i prezime je obavezno.")

        with session_scope() as session:
            customer = Customer(
                full_name=full_name,
                phone=phone.strip() or None,
                city=city.strip() or None,
                address=address.strip() or None,
                note=note.strip() or None,
            )
            session.add(customer)
            session.flush()
            session.refresh(customer)
            return customer

    @staticmethod
    def update_customer(
        customer_id: int,
        full_name: str,
        phone: str = "",
        city: str = "",
        address: str = "",
        note: str = "",
    ) -> Customer:
        full_name = full_name.strip()
        if not full_name:
            raise ValueError("Ime i prezime je obavezno.")

        with session_scope() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise ValueError("Kupac nije pronađen.")

            customer.full_name = full_name
            customer.phone = phone.strip() or None
            customer.city = city.strip() or None
            customer.address = address.strip() or None
            customer.note = note.strip() or None
            session.flush()
            session.refresh(customer)
            return customer

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        with session_scope() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise ValueError("Kupac nije pronađen.")
            if customer.orders:
                raise ValueError("Kupac ima vezane narudžbe i ne može se obrisati.")
            session.delete(customer)

    @staticmethod
    def count_customers() -> int:
        with session_scope() as session:
            return session.execute(select(func.count()).select_from(Customer)).scalar_one()
