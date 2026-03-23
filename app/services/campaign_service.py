from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.database import session_scope
from app.database.models import (
    Campaign,
    CampaignPrice,
    CampaignStatus,
    ImportErrorLog,
    ImportProductMatch,
    ImportSession,
    ImportStatus,
    Product,
    ProductMatchSource,
)
from app.dto import CampaignDTO, CampaignPriceDTO, ProductDTO, _to_campaign_dto, _to_campaign_price_dto, _to_product_dto
from app.importers.excel_importer import (
    ExcelRow,
    ImportResult,
    load_excel_data,
    normalize_product_name,
)


@dataclass
class ProductMatch:
    """Rezultat match-a proizvoda."""
    product: Product
    source: ProductMatchSource
    confidence_note: str
    requires_review: bool


class CampaignService:
    """Service layer za upravljanje kampanjama i import."""

    # ---------------------------------------------------------------------
    # Campaign CRUD
    # ---------------------------------------------------------------------

    @staticmethod
    def create_campaign(
        name: str,
        start_date: date,
        end_date: date,
        note: Optional[str] = None
    ) -> CampaignDTO:
        """
        Kreira novu kampanju i vraća CampaignDTO.

        Args:
            name: Naziv kampanje (mora biti jedinstven)
            start_date: Datum početka
            end_date: Datum završetka
            note: Opciona napomena

        Returns:
            CampaignDTO kreirane kampanje

        Raises:
            ValueError: Ako kampanja sa istim imenom već postoji
        """
        name = name.strip()
        if not name:
            raise ValueError("Naziv kampanje je obavezan.")

        if start_date > end_date:
            raise ValueError("Datum početka mora biti prije datuma završetka.")

        with session_scope() as session:
            # Provjeri da li kampanja već postoji
            existing = session.execute(
                select(Campaign).where(Campaign.name == name)
            ).scalars().first()

            if existing:
                raise ValueError(
                    f"Kampanja sa nazivom '{name}' već postoji."
                )

            campaign = Campaign(
                name=name,
                start_date=start_date,
                end_date=end_date,
                status=CampaignStatus.DRAFT,
                note=note
            )

            session.add(campaign)
            session.flush()

            # Vrati DTO prije zatvaranja sesije
            return _to_campaign_dto(campaign)

    @staticmethod
    def get_campaign_by_name(name: str) -> Optional[CampaignDTO]:
        """
        Dohvaća kampanju po nazivu i vraća CampaignDTO.
        """
        with session_scope() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.name == name)
            ).scalars().first()
            return _to_campaign_dto(campaign) if campaign else None

    @staticmethod
    def list_campaigns() -> List[CampaignDTO]:
        """
        Vraća listu svih kampanja kao CampaignDTO.
        """
        with session_scope() as session:
            campaigns = list(
                session.execute(
                    select(Campaign).order_by(Campaign.start_date.desc())
                ).scalars().all()
            )
            return [_to_campaign_dto(c) for c in campaigns]

    @staticmethod
    def list_campaign_products(campaign_id: int) -> List[CampaignPriceDTO]:
        """
        Vraća listu CampaignPriceDTO za datu kampanju.
        """
        with session_scope() as session:
            prices = list(
                session.execute(
                    select(CampaignPrice)
                    .options(selectinload(CampaignPrice.product))
                    .where(CampaignPrice.campaign_id == campaign_id)
                    .order_by(CampaignPrice.id.asc())
                ).scalars().all()
            )
            return [_to_campaign_price_dto(cp) for cp in prices]

    # ---------------------------------------------------------------------
    # Product matching
    # ---------------------------------------------------------------------

    @staticmethod
    def _find_product_by_supplier_code(
        session,
        supplier_code: str
    ) -> Optional[Product]:
        """
        Traži proizvod po supplier_code (tačan match).
        """
        return session.execute(
            select(Product).where(Product.supplier_code == supplier_code)
        ).scalars().first()

    @staticmethod
    def _find_product_by_normalized_name(
        session,
        normalized_name: str
    ) -> Optional[Product]:
        """
        Traži proizvod po normalized_name (tačan match).
        """
        return session.execute(
            select(Product).where(Product.normalized_name == normalized_name)
        ).scalars().first()

    @staticmethod
    def _find_product_by_name_and_brand(
        session,
        normalized_name: str,
        brand: Optional[str]
    ) -> Optional[Product]:
        """
        Traži proizvod po normalized_name + brand.
        """
        if not brand:
            return None
        
        normalized_brand = normalize_product_name(brand)
        
        return session.execute(
            select(Product).where(
                Product.normalized_name == normalized_name,
                Product.brand == brand
            )
        ).scalars().first()

    @staticmethod
    def find_or_create_product(
        session,
        supplier_code: Optional[str],
        product_name: str,
        brand: Optional[str],
        session_id: int,
        excel_row_number: int
    ) -> Tuple[Product, ProductMatch]:
        """
        Pronalazi ili kreira proizvod.
        
        Logika:
        1. ako postoji supplier_code → traži po šifri
        2. ako ne postoji → pokušaj match po normalized_name
        3. ako postoji brand → pokušaj normalized_name + brand
        4. ako nema poklapanja → kreiraj novi proizvod
        
        Returns:
            Tuple (Product, ProductMatch)
        """
        normalized_name = normalize_product_name(product_name)
        
        # 1. Pokušaj match po supplier_code
        if supplier_code:
            product = CampaignService._find_product_by_supplier_code(
                session, supplier_code
            )
            if product:
                match = ProductMatch(
                    product=product,
                    source=ProductMatchSource.SUPPLIER_CODE,
                    confidence_note=f"Match po šifri: {supplier_code}",
                    requires_review=False
                )
                CampaignService._log_product_match(
                    session, session_id, excel_row_number,
                    supplier_code, product_name, normalized_name, brand,
                    match
                )
                return product, match
        
        # 2. Pokušaj match po normalized_name
        product = CampaignService._find_product_by_normalized_name(
            session, normalized_name
        )
        if product:
            match = ProductMatch(
                product=product,
                source=ProductMatchSource.NORMALIZED_NAME,
                confidence_note=f"Match po nazivu: {normalized_name}",
                requires_review=False
            )
            CampaignService._log_product_match(
                session, session_id, excel_row_number,
                supplier_code, product_name, normalized_name, brand,
                match
            )
            return product, match
        
        # 3. Pokušaj match po normalized_name + brand
        if brand:
            product = CampaignService._find_product_by_name_and_brand(
                session, normalized_name, brand
            )
            if product:
                match = ProductMatch(
                    product=product,
                    source=ProductMatchSource.NORMALIZED_NAME_AND_BRAND,
                    confidence_note=f"Match po nazivu i brandu: {normalized_name} + {brand}",
                    requires_review=False
                )
                CampaignService._log_product_match(
                    session, session_id, excel_row_number,
                    supplier_code, product_name, normalized_name, brand,
                    match
                )
                return product, match
        
        # 4. Kreiraj novi proizvod
        product = Product(
            supplier_code=supplier_code,
            name=product_name,
            normalized_name=normalized_name,
            brand=brand,
            is_active=True
        )
        session.add(product)
        session.flush()
        
        match = ProductMatch(
            product=product,
            source=ProductMatchSource.NEW_PRODUCT,
            confidence_note="Novi proizvod - kreiran",
            requires_review=False
        )
        CampaignService._log_product_match(
            session, session_id, excel_row_number,
            supplier_code, product_name, normalized_name, brand,
            match
        )
        
        return product, match

    @staticmethod
    def _log_product_match(
        session,
        session_id: int,
        excel_row_number: int,
        supplier_code: Optional[str],
        raw_name: str,
        normalized_name: str,
        brand: Optional[str],
        match: ProductMatch
    ) -> None:
        """
        Loguje product match u bazu.
        """
        import_match = ImportProductMatch(
            session_id=session_id,
            product_id=match.product.id,
            excel_row_number=excel_row_number,
            raw_supplier_code=supplier_code,
            raw_name=raw_name,
            raw_normalized_name=normalized_name,
            raw_brand=brand,
            match_source=match.source,
            confidence_note=match.confidence_note,
            requires_review=match.requires_review
        )
        session.add(import_match)

    # ---------------------------------------------------------------------
    # Import kampanje
    # ---------------------------------------------------------------------

    @staticmethod
    def import_campaign_from_excel(
        excel_path: str | Path,
        campaign_name: str,
        start_date: date,
        end_date: date,
        note: Optional[str] = None
    ) -> ImportResult:
        """
        Importuje kampanju iz Excel fajla.
        
        Args:
            excel_path: Putanja do Excel fajla
            campaign_name: Naziv kampanje
            start_date: Datum početka kampanje
            end_date: Datum završetka kampanje
            note: Opciona napomena
        
        Returns:
            ImportResult sa statistikom importa
        
        Raises:
            FileNotFoundError: Ako Excel fajl ne postoji
            ValueError: Ako kampanja već postoji ili podaci nisu validni
        """
        excel_path = Path(excel_path)
        
        # Kreiraj import sesiju
        with session_scope() as session:
            import_session = ImportSession(
                import_type="campaign_price_list",
                source_filename=excel_path.name,
                status=ImportStatus.STARTED
            )
            session.add(import_session)
            session.flush()
            session_id = import_session.id
        
        # Učitaj i parsiraj Excel
        rows, mapped, load_errors = load_excel_data(excel_path)
        
        # Loguj greške iz učitavanja
        with session_scope() as session:
            for err in load_errors:
                error_log = ImportErrorLog(
                    session_id=session_id,
                    excel_row_number=err["row"],
                    field_name="name" if "Naziv" in err["error"] else "price",
                    error_message=err["error"]
                )
                session.add(error_log)
        
        # Procesuiraj redove
        new_products = 0
        matched_products = 0
        skipped_rows = len(load_errors)
        
        with session_scope() as session:
            # Kreiraj kampanju
            existing = session.execute(
                select(Campaign).where(Campaign.name == campaign_name)
            ).scalars().first()
            
            if existing:
                # Ažuriraj import sesiju
                import_session = session.get(ImportSession, session_id)
                import_session.status = ImportStatus.FAILED
                import_session.message = f"Kampanja '{campaign_name}' već postoji"
                
                raise ValueError(
                    f"Kampanja sa nazivom '{campaign_name}' već postoji."
                )
            
            campaign = Campaign(
                name=campaign_name,
                start_date=start_date,
                end_date=end_date,
                status=CampaignStatus.DRAFT,
                source_excel_filename=excel_path.name,
                note=note
            )
            session.add(campaign)
            session.flush()
            campaign_id = campaign.id
            
            # Skup product_id-eva već dodanih u ovu kampanju (sprečava duplikate)
            added_product_ids: set = set()

            # Procesuiraj svaki red
            for row in rows:
                try:
                    # Pronađi ili kreiraj proizvod
                    product, match = CampaignService.find_or_create_product(
                        session=session,
                        supplier_code=row.supplier_code,
                        product_name=row.product_name,
                        brand=row.brand,
                        session_id=session_id,
                        excel_row_number=row.row_number
                    )

                    # Preskoči duplikat — isti proizvod se pojavljuje više puta u fajlu
                    if product.id in added_product_ids:
                        error_log = ImportErrorLog(
                            session_id=session_id,
                            excel_row_number=row.row_number,
                            field_name="product",
                            error_message=f"Duplikat: '{row.product_name}' već dodan u ovu kampanju"
                        )
                        session.add(error_log)
                        skipped_rows += 1
                        continue

                    added_product_ids.add(product.id)

                    if match.source == ProductMatchSource.NEW_PRODUCT:
                        new_products += 1
                    else:
                        matched_products += 1

                    # Kreiraj campaign_price
                    campaign_price = CampaignPrice(
                        campaign_id=campaign_id,
                        product_id=product.id,
                        regular_price=row.regular_price,
                        discount_price=row.discount_price,
                        points=row.points,
                        status_label="akcija" if row.discount_price else None
                    )
                    session.add(campaign_price)

                except Exception as e:
                    # Loguj grešku
                    error_log = ImportErrorLog(
                        session_id=session_id,
                        excel_row_number=row.row_number,
                        field_name="product",
                        error_message=str(e)
                    )
                    session.add(error_log)
                    skipped_rows += 1
            
            # Ažuriraj import sesiju
            import_session = session.get(ImportSession, session_id)
            import_session.rows_total = len(rows) + len(load_errors)
            import_session.rows_successful = new_products + matched_products
            import_session.rows_failed = skipped_rows
            import_session.status = ImportStatus.COMPLETED
            import_session.message = f"Import uspješan: {new_products + matched_products} proizvoda"
        
        return ImportResult(
            total_rows=len(rows) + len(load_errors),
            imported_products=new_products + matched_products,
            new_products=new_products,
            matched_products=matched_products,
            skipped_rows=skipped_rows,
            errors=load_errors
        )

    @staticmethod
    def get_import_session(session_id: int) -> Optional[ImportSession]:
        """
        Dohvaća detalje import sesije sa greškama i product matchovima.
        """
        with session_scope() as session:
            return session.execute(
                select(ImportSession)
                .options(
                    selectinload(ImportSession.errors),
                    selectinload(ImportSession.product_matches),
                )
                .where(ImportSession.id == session_id)
            ).scalar_one_or_none()

    @staticmethod
    def list_import_sessions() -> List[ImportSession]:
        """
        Vraća listu import sesija.
        """
        with session_scope() as session:
            return list(
                session.execute(
                    select(ImportSession).order_by(ImportSession.created_at.desc())
                ).scalars().all()
            )

    @staticmethod
    def delete_campaign(campaign_id: int) -> bool:
        """
        Briše kampanju i sve pripadajuće proizvode (CampaignPrice).

        Args:
            campaign_id: ID kampanje za brisanje

        Returns:
            True ako je brisanje uspješno

        Raises:
            ValueError: Ako kampanja ne postoji
        """
        with session_scope() as session:
            campaign = session.get(Campaign, campaign_id)
            if campaign is None:
                raise ValueError(f"Kampanja #{campaign_id} nije pronađena.")

            # Prvo obriši sve CampaignPrice zapise
            for cp in campaign.prices:
                session.delete(cp)

            # Zatim obriši kampanju
            session.delete(campaign)

            return True
