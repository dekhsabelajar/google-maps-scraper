"""
Database storage module: SQLite/PostgreSQL schema, entity deduplication,
transaction management, and atomic checkpointing.
"""
import enum
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import (
    create_engine,
    Boolean,
    Column,
    String,
    Text,
    DateTime,
    Float,
    Integer,
    Enum as SAEnum,
    Index,
    select,
    text,
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
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    kecamatan = Column(String(120), nullable=True)
    kota_kabupaten = Column(String(120), nullable=True)
    google_url = Column(Text, nullable=True)
    is_replied = Column(Boolean, nullable=False, default=False)
    reply_notes = Column(Text, nullable=True)
    outreach_updated_at = Column(DateTime, nullable=True)
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
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "kecamatan": self.kecamatan,
            "kota_kabupaten": self.kota_kabupaten,
            "google_url": self.google_url,
            "is_replied": bool(self.is_replied) if self.is_replied is not None else False,
            "reply_notes": self.reply_notes or "",
            "outreach_updated_at": self.outreach_updated_at.isoformat() if self.outreach_updated_at else None,
            "extracted_emails": emails,
            "enrichment_status": self.enrichment_status.value if hasattr(self.enrichment_status, "value") else str(self.enrichment_status),
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "dedup_hash": self.dedup_hash,
        }


