from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, or_, select

from app.database.database import session_scope
from app.database.models import Customer
from app.dto import CustomerDTO, _to_customer_dto


def validate_customer_input(
    full_name: str,
    phone: str = "",
    city: str = "",
    address: str = "",
    note: str = "",
) -> None:
    """Validira input za kupca."""
    # Validacija imena i prezimena
    full_name = full_name.strip()
    if not full_name:
        raise ValueError("Ime i prezime je obavezno.")
    if len(full_name) > 150:
        raise ValueError("Ime i prezime ne smije biti duže od 150 karaktera.")
    
    # Validacija telefona (opciono)
    phone = phone.strip()
    if phone:
        if len(phone) > 50:
            raise ValueError("Telefon ne smije biti duži od 50 karaktera.")
        
        # Osnovna validacija telefona (brojevi, +, razmaci, zagrade)
        phone_pattern = r'^[\d\s\+\-\(\)\.]+$'
        if not re.match(phone_pattern, phone):
            raise ValueError("Telefon sadrži nedozvoljene karaktere.")
    
    # Validacija grada (opciono)
    city = city.strip()
    if city and len(city) > 100:
        raise ValueError("Grad ne smije biti duži od 100 karaktera.")
    
    # Validacija adrese (opciono)
    address = address.strip()
    if address and len(address) > 200:
        raise ValueError("Adresa ne smije biti duža od 200 karaktera.")
    
    # Validacija napomene (opciono)
    note = note.strip()
    if note and len(note) > 500:
        raise ValueError("Napomena ne smije biti duža od 500 karaktera.")


class CustomerService:
    @staticmethod
    def get_customer(customer_id: int) -> Optional[CustomerDTO]:
        """Dohvaća jednog kupca po ID-u i vraća CustomerDTO."""
        with session_scope() as session:
            customer = session.get(Customer, customer_id)
            if customer is not None:
                return _to_customer_dto(customer)
            return None

    @staticmethod
    def list_customers(search_text: str = "") -> list[CustomerDTO]:
        """Vraća listu CustomerDTO objekata."""
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
    def create_customer(
        full_name: str,
        phone: str = "",
        city: str = "",
        address: str = "",
        note: str = "",
    ) -> CustomerDTO:
        """Kreira novog kupca i vraća CustomerDTO."""
        # Validiraj input
        validate_customer_input(full_name, phone, city, address, note)
        
        # Strip values
        full_name = full_name.strip()
        phone = phone.strip()
        city = city.strip()
        address = address.strip()
        note = note.strip()

        with session_scope() as session:
            customer = Customer(
                full_name=full_name,
                phone=phone or None,
                city=city or None,
                address=address or None,
                note=note or None,
            )
            session.add(customer)
            session.flush()
            session.refresh(customer)
            return _to_customer_dto(customer)

    @staticmethod
    def update_customer(
        customer_id: int,
        full_name: str,
        phone: str = "",
        city: str = "",
        address: str = "",
        note: str = "",
    ) -> CustomerDTO:
        """Ažurira kupca i vraća CustomerDTO."""
        # Validiraj input
        validate_customer_input(full_name, phone, city, address, note)
        
        # Strip values
        full_name = full_name.strip()
        phone = phone.strip()
        city = city.strip()
        address = address.strip()
        note = note.strip()

        with session_scope() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise ValueError("Kupac nije pronađen.")

            customer.full_name = full_name
            customer.phone = phone or None
            customer.city = city or None
            customer.address = address or None
            customer.note = note or None
            session.flush()
            session.refresh(customer)
            return _to_customer_dto(customer)

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        """Briše kupca ako nema vezanih narudžbi."""
        from sqlalchemy import select
        
        with session_scope() as session:
            customer = session.get(Customer, customer_id)
            if customer is None:
                raise ValueError("Kupac nije pronađen.")
            
            # Provjeri ima li narudžbi
            from app.database.models import Order
            orders_count = session.execute(
                select(func.count()).select_from(Order).where(Order.customer_id == customer_id)
            ).scalar_one()
            
            if orders_count > 0:
                raise ValueError(f"Kupac ima {orders_count} vezanih narudžbi i ne može se obrisati.")
            
            session.delete(customer)

    @staticmethod
    def count_customers() -> int:
        """Vraća ukupan broj kupaca."""
        with session_scope() as session:
            return session.execute(select(func.count()).select_from(Customer)).scalar_one()
