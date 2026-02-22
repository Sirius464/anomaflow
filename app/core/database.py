"""
AnomaFlow v2.0 — Modèles de base de données
Corrections v2 :
  - declarative_base() → DeclarativeBase (SQLAlchemy 2.x)
  - Anomaly.timestamp : String → DateTime
  - Ajout UserProfile pour PUT /users/me
  - Index supplémentaires pour les requêtes fréquentes
"""
from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import settings


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Modèles ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name     = Column(String(255), nullable=True)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploads = relationship("Upload", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Upload(Base):
    __tablename__ = "uploads"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename        = Column(String(255), nullable=False)
    upload_date     = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_rows      = Column(Integer, default=0)
    anomalies_count = Column(Integer, default=0)
    status          = Column(String(50), default="pending")  # pending | completed | error
    report_json     = Column(Text)

    user      = relationship("User", back_populates="uploads")
    anomalies = relationship("Anomaly", back_populates="upload", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_uploads_user_date", "user_id", "upload_date"),
    )

    def __repr__(self) -> str:
        return f"<Upload id={self.id} file={self.filename!r} status={self.status!r}>"


class Anomaly(Base):
    __tablename__ = "anomalies"

    id                 = Column(Integer, primary_key=True, index=True)
    upload_id          = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    transaction_id     = Column(String(255), nullable=False)
    user_id_transaction = Column(String(255), nullable=False, index=True)
    amount             = Column(Float, nullable=False)
    # ✅ Correction v2 : DateTime au lieu de String pour permettre les requêtes temporelles
    transaction_at     = Column(DateTime, nullable=True)
    anomaly_type       = Column(String(100), nullable=False, index=True)
    reason             = Column(Text, nullable=False)
    severity           = Column(String(20), nullable=False, index=True)
    confidence_score   = Column(Float, nullable=False, default=0.0)
    detected_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    upload = relationship("Upload", back_populates="anomalies")

    __table_args__ = (
        Index("ix_anomalies_severity_type", "severity", "anomaly_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Anomaly id={self.id} type={self.anomaly_type!r} "
            f"severity={self.severity!r} amount={self.amount}>"
        )


# ── Engine & Session ──────────────────────────────────────────────────────────

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Crée toutes les tables si elles n'existent pas."""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de données initialisée")


def get_db() -> Generator:
    """Fournit une session SQLAlchemy (dependency injection FastAPI)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        