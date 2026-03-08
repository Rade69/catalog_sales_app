from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# -----------------------------------------------------------------------------
# Base
# -----------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class OrderStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InstallmentStatus(str, Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class ImportType(str, Enum):
    CAMPAIGN_PRICE_LIST = "campaign_price_list"
    MASTER_PRICE_LIST = "master_price_list"
    CUSTOMER_HISTORY = "customer_history"


class ImportStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductMatchSource(str, Enum):
    SUPPLIER_CODE = "supplier_code"
    NORMALIZED_NAME = "normalized_name"
    NORMALIZED_NAME_AND_BRAND = "normalized_name_and_brand"
    MANUAL = "manual"
    NEW_PRODUCT = "new_product"


# -----------------------------------------------------------------------------
# Mixins
# -----------------------------------------------------------------------------


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


# -----------------------------------------------------------------------------
# Core tables
# -----------------------------------------------------------------------------


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_full_name", "full_name"),
        Index("ix_customers_phone", "phone"),
        Index("ix_customers_city", "city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(120))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    orders: Mapped[list[Order]] = relationship(
        back_populates="customer", cascade="save-update, merge"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} full_name={self.full_name!r}>"


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_name", "name"),
        Index("ix_products_normalized_name", "normalized_name"),
        Index("ix_products_brand", "brand"),
        Index("ix_products_model", "model"),
        Index("ix_products_supplier_code", "supplier_code"),
        Index("ix_products_brand_normalized_name", "brand", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Bitno: supplier_code nije pouzdan kao jedini identitet proizvoda.
    # Može biti prazan, ponovljen ili nečist u Excel fajlovima.
    supplier_code: Mapped[Optional[str]] = mapped_column(String(100))

    # Originalni naziv iz izvora.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Očišćeni naziv za matching prilikom importa.
    # Npr. " Philips  Blender 500W " -> "philips blender 500w"
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)

    brand: Mapped[Optional[str]] = mapped_column(String(120))
    model: Mapped[Optional[str]] = mapped_column(String(150))
    category: Mapped[Optional[str]] = mapped_column(String(120))
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(30))
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    campaign_prices: Mapped[list[CampaignPrice]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="product")
    import_matches: Mapped[list[ImportProductMatch]] = relationship(
        back_populates="product"
    )

    def __repr__(self) -> str:
        return (
            f"<Product id={self.id} name={self.name!r} "
            f"normalized_name={self.normalized_name!r}>"
        )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("name", name="uq_campaigns_name"),
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_date_range", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        SqlEnum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False
    )
    source_excel_filename: Mapped[Optional[str]] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(Text)

    prices: Mapped[list[CampaignPrice]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="campaign")

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} status={self.status.value}>"


