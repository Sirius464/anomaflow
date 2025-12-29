"""Configuration de l'application"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "AnomaFlow")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./anomaflow.db")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", 10485760))
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx"]
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    ML_ENABLED: bool = os.getenv("ML_ENABLED", "false").lower() == "true"
    ML_CONTAMINATION: float = 0.1
    ANOMALY_THRESHOLD_MULTIPLIER: float = float(os.getenv("ANOMALY_THRESHOLD_MULTIPLIER", 3.0))
    MAX_TRANSACTIONS_PER_HOUR: int = int(os.getenv("MAX_TRANSACTIONS_PER_HOUR", 10))
    SUSPICIOUS_ROUND_AMOUNTS: List[float] = [100.0, 500.0, 1000.0, 5000.0]
    SMTP_ENABLED: bool = os.getenv("SMTP_ENABLED", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()

def validate_config():
    if settings.SECRET_KEY == "change-me":
        print("⚠️  ATTENTION : SECRET_KEY par défaut !")
    if not settings.GROQ_API_KEY:
        print("ℹ️  Groq API non configurée")
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR)
    print(f"✅ Configuration chargée : {settings.APP_NAME} v{settings.APP_VERSION}")

def validate_security():
    """Valide la configuration de sécurité"""
    weak_keys = ["change-me", "secret", "password", "123456"]
    if settings.SECRET_KEY in weak_keys:
        raise ValueError("SECRET_KEY trop faible ! Modifiez .env")
    if len(settings.SECRET_KEY) < 32:
        print("⚠️  SECRET_KEY courte. Recommandé: 64 caractères")
    if settings.DEBUG:
        print("⚠️  Mode DEBUG activé - désactivez en production")