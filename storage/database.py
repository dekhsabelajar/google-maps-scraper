"""
Database storage module: SQLite/PostgreSQL schema, entity deduplication,
transaction management, and atomic checkpointing.
"""
import enum
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    Index,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

from config.settings import settings
from core.normalizer import generate_dedup_hash

Base = declarative_base()


class EnrichmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    NO_WEBSITE = "NO_WEBSITE"
    FAILED = "FAILED"


class BusinessEntity(Base):
    """
    Business Entity Table complying with PRD Section 5 schema.
    """
    __tablename__ = "business_entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    search_keyword = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    phone_number = Column(String(50), nullable=True)
    website_url = Column(Text, nullable=True)
    extracted_emails = Column(Text, nullable=True)  # Stored as JSON string
    enrichment_status = Column(SAEnum(EnrichmentStatus), nullable=False, default=EnrichmentStatus.PENDING)
    scraped_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    dedup_hash = Column(String(64), unique=True, index=True, nullable=False)

    __table_args__ = (
        Index("idx_search_keyword", "search_keyword"),
        Index("idx_enrichment_status", "enrichment_status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        emails = []
        if self.extracted_emails:
            try:
                emails = json.loads(self.extracted_emails)
            except Exception:
                emails = [self.extracted_emails]

        return {
            "id": self.id,
            "search_keyword": self.search_keyword,
            "business_name": self.business_name,
            "category": self.category,
            "address": self.address,
            "phone_number": self.phone_number,
            "website_url": self.website_url,
            "extracted_emails": emails,
            "enrichment_status": self.enrichment_status.value if hasattr(self.enrichment_status, "value") else str(self.enrichment_status),
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "dedup_hash": self.dedup_hash,
        }


class DatabaseManager:
    """
    Manages database sessions, deduplication logic, and atomic status checkpoints.
    """
    def __init__(self, db_url: Optional[str] = None):
        if not db_url:
            db_path = settings.DATABASE_PATH
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_url = f"sqlite:///{db_path}"
        else:
            self.db_url = db_url

        self.engine = create_engine(
            self.db_url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False} if "sqlite" in self.db_url else {}
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.Session = scoped_session(self.session_factory)
        self.create_tables()

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def insert_or_update_entity(
        self,
        search_keyword: str,
        business_name: str,
        category: Optional[str] = None,
        address: Optional[str] = None,
        phone_number: Optional[str] = None,
        website_url: Optional[str] = None,
        enrichment_status: Optional[EnrichmentStatus] = None,
    ) -> Tuple[BusinessEntity, bool]:
        """
        Deduplication logic (FR-07):
        Checks if entity already exists using SHA-256(name + phone/address).
        If exists, updates missing attributes and returns (entity, False).
        If new, inserts entity and returns (entity, True).
        """
        dedup_hash = generate_dedup_hash(business_name, phone_number, address)
        session = self.Session()
        try:
            stmt = select(BusinessEntity).where(BusinessEntity.dedup_hash == dedup_hash)
            existing = session.execute(stmt).scalar_one_or_none()

            # Determine default enrichment status
            if enrichment_status is None:
                if not website_url:
                    initial_status = EnrichmentStatus.NO_WEBSITE
                else:
                    initial_status = EnrichmentStatus.PENDING
            else:
                initial_status = enrichment_status

            if existing:
                # Update any newly discovered attributes without overwriting valid data
                if not existing.category and category:
                    existing.category = category
                if not existing.address and address:
                    existing.address = address
                if not existing.phone_number and phone_number:
                    existing.phone_number = phone_number
                if not existing.website_url and website_url:
                    existing.website_url = website_url
                    if existing.enrichment_status == EnrichmentStatus.NO_WEBSITE:
                        existing.enrichment_status = EnrichmentStatus.PENDING

                session.commit()
                return existing, False

            # Create new entity
            new_entity = BusinessEntity(
                search_keyword=search_keyword,
                business_name=business_name,
                category=category,
                address=address,
                phone_number=phone_number,
                website_url=website_url,
                enrichment_status=initial_status,
                scraped_at=datetime.now(timezone.utc),
                dedup_hash=dedup_hash,
            )
            session.add(new_entity)
            session.commit()
            return new_entity, True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_pending_enrichment_entities(self, limit: Optional[int] = None) -> List[BusinessEntity]:
        """
        Retrieves entities ready for Stage 2 email enrichment.
        Used for normal flow or --resume mode.
        """
        session = self.Session()
        try:
            stmt = select(BusinessEntity).where(
                BusinessEntity.enrichment_status == EnrichmentStatus.PENDING,
                BusinessEntity.website_url.isnot(None)
            )
            if limit:
                stmt = stmt.limit(limit)
            results = session.execute(stmt).scalars().all()
            return list(results)
        finally:
            session.close()

    def update_enrichment_result(
        self,
        entity_id: str,
        emails: List[str],
        status: EnrichmentStatus
    ):
        """
        Updates an entity with extracted emails and final enrichment status.
        """
        session = self.Session()
        try:
            stmt = select(BusinessEntity).where(BusinessEntity.id == entity_id)
            entity = session.execute(stmt).scalar_one_or_none()
            if entity:
                entity.extracted_emails = json.dumps(emails)
                entity.enrichment_status = status
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_all_entities_as_dicts(self, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns all entities as dictionaries for export and metric evaluation.
        """
        session = self.Session()
        try:
            stmt = select(BusinessEntity)
            if keyword:
                stmt = stmt.where(BusinessEntity.search_keyword == keyword)
            entities = session.execute(stmt).scalars().all()
            return [e.to_dict() for e in entities]
        finally:
            session.close()

    def count_entities(self, keyword: Optional[str] = None) -> int:
        session = self.Session()
        try:
            stmt = select(BusinessEntity)
            if keyword:
                stmt = stmt.where(BusinessEntity.search_keyword == keyword)
            return len(session.execute(stmt).scalars().all())
        finally:
            session.close()
