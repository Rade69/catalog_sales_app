from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignStatus,
    Customer,
    ImportErrorLog,
    ImportSession,
    ImportStatus,
    Installment,
    InstallmentStatus,
    Order,
    OrderStatus,
    Payment,
    Product,
)
from app.importers.history_importer import (
    HistoryImportResult,
    HistoryRow,
    load_history_excel_data,
    normalize_column_name,
)
from dateutil.relativedelta import relativedelta


class HistoryImportService:
    """
    Service layer za import istorijskih podataka.
    
    Importuje narudžbe iz Excel tabele sa već evidentiranim uplatama.
    """

    # ---------------------------------------------------------------------
    # Customer handling
    # ---------------------------------------------------------------------

    @staticmethod
    def _find_or_create_customer(
        session,
        name: str,
        phone: Optional[str],
        city: Optional[str]
    ) -> Tuple[Customer, bool]:
        """
        Pronalazi ili kreira kupca.
        
        Returns:
            Tuple (Customer, is_new)
        """
        # Pokušaj pronaći po imenu i telefonu (ako postoji)
        if phone:
            customer = session.execute(
                select(Customer).where(
                    Customer.full_name == name,
                    Customer.phone == phone
                )
            ).scalars().first()
            
            if customer:
                return customer, False
        
        # Pokušaj samo po imenu
        customer = session.execute(
            select(Customer).where(Customer.full_name == name)
        ).scalars().first()
        
        if customer:
            return customer, False
        
        # Kreiraj novog kupca
        customer = Customer(
            full_name=name,
            phone=phone,
            city=city,
            is_active=True
        )
        session.add(customer)
        session.flush()
        
        return customer, True

    # ---------------------------------------------------------------------
    # Product handling
    # ---------------------------------------------------------------------

    @staticmethod
    def _find_or_create_product(
        session,
        product_name: str
    ) -> Tuple[Product, bool]:
        """
        Pronalazi ili kreira proizvod po nazivu.
        
        Returns:
            Tuple (Product, is_new)
        """
        from app.importers.excel_importer import normalize_product_name
        
        normalized_name = normalize_product_name(product_name)
        
        # Pokušaj pronaći po normalized_name
        product = session.execute(
            select(Product).where(Product.normalized_name == normalized_name)
        ).scalars().first()
        
        if product:
            return product, False
        
        # Kreiraj novi proizvod
        product = Product(
            name=product_name,
            normalized_name=normalized_name,
            is_active=True
        )
        session.add(product)
        session.flush()
        
        return product, True

    # ---------------------------------------------------------------------
    # Campaign handling
    # ---------------------------------------------------------------------

    @staticmethod
    def _get_or_create_history_campaign(session) -> Campaign:
        """
        Dohvaća ili kreira default kampanju za istorijske podatke.
        """
        campaign = session.execute(
            select(Campaign).where(Campaign.name == "Istorija - import")
        ).scalars().first()
        
        if campaign:
            return campaign
        
        # Kreiraj kampanju za istoriju
        campaign = Campaign(
            name="Istorija - import",
            start_date=date(2020, 1, 1),
            end_date=date(2030, 12, 31),
            status=CampaignStatus.ARCHIVED,
            note="Kampanja kreirana automatski za import istorijskih podataka"
        )
        session.add(campaign)
        session.flush()
        
        return campaign

    # ---------------------------------------------------------------------
    # Order handling
    # ---------------------------------------------------------------------

    @staticmethod
    def _create_order(
        session,
        customer: Customer,
        product: Product,
        price: Decimal,
        installments_count: int,
        campaign: Campaign
    ) -> Order:
        """
        Kreira narudžbu sa snapshot podacima.
        """
        order = Order(
            customer_id=customer.id,
            campaign_id=campaign.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            product_normalized_name_snapshot=product.normalized_name,
            product_brand_snapshot=product.brand,
            unit_price_snapshot=price,
            total_price_snapshot=price,
            installments_count=installments_count,
            status=OrderStatus.COMPLETED,  # Istorija = completed
            first_due_date=date.today()
        )
        session.add(order)
        session.flush()
        
        return order

    # ---------------------------------------------------------------------
    # Installment handling
    # ---------------------------------------------------------------------

    @staticmethod
    def _generate_installments(
        session,
        order: Order,
        total_price: Decimal,
        count: int
    ) -> List[Installment]:
        """
        Generiše rate za narudžbu.
        Posljednja rata se koriguje zbog zaokruživanja.
        """
        # Osnovna rata
        base_installment = (total_price / count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Ukupno od prvih (count-1) rata
        first_n_total = base_installment * (count - 1)
        
        # Zadnja rata
        last_installment = total_price - first_n_total
        
        today = date.today()
        installments: List[Installment] = []
        
        for i in range(count):
            if i < count - 1:
                amount = base_installment
            else:
                amount = last_installment
            
            installment = Installment(
                order_id=order.id,
                installment_number=i + 1,
                amount=amount,
                due_date=today + relativedelta(months=i + 1),
                status=InstallmentStatus.PENDING
            )
            session.add(installment)
            installments.append(installment)
        
        return installments

    @staticmethod
    def _mark_installment_as_paid(
        session,
        installment: Installment,
        payment_date: Optional[date] = None
    ) -> Payment:
        """
        Označava ratu kao plaćenu kreiranjem Payment zapisa.
        """
        payment = Payment(
            installment_id=installment.id,
            payment_date=payment_date or date.today(),
            amount=installment.amount,
            note="Import iz istorije"
        )
        session.add(payment)
        
        # Ažuriraj status rate
        installment.status = InstallmentStatus.PAID
        installment.paid_at = datetime.now()
        
        return payment

    # ---------------------------------------------------------------------
    # Main import
    # ---------------------------------------------------------------------

    @staticmethod
    def import_history_from_excel(
        excel_path: str | Path
    ) -> HistoryImportResult:
        """
        Importuje istorijske podatke iz Excel fajla.
        
        Args:
            excel_path: Putanja do Excel fajla
        
        Returns:
            HistoryImportResult sa statistikom importa
        """
        excel_path = Path(excel_path)
        
        # Kreiraj import sesiju
        with session_scope() as session:
            import_session = ImportSession(
                import_type="customer_history",
                source_filename=excel_path.name,
                status=ImportStatus.STARTED
            )
            session.add(import_session)
            session.flush()
            session_id = import_session.id
        
        # Učitaj i parsiraj Excel
        rows, mapped, load_errors = load_history_excel_data(excel_path)
        
        # Loguj greške iz učitavanja
        with session_scope() as session:
            for err in load_errors:
                error_log = ImportErrorLog(
                    session_id=session_id,
                    excel_row_number=err["row"],
                    field_name="customer" if "kupac" in err["error"].lower() else "product",
                    error_message=err["error"]
                )
                session.add(error_log)
        
        # Procesuiraj redove
        customers_created = 0
        orders_created = 0
        installments_created = 0
        payments_created = 0
        skipped_rows = len(load_errors)
        
        with session_scope() as session:
            # Dohvati ili kreiraj kampanju za istoriju
            campaign = HistoryImportService._get_or_create_history_campaign(session)
            
            # Procesuiraj svaki red
            for row in rows:
                try:
                    # 1. Pronađi ili kreiraj kupca
                    customer, is_new_customer = HistoryImportService._find_or_create_customer(
                        session=session,
                        name=row.customer_name,
                        phone=row.customer_phone,
                        city=row.customer_city
                    )
                    if is_new_customer:
                        customers_created += 1
                    
                    # 2. Pronađi ili kreiraj proizvod
                    product, is_new_product = HistoryImportService._find_or_create_product(
                        session=session,
                        product_name=row.product_name
                    )
                    
                    # 3. Kreiraj narudžbu
                    order = HistoryImportService._create_order(
                        session=session,
                        customer=customer,
                        product=product,
                        price=row.price,
                        installments_count=row.installments_count,
                        campaign=campaign
                    )
                    orders_created += 1
                    
                    # 4. Generiši rate
                    installments = HistoryImportService._generate_installments(
                        session=session,
                        order=order,
                        total_price=row.price,
                        count=row.installments_count
                    )
                    installments_created += len(installments)
                    
                    # 5. Označi uplaćene rate
                    for paid_num in row.paid_installments:
                        if paid_num <= len(installments):
                            installment = installments[paid_num - 1]
                            HistoryImportService._mark_installment_as_paid(
                                session=session,
                                installment=installment
                            )
                            payments_created += 1
                    
                except Exception as e:
                    # Loguj grešku
                    error_log = ImportErrorLog(
                        session_id=session_id,
                        excel_row_number=row.row_number,
                        field_name="order",
                        error_message=str(e)
                    )
                    session.add(error_log)
                    skipped_rows += 1
            
            # Ažuriraj import sesiju
            import_session = session.get(ImportSession, session_id)
            import_session.rows_total = len(rows) + len(load_errors)
            import_session.rows_successful = orders_created
            import_session.rows_failed = skipped_rows
            import_session.status = ImportStatus.COMPLETED
            import_session.message = (
                f"Import uspješan: {customers_created} kupaca, "
                f"{orders_created} narudžbi, {payments_created} uplata"
            )
        
        return HistoryImportResult(
            total_rows=len(rows) + len(load_errors),
            customers_created=customers_created,
            orders_created=orders_created,
            installments_created=installments_created,
            payments_created=payments_created,
            skipped_rows=skipped_rows,
            errors=load_errors
        )

    @staticmethod
    def get_import_session(session_id: int) -> Optional[ImportSession]:
        """
        Dohvaća detalje import sesije.
        """
        with session_scope() as session:
            imp_session = session.get(ImportSession, session_id)
            if imp_session:
                session.refresh(imp_session, ["errors"])
            return imp_session
