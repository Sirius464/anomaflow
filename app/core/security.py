"""
AnomaFlow v2.0 — Sécurité & Authentification
Nouveautés v2 :
  - TokenBlacklist en mémoire avec TTL automatique (support logout)
  - Schéma de réponse enrichi
  - Type hints complets
"""
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import User, get_db

# ── Cryptographie ─────────────────────────────────────────────────────────────

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],
    default="pbkdf2_sha256",
    deprecated="auto",
)

security_scheme = HTTPBearer()


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ── Token Blacklist ───────────────────────────────────────────────────────────

class TokenBlacklist:
    """
    Blacklist de tokens JWT révoqués, stockée en mémoire.
    Chaque entrée expire automatiquement après TTL secondes pour éviter
    une croissance illimitée de la mémoire.
    """

    def __init__(self) -> None:
        self._store: dict[str, float] = {}  # jti → timestamp d'expiration
        self._lock = Lock()

    def revoke(self, jti: str, ttl: int = settings.TOKEN_BLACKLIST_TTL) -> None:
        with self._lock:
            self._purge_expired()
            self._store[jti] = time.time() + ttl

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            expiry = self._store.get(jti)
            if expiry is None:
                return False
            if time.time() > expiry:
                del self._store[jti]
                return False
            return True

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if v < now]
        for k in expired:
            del self._store[k]

    @property
    def size(self) -> int:
        return len(self._store)


# Singleton partagé dans toute l'application
token_blacklist = TokenBlacklist()


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_hours: Optional[int] = None) -> str:
    """Génère un JWT signé avec une durée de vie configurable."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        hours=expires_hours or settings.ACCESS_TOKEN_EXPIRE_HOURS
    )
    # jti (JWT ID) unique permet la révocation individuelle
    import uuid
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Décode et valide un JWT. Lève HTTP 401 si invalide ou révoqué."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti", "")
    if token_blacklist.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token révoqué — veuillez vous reconnecter",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def revoke_token(token: str) -> None:
    """Révoque un token JWT (utilisé par /auth/logout)."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},  # on révoque même les tokens expirés
        )
        jti = payload.get("jti", token[:32])
        exp = payload.get("exp", int(time.time()) + settings.TOKEN_BLACKLIST_TTL)
        ttl = max(0, exp - int(time.time()))
        token_blacklist.revoke(jti, ttl=ttl or settings.TOKEN_BLACKLIST_TTL)
    except JWTError:
        pass  # token déjà invalide, rien à révoquer


# ── Dépendances FastAPI ───────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency : récupère l'utilisateur à partir du JWT Bearer."""
    payload = decode_token(credentials.credentials)
    email: Optional[str] = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token malformé")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Vérifie les identifiants et retourne l'utilisateur ou None."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user