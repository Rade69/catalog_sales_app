"""
Testovi za campaign_service.py.

Testiraju se:
- CampaignService.get_campaign
- CampaignService.list_campaigns
- CampaignService.create_campaign
- CampaignService.update_campaign
- CampaignService.delete_campaign
"""

from __future__ import annotations

from datetime import date
import pytest

from app.database.models import Campaign, CampaignStatus
from app.services.campaign_service import CampaignService


class TestCampaignService:
    """Testovi za CampaignService."""

    def test_get_campaign_exists(self, db, sample_campaign):
        """Dohvatanje postojeće kampanje."""
        campaign_dto = CampaignService.get_campaign(sample_campaign.id)
        
        assert campaign_dto is not None
        assert campaign_dto.id == sample_campaign.id
        assert campaign_dto.name == sample_campaign.name
        assert campaign_dto.status == sample_campaign.status.value

    def test_get_campaign_not_exists(self, db):
        """Dohvatanje nepostojeće kampanje."""
        campaign_dto = CampaignService.get_campaign(99999)
        assert campaign_dto is None

    def test_list_campaigns_empty(self, db):
        """Lista kampanja kada nema kampanja."""
        campaigns = CampaignService.list_campaigns()
        assert campaigns == []

    def test_list_campaigns_with_data(self, db):
        """Lista kampanja sa podacima."""
        # Kreiraj nekoliko kampanja
        campaigns_data = [
            ("Kampanja 1", date(2024, 1, 1), date(2024, 6, 30), CampaignStatus.ACTIVE),
            ("Kampanja 2", date(2024, 7, 1), date(2024, 12, 31), CampaignStatus.DRAFT),
            ("Kampanja 3", date(2023, 1, 1), date(2023, 12, 31), CampaignStatus.ARCHIVED),
        ]
        
        for name, start_date, end_date, status in campaigns_data:
            campaign = Campaign(
                name=name,
                start_date=start_date,
                end_date=end_date,
                status=status,
            )
            db.add(campaign)
        db.commit()
        
        campaigns = CampaignService.list_campaigns()
        
        assert len(campaigns) == 3
        # Proveri da li su sortirane po start_date opadajuće (najnovije prvo)
        assert campaigns[0].name == "Kampanja 2"  # start_date 2024-07-01
        assert campaigns[1].name == "Kampanja 1"  # start_date 2024-01-01
        assert campaigns[2].name == "Kampanja 3"  # start_date 2023-01-01

    def test_list_campaigns_filter_status(self, db):
        """Filtriranje kampanja po statusu."""
        campaigns_data = [
            ("Aktivna", date(2024, 1, 1), date(2024, 6, 30), CampaignStatus.ACTIVE),
            ("Draft", date(2024, 7, 1), date(2024, 12, 31), CampaignStatus.DRAFT),
            ("Arhivirana", date(2023, 1, 1), date(2023, 12, 31), CampaignStatus.ARCHIVED),
            ("Aktivna 2", date(2024, 3, 1), date(2024, 8, 31), CampaignStatus.ACTIVE),
        ]
        
        for name, start_date, end_date, status in campaigns_data:
            campaign = Campaign(
                name=name,
                start_date=start_date,
                end_date=end_date,
                status=status,
            )
            db.add(campaign)
        db.commit()
        
        # Dohvati sve kampanje
        campaigns = CampaignService.list_campaigns()
        assert len(campaigns) == 4
        
        # Proveri da li su sortirane po datumu početka (opadajuće)
        dates = [c.start_date for c in campaigns]
        assert dates == sorted(dates, reverse=True)



    def test_create_campaign_success(self, db):
        """Kreiranje nove kampanje."""
        campaign_dto = CampaignService.create_campaign(
            name="Nova kampanja",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            note="Test napomena",
        )
        
        assert campaign_dto.id is not None
        assert campaign_dto.name == "Nova kampanja"
        assert campaign_dto.start_date == date(2024, 1, 1)
        assert campaign_dto.end_date == date(2024, 12, 31)
        assert campaign_dto.status == "draft"  # Automatski se postavlja na DRAFT
        assert campaign_dto.note == "Test napomena"
        
        # Proveri da li je stvarno sačuvana u bazi
        campaign = db.get(Campaign, campaign_dto.id)
        assert campaign is not None
        assert campaign.name == "Nova kampanja"

    def test_create_campaign_empty_name(self, db):
        """Kreiranje kampanje bez naziva."""
        with pytest.raises(ValueError, match="Naziv kampanje je obavezan."):
            CampaignService.create_campaign(
                name="",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

    def test_create_campaign_invalid_dates(self, db):
        """Kreiranje kampanje sa end_date prije start_date."""
        with pytest.raises(ValueError, match="Datum početka mora biti prije datuma završetka."):
            CampaignService.create_campaign(
                name="Test",
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),  # prije start_date
            )

    def test_create_campaign_duplicate_name(self, db, sample_campaign):
        """Kreiranje kampanje sa postojećim imenom."""
        with pytest.raises(ValueError, match=f"Kampanja sa nazivom '{sample_campaign.name}' već postoji."):
            CampaignService.create_campaign(
                name=sample_campaign.name,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            )

    def test_update_campaign_success(self, db, sample_campaign):
        """Ažuriranje postojeće kampanje."""
        campaign_dto = CampaignService.update_campaign(
            campaign_id=sample_campaign.id,
            name="Ažurirani naziv",
            start_date=date(2024, 2, 1),
            end_date=date(2024, 11, 30),
            status="active",
            note="Ažurirana napomena",
        )
        
        assert campaign_dto.id == sample_campaign.id
        assert campaign_dto.name == "Ažurirani naziv"
        assert campaign_dto.start_date == date(2024, 2, 1)
        assert campaign_dto.end_date == date(2024, 11, 30)
        assert campaign_dto.status == "active"
        assert campaign_dto.note == "Ažurirana napomena"
        
        # Proveri da li je stvarno ažurirana u bazi
        db.refresh(sample_campaign)
        assert sample_campaign.name == "Ažurirani naziv"
        assert sample_campaign.status == CampaignStatus.ACTIVE

    def test_update_campaign_not_exists(self, db):
        """Ažuriranje nepostojeće kampanje."""
        with pytest.raises(ValueError, match="Kampanja #99999 nije pronađena."):
            CampaignService.update_campaign(
                campaign_id=99999,
                name="Test",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                status="draft",
            )

    def test_update_campaign_archive_with_orders(self, db, sample_campaign, sample_order):
        """Arhiviranje kampanje koja ima aktivne narudžbe."""
        # sample_order koristi sample_campaign
        with pytest.raises(ValueError, match="Kampanja ima 1 vezanih narudžbi i ne može se arhivirati."):
            CampaignService.update_campaign(
                campaign_id=sample_campaign.id,
                name=sample_campaign.name,
                start_date=sample_campaign.start_date,
                end_date=sample_campaign.end_date,
                status="archived",  # pokušaj arhiviranja
            )

    def test_delete_campaign_success(self, db):
        """Brisanje kampanje (soft delete)."""
        # Kreiraj kampanju za brisanje
        campaign = Campaign(
            name="Za brisanje",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            status=CampaignStatus.DRAFT,
        )
        db.add(campaign)
        db.commit()
        
        # Sačuvaj ID pre brisanja
        campaign_id = campaign.id
        
        # Metoda vraća None ako je uspešno
        CampaignService.delete_campaign(campaign_id)
        
        # Proveri da li je kampanja zaista obrisana
        db.expire_all()
        deleted_campaign = db.get(Campaign, campaign_id)
        assert deleted_campaign is None
        
        # Proveri da li se ne pojavljuje u listi
        campaigns = CampaignService.list_campaigns()
        campaign_ids = [c.id for c in campaigns]
        assert campaign_id not in campaign_ids

    def test_delete_campaign_not_exists(self, db):
        """Brisanje nepostojeće kampanje."""
        with pytest.raises(ValueError, match="Kampanja #99999 nije pronađena."):
            CampaignService.delete_campaign(99999)

    def test_delete_campaign_with_orders(self, db, sample_campaign, sample_order):
        """Brisanje kampanje koja ima narudžbe."""
        with pytest.raises(ValueError, match="Kampanja ima 1 vezanih narudžbi i ne može se obrisati."):
            CampaignService.delete_campaign(sample_campaign.id)

    def test_campaign_dto_structure(self, db, sample_campaign):
        """Provera strukture CampaignDTO."""
        campaign_dto = CampaignService.get_campaign(sample_campaign.id)
        
        # Proveri da li DTO ima sva očekivana polja
        assert hasattr(campaign_dto, 'id')
        assert hasattr(campaign_dto, 'name')
        assert hasattr(campaign_dto, 'start_date')
        assert hasattr(campaign_dto, 'end_date')
        assert hasattr(campaign_dto, 'status')
        assert hasattr(campaign_dto, 'source_excel_filename')
        assert hasattr(campaign_dto, 'note')
        
        # Proveri tipove
        assert isinstance(campaign_dto.id, int)
        assert isinstance(campaign_dto.name, str)
        assert isinstance(campaign_dto.start_date, date)
        assert isinstance(campaign_dto.end_date, date)
        assert isinstance(campaign_dto.status, str)