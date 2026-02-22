"""
AnomaFlow v2.0 — Configuration centralisée
"""
import os
import secrets
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "AnomaFlow")
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

    # ── Sécurité ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", 24))
    # Durée de vie des tokens révoqués en mémoire (secondes)
    TOKEN_BLACKLIST_TTL: int = int(os.getenv("TOKEN_BLACKLIST_TTL", 86400))

    # ── Base de données ───────────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./anomaflow.db")

    # ── Upload ────────────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10 Mo
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    ALLOWED_EXTENSIONS: List[str] = [".csv"]

    # ── Groq / IA ─────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", 1200))
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", 0.7))
    GROQ_TIMEOUT: float = float(os.getenv("GROQ_TIMEOUT", 30.0))
    GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", 3))

    # ── Détection d'anomalies ─────────────────────────────────────────────────
    ANOMALY_THRESHOLD_MULTIPLIER: float = float(
        os.getenv("ANOMALY_THRESHOLD_MULTIPLIER", 3.0)
    )
    MAX_TRANSACTIONS_PER_HOUR: int = int(
        os.getenv("MAX_TRANSACTIONS_PER_HOUR", 10)
    )
    # Seuils pour les montants quasi-ronds (tolérance ±ROUND_AMOUNT_TOLERANCE %)
    SUSPICIOUS_ROUND_AMOUNTS: List[float] = [
        100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0
    ]
    ROUND_AMOUNT_TOLERANCE: float = float(
        os.getenv("ROUND_AMOUNT_TOLERANCE", 0.02)  # ±2 %
    )
    # Plage horaire considérée comme "hors-heures" (heures UTC)
    SUSPICIOUS_HOUR_START: int = int(os.getenv("SUSPICIOUS_HOUR_START", 22))
    SUSPICIOUS_HOUR_END: int = int(os.getenv("SUSPICIOUS_HOUR_END", 6))
    # Nombre maximum d'anomalies retournées par analyse
    MAX_ANOMALIES_RETURNED: int = int(os.getenv("MAX_ANOMALIES_RETURNED", 100))

    # ── Machine Learning ──────────────────────────────────────────────────────
    ML_ENABLED: bool = os.getenv("ML_ENABLED", "true").lower() == "true"
    ML_CONTAMINATION: float = float(os.getenv("ML_CONTAMINATION", 0.05))

    # ── Pagination ────────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", 20))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", 100))

    # ── Logs ──────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()


def validate_config() -> None:
    """Valide et complète la configuration au démarrage."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Génère une SECRET_KEY sécurisée si absente (dev uniquement)
    if not settings.SECRET_KEY:
        settings.SECRET_KEY = secrets.token_hex(32)
        print("⚠️  SECRET_KEY auto-générée (non persistante). Définissez SECRET_KEY dans .env")
    elif settings.SECRET_KEY in ("change-me", "secret", "password"):
        print("⚠️  SECRET_KEY faible détectée — modifiez .env avant toute mise en production")

    if not settings.GROQ_API_KEY:
        print("ℹ️  GROQ_API_KEY non configurée — les rapports IA utiliseront le mode dégradé")

    if settings.DEBUG:
        print("⚠️  Mode DEBUG actif — désactivez en production (DEBUG=false)")

    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} — configuration chargée")