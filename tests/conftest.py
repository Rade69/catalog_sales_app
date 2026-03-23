"""
Pytest konfiguracioni fajl za catalog_sales_app.

Sadrži fixture-ove za:
- In-memory SQLite bazu za svaki test
- SessionLocal override da koristi test bazu
- Automatsko kreiranje svih tabela
- Čišćenje posle svakog testa
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Customer, Campaign, CampaignStatus, Order, Installment, Payment
from app.database import database


@pytest.fixture(scope="function")
def test_engine():
    """
    Kreira in-memory SQLite engine za testove.
    
    Koristi:
    - :memory: SQLite bazu u memoriji
    - StaticPool da bi sesija delila istu konekciju
    - check_same_thread=False za SQLite
    """
    from sqlalchemy.pool import StaticPool
    
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    
    # Postavi SQLite pragme za testove
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Kreiraj sve tabele
    Base.metadata.create_all(bind=engine)
    
    yield engine


@pytest.fixture(scope="function")
def test_session(test_engine):
    """
    Kreira novu sesiju za svaki test.
    """
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )
    
    session = TestingSessionLocal()
    session.begin()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def override_database(test_engine, test_session):
    """
    Override-uje i session_scope() i SessionLocal da koriste test engine.
    
    Ovo je ključno jer servisi koriste session_scope() iz database.py.
    """
    from contextlib import contextmanager
    
    # Kreiraj TestingSessionLocal
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )
    
    @contextmanager
    def test_session_scope():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            if session.is_active:
                session.rollback()
            raise
        finally:
            session.close()
    
    # Sačuvaj originale
    original_session_scope = database.session_scope
    original_session_local = database.SessionLocal
    
    # Override-uj
    database.session_scope = test_session_scope
    database.SessionLocal = TestingSessionLocal
    
    yield
    
    # Vrati originale
    database.session_scope = original_session_scope
    database.SessionLocal = original_session_local


@pytest.fixture(scope="function")
def db(test_engine, override_database, test_session):
    """
    Glavni fixture za testove.
    
    Korišćenje:
        def test_something(db):
            # db je test_session
            # session_scope() i SessionLocal su override-ovani
    """
    yield test_session


@pytest.fixture
def sample_customer(db):
    """Kreira sample kupca za testove."""
    customer = Customer(
        full_name="Test Kupac",
        phone="061123456",
        city="Sarajevo",
        address="Testna 1",
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@pytest.fixture
def sample_campaign(db):
    """Kreira sample kampanju za testove."""
    from datetime import date
    
    campaign = Campaign(
        name="Test Kampanja",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status=CampaignStatus.ACTIVE,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@pytest.fixture
def sample_order(db, sample_customer, sample_campaign):
    """Kreira sample narudžbu sa ratama za testove."""
    from datetime import date, timedelta
    from decimal import Decimal
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.database.models import OrderStatus
    from app.services.installment_service import InstallmentService
    
    order = Order(
        customer_id=sample_customer.id,
        campaign_id=sample_campaign.id,
        product_name_snapshot="Test Proizvod",
        unit_price_snapshot=Decimal("100.00"),
        total_price_snapshot=Decimal("100.00"),
        installments_count=2,
        status=OrderStatus.ACTIVE,
        first_due_date=date.today() + timedelta(days=30),
    )
    db.add(order)
    db.flush()
    
    # Kreiraj rate koristeći InstallmentService
    installments = InstallmentService.generate_for_order(order)
    for inst in installments:
        db.add(inst)
    
    db.commit()
    
    # Eksplicitno učitaj order sa ratama koristeći joinedload
    stmt = select(Order).options(joinedload(Order.installments)).where(Order.id == order.id)
    order = db.execute(stmt).unique().scalars().first()
    
    return order