class BusinessReview(Base):
    """
    Stores individual customer reviews from Google Maps.
    Includes reviewer name, star rating, text comment, sentiment tag, and owner responses.
    """
    __tablename__ = "business_reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(36), nullable=True)
    business_name = Column(String(255), nullable=False, index=True)
    niche = Column(String(255), nullable=True, index=True)
    author = Column(String(255), nullable=True)
    rating = Column(Float, nullable=True)
    review_date = Column(String(100), nullable=True)
    review_text = Column(Text, nullable=True)
    sentiment = Column(String(50), nullable=True)
    owner_response = Column(Text, nullable=True)
    scraped_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    review_hash = Column(String(64), unique=True, index=True, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "business_id": self.business_id,
            "business_name": self.business_name,
            "niche": self.niche,
            "author": self.author,
            "rating": self.rating,
            "review_date": self.review_date,
            "review_text": self.review_text,
            "sentiment": self.sentiment,
            "owner_response": self.owner_response,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


def _resolve_database_url(explicit_url: Optional[str] = None) -> str:
    """
    Resolve database connection URL in priority order:
    1. Explicit argument
    2. Environment variable (SUPABASE_DB_URL / DATABASE_URL)
    3. Streamlit secrets (SUPABASE_DB_URL / DATABASE_URL)
    4. Local SQLite fallback (settings.DATABASE_PATH)
    """
    raw_url = explicit_url or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not raw_url:
        try:
            import streamlit as st
            raw_url = st.secrets.get("SUPABASE_DB_URL") or st.secrets.get("DATABASE_URL")
        except Exception:
            raw_url = None

    if raw_url and isinstance(raw_url, str) and raw_url.strip():
        clean_url = raw_url.strip()
        if clean_url.startswith("postgres://"):
            clean_url = "postgresql+psycopg2://" + clean_url[len("postgres://"):]
        elif clean_url.startswith("postgresql://"):
            clean_url = "postgresql+psycopg2://" + clean_url[len("postgresql://"):]
        return clean_url

    db_path = settings.DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


class DatabaseManager:
    """
    Manages database sessions, deduplication logic, and atomic status checkpoints.
    Supports Supabase (PostgreSQL) and local SQLite seamlessly.
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = _resolve_database_url(db_url)
        is_sqlite = self.db_url.startswith("sqlite")

        engine_kwargs: Dict[str, Any] = {"echo": False, "future": True}
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_recycle"] = 300

        self.engine = create_engine(self.db_url, **engine_kwargs)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.Session = scoped_session(self.session_factory)
        self.create_tables()

    def get_storage_backend_label(self) -> str:
        """Return a human-readable label for the active database backend."""
        if "sqlite" in self.db_url:
            return "SQLite Lokal"
        if "supabase" in self.db_url.lower():
            return "Supabase (PostgreSQL)"
        return "PostgreSQL Cloud"

    def create_tables(self):
        Base.metadata.create_all(self.engine)
        self._ensure_geo_columns()

    def _ensure_geo_columns(self):
        """Safely migrate existing SQLite or PostgreSQL tables to include geo & outreach columns."""
        extra_cols_sqlite = {
            "latitude": "FLOAT",
            "longitude": "FLOAT",
            "kecamatan": "VARCHAR(120)",
            "kota_kabupaten": "VARCHAR(120)",
            "google_url": "TEXT",
            "is_replied": "BOOLEAN DEFAULT 0",
            "reply_notes": "TEXT",
            "outreach_updated_at": "DATETIME",
        }
        extra_cols_pg = {
            "latitude": "DOUBLE PRECISION",
            "longitude": "DOUBLE PRECISION",
            "kecamatan": "VARCHAR(120)",
            "kota_kabupaten": "VARCHAR(120)",
            "google_url": "TEXT",
            "is_replied": "BOOLEAN NOT NULL DEFAULT FALSE",
            "reply_notes": "TEXT",
            "outreach_updated_at": "TIMESTAMP",
        }
        with self.engine.begin() as conn:
            if "sqlite" in self.db_url:
                existing = {
                    row[1] for row in conn.execute(text("PRAGMA table_info(business_entities)")).fetchall()
                }
                for col_name, col_type in extra_cols_sqlite.items():
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE business_entities ADD COLUMN {col_name} {col_type}"))
            else:
                for col_name, col_type in extra_cols_pg.items():
                    conn.execute(text(f"ALTER TABLE business_entities ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))

    def insert_or_update_entity(
        self,
        search_keyword: str,
        business_name: str,
        category: Optional[str] = None,
        address: Optional[str] = None,
        phone_number: Optional[str] = None,
        website_url: Optional[str] = None,
        rating: Optional[float] = None,
        reviews_count: Optional[int] = None,
        enrichment_status: Optional[EnrichmentStatus] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        kecamatan: Optional[str] = None,
        kota_kabupaten: Optional[str] = None,
        google_url: Optional[str] = None,
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
                if rating is not None:
                    existing.rating = rating
                if reviews_count is not None:
                    existing.reviews_count = reviews_count
                if existing.latitude is None and latitude is not None:
                    existing.latitude = latitude
                if existing.longitude is None and longitude is not None:
                    existing.longitude = longitude
                if (not existing.kecamatan or existing.kecamatan == "Tidak Diketahui") and kecamatan:
                    existing.kecamatan = kecamatan
                if (not existing.kota_kabupaten or existing.kota_kabupaten == "Tidak Diketahui") and kota_kabupaten:
                    existing.kota_kabupaten = kota_kabupaten
                if not existing.google_url and google_url:
                    existing.google_url = google_url

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
                rating=rating,
                reviews_count=reviews_count,
                latitude=latitude,
                longitude=longitude,
                kecamatan=kecamatan,
                kota_kabupaten=kota_kabupaten,
                google_url=google_url,
                is_replied=False,
                reply_notes="",
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
        Returns all entities as dictionaries ordered newest-first for dashboard & export.
        """
        session = self.Session()
        try:
            stmt = select(BusinessEntity).order_by(BusinessEntity.scraped_at.desc())
            if keyword:
                stmt = stmt.where(BusinessEntity.search_keyword == keyword)
            entities = session.execute(stmt).scalars().all()
            return [e.to_dict() for e in entities]
        finally:
            session.close()

    def update_outreach_batch(self, updates: List[Dict[str, Any]]) -> int:
        """
        Persist manual outreach status (is_replied checkbox & reply_notes) to the database.
        Each item in updates should have: id, is_replied, reply_notes.
        Returns the number of rows updated.
        """
        if not updates:
            return 0
        session = self.Session()
        updated_count = 0
        now_ts = datetime.now(timezone.utc)
        try:
            for item in updates:
                entity_id = item.get("id")
                if not entity_id:
                    continue
                stmt = select(BusinessEntity).where(BusinessEntity.id == entity_id)
                entity = session.execute(stmt).scalar_one_or_none()
                if entity:
                    entity.is_replied = bool(item.get("is_replied", False))
                    entity.reply_notes = str(item.get("reply_notes") or "").strip()
                    entity.outreach_updated_at = now_ts
                    updated_count += 1
            session.commit()
            return updated_count
        except Exception:
            session.rollback()
            raise
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

    def insert_review(
        self,
        business_name: str,
        author: str,
        rating: Optional[float] = None,
        review_date: Optional[str] = None,
        review_text: Optional[str] = None,
        sentiment: Optional[str] = None,
        owner_response: Optional[str] = None,
        niche: Optional[str] = None,
        business_id: Optional[str] = None,
    ) -> Tuple[BusinessReview, bool]:
        raw_sig = f"{business_name}_{author}_{rating}_{review_date}_{review_text[:30] if review_text else ''}"
        review_hash = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()
        session = self.Session()
        try:
            stmt = select(BusinessReview).where(BusinessReview.review_hash == review_hash)
            existing = session.execute(stmt).scalar_one_or_none()
            if existing:
                return existing, False

            new_review = BusinessReview(
                business_id=business_id,
                business_name=business_name,
                niche=niche,
                author=author,
                rating=rating,
                review_date=review_date,
                review_text=review_text,
                sentiment=sentiment,
                owner_response=owner_response,
                review_hash=review_hash,
            )
            session.add(new_review)
            session.commit()
            return new_review, True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_all_reviews_as_dicts(
        self,
        business_name: Optional[str] = None,
        niche: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            stmt = select(BusinessReview)
            if business_name:
                stmt = stmt.where(BusinessReview.business_name == business_name)
            if niche:
                stmt = stmt.where(BusinessReview.niche == niche)
            if limit:
                stmt = stmt.limit(limit)
            reviews = session.execute(stmt).scalars().all()
            return [r.to_dict() for r in reviews]
        finally:
            session.close()

    def get_reviewed_business_names(self) -> set:
        session = self.Session()
        try:
            stmt = select(BusinessReview.business_name).distinct()
            res = session.execute(stmt).scalars().all()
            return set(res)
        finally:
            session.close()
