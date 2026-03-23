"""
Data Transfer Objects (DTO) za Catalog Sales App.

DTO-ovi eliminišu potrebu za session.expunge() pattern-om tako što
kopiraju podatke iz ORM objekata u obične dataclasses prije zatvaranja sesije.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CustomerDTO:
    """DTO za Customer model."""
    id: int
    full_name: str
    phone: Optional[str]
    city: Optional[str]
    address: Optional[str]
    note: Optional[str]
    is_active: bool


@dataclass
class ProductDTO:
    """DTO za Product model."""
    id: int
    name: str
    normalized_name: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    supplier_code: Optional[str]
    category: Optional[str]
    unit_of_measure: Optional[str]
    note: Optional[str]
    is_active: bool


@dataclass
class CampaignDTO:
    """DTO za Campaign model."""
    id: int
    name: str
    start_date: date
    end_date: date
    status: str  # 'draft', 'active', 'archived'
    source_excel_filename: Optional[str]
    note: Optional[str]


@dataclass
class InstallmentDTO:
    """
    DTO za Installment model.
    
    Sadrži i izračunate vrijednosti (paid_amount, remaining_amount)
    da bi se izbjeglo ponovno računanje u GUI-u.
    
    TAKOĐER sadrži denormalizovane podatke o narudžbi i kupcu
    da bi se izbjegao pristup ORM relacijama.
    """
    id: int
    order_id: int
    installment_number: int
    due_date: date
    amount: Decimal
    status: str  # 'pending', 'partially_paid', 'paid', 'overdue', 'cancelled'
    paid_at: Optional[datetime]
    note: Optional[str]
    
    # Denormalizovani podaci o narudžbi (izbjegava N+1 problem)
    order_customer_name: str = ""  # Iz Order.customer.full_name
    order_product_name: str = ""   # Iz Order.product_name_snapshot
    order_total_price: Decimal = field(default_factory=lambda: Decimal("0.00"))  # Iz Order.total_price_snapshot
    order_installments_count: int = 0  # Iz Order.installments_count
    
    # Izračunate vrijednosti
    paid_amount: Decimal = field(default_factory=lambda: Decimal("0.00"))
    remaining_amount: Decimal = field(default_factory=lambda: Decimal("0.00"))


@dataclass
class PaymentDTO:
    """DTO za Payment model."""
    id: int
    installment_id: int
    payment_date: date
    amount: Decimal
    note: Optional[str]


@dataclass
class OrderDTO:
    """
    DTO za Order model.
    
    Sadrži denormalizovane podatke o kupcu (customer_name) da bi se
    izbjegao N+1 problem pri pristupu order.customer.full_name.
    """
    id: int
    customer_id: int
    customer_name: str  # Denormalizovano iz Customer.full_name
    campaign_id: int
    order_date: date
    status: str  # 'active', 'completed', 'cancelled'
    product_name_snapshot: str
    product_normalized_name_snapshot: Optional[str]
    product_code_snapshot: Optional[str]
    product_brand_snapshot: Optional[str]
    product_model_snapshot: Optional[str]
    quantity: int
    unit_price_snapshot: Decimal
    total_price_snapshot: Decimal
    installments_count: int
    first_due_date: Optional[date]
    contract_number: Optional[str]
    note: Optional[str]
    
    # Ugniježđeni DTO-ovi
    installments: list[InstallmentDTO] = field(default_factory=list)


@dataclass
class PriceListItemDTO:
    """DTO za PriceListItem model."""
    id: int
    price_list_id: int
    row_number: Optional[int]
    supplier_code: Optional[str]
    name: str
    brand: Optional[str]
    supplier: Optional[str]
    regular_price: Optional[Decimal]
    discount_price: Optional[Decimal]
    points: Optional[int]
    status: Optional[str]


@dataclass
class CampaignPriceDTO:
    """DTO za CampaignPrice model."""
    id: int
    campaign_id: int
    product_id: int
    regular_price: Decimal
    discount_price: Optional[Decimal]
    points: Optional[int]
    status_label: Optional[str]
    
    # Izračunata vrijednost
    @property
    def effective_price(self) -> Decimal:
        return self.discount_price if self.discount_price is not None else self.regular_price


# -----------------------------------------------------------------------------
# Helper funkcije za konverziju ORM → DTO
# -----------------------------------------------------------------------------

def _to_customer_dto(customer) -> CustomerDTO:
    """Konvertuje SQLAlchemy Customer objekat u CustomerDTO."""
    return CustomerDTO(
        id=customer.id,
        full_name=customer.full_name,
        phone=customer.phone,
        city=customer.city,
        address=customer.address,
        note=customer.note,
        is_active=customer.is_active,
    )


def _to_product_dto(product) -> ProductDTO:
    """Konvertuje SQLAlchemy Product objekat u ProductDTO."""
    return ProductDTO(
        id=product.id,
        name=product.name,
        normalized_name=product.normalized_name,
        brand=product.brand,
        model=product.model,
        supplier_code=product.supplier_code,
        category=product.category,
        unit_of_measure=product.unit_of_measure,
        note=product.note,
        is_active=product.is_active,
    )


def _to_campaign_dto(campaign) -> CampaignDTO:
    """Konvertuje SQLAlchemy Campaign objekat u CampaignDTO."""
    status_value = campaign.status.value if hasattr(campaign.status, 'value') else str(campaign.status)
    return CampaignDTO(
        id=campaign.id,
        name=campaign.name,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        status=status_value,
        source_excel_filename=campaign.source_excel_filename,
        note=campaign.note,
    )


def _to_installment_dto(installment, include_order_data: bool = False) -> InstallmentDTO:
    """
    Konvertuje SQLAlchemy Installment objekat u InstallmentDTO.
    
    Automatski računa paid_amount i remaining_amount.
    
    Args:
        installment: SQLAlchemy Installment objekat
        include_order_data: Ako je True, uključi denormalizovane podatke o narudžbi
                          (zahtijeva da je order sa customer učitan)
    """
    paid_amount = sum(
        (Decimal(str(payment.amount)) for payment in installment.payments),
        Decimal("0.00")
    )
    remaining = max(Decimal("0.00"), Decimal(str(installment.amount)) - paid_amount)
    
    status_value = installment.status.value if hasattr(installment.status, 'value') else str(installment.status)
    
    # Denormalizovani podaci o narudžbi
    order_customer_name = ""
    order_product_name = ""
    order_total_price = Decimal("0.00")
    order_installments_count = 0
    
    if include_order_data:
        order = getattr(installment, 'order', None)
        if order:
            customer = getattr(order, 'customer', None)
            order_customer_name = customer.full_name if customer else ""
            order_product_name = order.product_name_snapshot
            order_total_price = Decimal(str(order.total_price_snapshot))
            order_installments_count = order.installments_count
    
    return InstallmentDTO(
        id=installment.id,
        order_id=installment.order_id,
        installment_number=installment.installment_number,
        due_date=installment.due_date,
        amount=Decimal(str(installment.amount)),
        status=status_value,
        paid_at=installment.paid_at,
        note=installment.note,
        paid_amount=paid_amount,
        remaining_amount=remaining,
        order_customer_name=order_customer_name,
        order_product_name=order_product_name,
        order_total_price=order_total_price,
        order_installments_count=order_installments_count,
    )


def _to_payment_dto(payment) -> PaymentDTO:
    """Konvertuje SQLAlchemy Payment objekat u PaymentDTO."""
    return PaymentDTO(
        id=payment.id,
        installment_id=payment.installment_id,
        payment_date=payment.payment_date,
        amount=Decimal(str(payment.amount)),
        note=payment.note,
    )


def _to_order_dto(order, include_installment_order_data: bool = False) -> OrderDTO:
    """
    Konvertuje SQLAlchemy Order objekat u OrderDTO.
    
    Pretpostavlja da su installments već učitani (joinedload/selectinload).
    
    Args:
        order: SQLAlchemy Order objekat
        include_installment_order_data: Ako je True, uključi denormalizovane podatke
                                       o narudžbi u svaki InstallmentDTO
    """
    status_value = order.status.value if hasattr(order.status, 'value') else str(order.status)
    
    # Denormalizuj customer ime
    customer_name = order.customer.full_name if order.customer else "N/A"
    
    # Konvertuj installments - proslijedi order podatke za denormalizaciju
    installments = []
    for inst in order.installments:
        # Privremeno dodaj order referencu za _to_installment_dto
        inst.order = order
        inst._cached_customer = order.customer
        dto = _to_installment_dto(inst, include_order_data=include_installment_order_data)
        installments.append(dto)
    
    return OrderDTO(
        id=order.id,
        customer_id=order.customer_id,
        customer_name=customer_name,
        campaign_id=order.campaign_id,
        order_date=order.order_date,
        status=status_value,
        product_name_snapshot=order.product_name_snapshot,
        product_normalized_name_snapshot=order.product_normalized_name_snapshot,
        product_code_snapshot=order.product_code_snapshot,
        product_brand_snapshot=order.product_brand_snapshot,
        product_model_snapshot=order.product_model_snapshot,
        quantity=order.quantity,
        unit_price_snapshot=Decimal(str(order.unit_price_snapshot)),
        total_price_snapshot=Decimal(str(order.total_price_snapshot)),
        installments_count=order.installments_count,
        first_due_date=order.first_due_date,
        contract_number=order.contract_number,
        note=order.note,
        installments=installments,
    )


def _to_price_list_item_dto(item) -> PriceListItemDTO:
    """Konvertuje SQLAlchemy PriceListItem objekat u PriceListItemDTO."""
    return PriceListItemDTO(
        id=item.id,
        price_list_id=item.price_list_id,
        row_number=item.row_number,
        supplier_code=item.supplier_code,
        name=item.name,
        brand=item.brand,
        supplier=item.supplier,
        regular_price=Decimal(str(item.regular_price)) if item.regular_price else None,
        discount_price=Decimal(str(item.discount_price)) if item.discount_price else None,
        points=item.points,
        status=item.status,
    )


def _to_campaign_price_dto(campaign_price) -> CampaignPriceDTO:
    """Konvertuje SQLAlchemy CampaignPrice objekat u CampaignPriceDTO."""
    return CampaignPriceDTO(
        id=campaign_price.id,
        campaign_id=campaign_price.campaign_id,
        product_id=campaign_price.product_id,
        regular_price=Decimal(str(campaign_price.regular_price)),
        discount_price=Decimal(str(campaign_price.discount_price)) if campaign_price.discount_price else None,
        points=campaign_price.points,
        status_label=campaign_price.status_label,
    )
