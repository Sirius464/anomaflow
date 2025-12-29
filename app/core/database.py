"""Connexion à la base de données"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from app.config import settings

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploads = relationship("Upload", back_populates="user")

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String(255))
    upload_date = Column(DateTime, default=datetime.utcnow)
    total_rows = Column(Integer, default=0)
    anomalies_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    report_json = Column(Text)
    user = relationship("User", back_populates="uploads")
    anomalies = relationship("Anomaly", back_populates="upload")

class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"))
    transaction_id = Column(String(255))
    user_id_transaction = Column(String(255))
    amount = Column(Float)
    timestamp = Column(String(255))
    anomaly_type = Column(String(100))
    reason = Column(Text)
    severity = Column(String(20))
    confidence_score = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow)
    upload = relationship("Upload", back_populates="anomalies")

# Créer l'engine directement avec les paramètres de configuration
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Crée toutes les tables si elles n'existent pas"""
    Base.metadata.create_all(bind=engine)
    print("✅ Base de données initialisée")

def get_db():
    """Fournit une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