class CampaignPrice(TimestampMixin, Base):
    __tablename__ = "campaign_prices"
    __table_args__ = (
        UniqueConstraint("campaign_id", "product_id", name="uq_campaign_product"),
        CheckConstraint("regular_price >= 0", name="ck_campaign_prices_regular_price"),
        CheckConstraint(
            "discount_price IS NULL OR discount_price >= 0",
            name="ck_campaign_prices_discount_price",
        ),
        CheckConstraint("points IS NULL OR points >= 0", name="ck_campaign_prices_points"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)

    regular_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    points: Mapped[Optional[int]] = mapped_column(Integer)
    status_label: Mapped[Optional[str]] = mapped_column(String(50))

    campaign: Mapped[Campaign] = relationship(back_populates="prices")
    product: Mapped[Product] = relationship(back_populates="campaign_prices")

    def effective_price(self) -> Decimal:
        return self.discount_price if self.discount_price is not None else self.regular_price

    def __repr__(self) -> str:
        return (
            f"<CampaignPrice id={self.id} campaign_id={self.campaign_id} "
            f"product_id={self.product_id}>"
        )


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orders_quantity"),
        CheckConstraint("unit_price_snapshot >= 0", name="ck_orders_unit_price_snapshot"),
        CheckConstraint("total_price_snapshot >= 0", name="ck_orders_total_price_snapshot"),
        CheckConstraint(
            "installments_count >= 1 AND installments_count <= 10",
            name="ck_orders_installments_count",
        ),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_campaign_id", "campaign_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_order_date", "order_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    order_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(OrderStatus), default=OrderStatus.ACTIVE, nullable=False
    )

    # Snapshot polja: istorija mora ostati tačna čak i kad se katalog promijeni.
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    product_normalized_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255))
    product_code_snapshot: Mapped[Optional[str]] = mapped_column(String(100))
    product_brand_snapshot: Mapped[Optional[str]] = mapped_column(String(120))
    product_model_snapshot: Mapped[Optional[str]] = mapped_column(String(150))

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    installments_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_due_date: Mapped[Optional[date]] = mapped_column(Date)
    contract_number: Mapped[Optional[str]] = mapped_column(String(50))  # Broj ugovora (historijski uvoz)
    note: Mapped[Optional[str]] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    campaign: Mapped[Campaign] = relationship(back_populates="orders")
    product: Mapped[Optional[Product]] = relationship(back_populates="orders")
    installments: Mapped[list[Installment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} customer_id={self.customer_id} status={self.status.value}>"


class Installment(TimestampMixin, Base):
    __tablename__ = "installments"
    __table_args__ = (
        UniqueConstraint("order_id", "installment_number", name="uq_order_installment_number"),
        CheckConstraint("installment_number >= 1", name="ck_installments_number"),
        CheckConstraint("amount >= 0", name="ck_installments_amount"),
        Index("ix_installments_order_id", "order_id"),
        Index("ix_installments_due_date", "due_date"),
        Index("ix_installments_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[InstallmentStatus] = mapped_column(
        SqlEnum(InstallmentStatus), default=InstallmentStatus.PENDING, nullable=False
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    note: Mapped[Optional[str]] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="installments")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="installment", cascade="all, delete-orphan"
    )

    @property
    def paid_amount(self) -> Decimal:
        return sum((payment.amount for payment in self.payments), Decimal("0.00"))

    @property
    def remaining_amount(self) -> Decimal:
        remaining = Decimal(str(self.amount)) - self.paid_amount
        return remaining if remaining > 0 else Decimal("0.00")

    def __repr__(self) -> str:
        return (
            f"<Installment id={self.id} order_id={self.order_id} "
            f"number={self.installment_number} status={self.status.value}>"
        )


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        Index("ix_payments_installment_id", "installment_id"),
        Index("ix_payments_payment_date", "payment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installment_id: Mapped[int] = mapped_column(
        ForeignKey("installments.id"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

    installment: Mapped[Installment] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} installment_id={self.installment_id} "
            f"amount={self.amount}>"
        )


# -----------------------------------------------------------------------------
# Import audit tables
# -----------------------------------------------------------------------------


class ImportSession(TimestampMixin, Base):
    __tablename__ = "import_sessions"
    __table_args__ = (
        Index("ix_import_sessions_type", "import_type"),
        Index("ix_import_sessions_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_type: Mapped[ImportType] = mapped_column(SqlEnum(ImportType), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        SqlEnum(ImportStatus), default=ImportStatus.STARTED, nullable=False
    )
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_successful: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)

    errors: Mapped[list[ImportErrorLog]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    product_matches: Mapped[list[ImportProductMatch]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ImportSession id={self.id} type={self.import_type.value} "
            f"status={self.status.value}>"
        )


class ImportErrorLog(Base):
    __tablename__ = "import_error_logs"
    __table_args__ = (Index("ix_import_error_logs_session_id", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("import_sessions.id"), nullable=False
    )
    excel_row_number: Mapped[Optional[int]] = mapped_column(Integer)
    field_name: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[ImportSession] = relationship(back_populates="errors")

    def __repr__(self) -> str:
        return f"<ImportErrorLog id={self.id} session_id={self.session_id}>"


class ImportProductMatch(TimestampMixin, Base):
    __tablename__ = "import_product_matches"
    __table_args__ = (
        Index("ix_import_product_matches_session_id", "session_id"),
        Index("ix_import_product_matches_product_id", "product_id"),
        Index("ix_import_product_matches_match_source", "match_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("import_sessions.id"), nullable=False
    )
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"))

    excel_row_number: Mapped[Optional[int]] = mapped_column(Integer)
    raw_supplier_code: Mapped[Optional[str]] = mapped_column(String(100))
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_brand: Mapped[Optional[str]] = mapped_column(String(120))

    match_source: Mapped[ProductMatchSource] = mapped_column(
        SqlEnum(ProductMatchSource), nullable=False
    )
    confidence_note: Mapped[Optional[str]] = mapped_column(Text)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    session: Mapped[ImportSession] = relationship(back_populates="product_matches")
    product: Mapped[Optional[Product]] = relationship(back_populates="import_matches")

    def __repr__(self) -> str:
        return (
            f"<ImportProductMatch id={self.id} session_id={self.session_id} "
            f"match_source={self.match_source.value}>"
        )


# -----------------------------------------------------------------------------
# Cjenovnik (monthly price list)
# -----------------------------------------------------------------------------


class PriceList(TimestampMixin, Base):
    __tablename__ = "price_lists"
    __table_args__ = (
        UniqueConstraint("name", name="uq_price_lists_name"),
        Index("ix_price_lists_name", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    items: Mapped[list[PriceListItem]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PriceList id={self.id} name={self.name!r}>"


class PriceListItem(Base):
    __tablename__ = "price_list_items"
    __table_args__ = (
        Index("ix_price_list_items_price_list_id", "price_list_id"),
        Index("ix_price_list_items_name", "name"),
        Index("ix_price_list_items_brand", "brand"),
        Index("ix_price_list_items_supplier", "supplier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_list_id: Mapped[int] = mapped_column(ForeignKey("price_lists.id"), nullable=False)
    row_number: Mapped[Optional[int]] = mapped_column(Integer)
    supplier_code: Mapped[Optional[str]] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(120))
    supplier: Mapped[Optional[str]] = mapped_column(String(200))  # Naziv firme/dobavljača
    regular_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    discount_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    points: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(100))

    price_list: Mapped[PriceList] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<PriceListItem id={self.id} name={self.name!r}>"


# -----------------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------------


def create_all(engine) -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(engine)
