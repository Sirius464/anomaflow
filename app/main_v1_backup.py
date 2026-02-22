"""
AnomaFlow v2.0 — Point d'entrée FastAPI
Nouveautés v2 :
  - POST /auth/logout (révocation JWT)
  - PUT  /users/me    (mise à jour profil)
  - GET  /reports/user/{user_id}  (admin)
  - Vérification de la taille du fichier uploadé
  - Pagination sur GET /reports
  - Risk summary intégré dans les réponses
  - Schémas Pydantic stricts
"""
from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.config import settings, validate_config
from app.core.database import Anomaly, Upload, User, get_db, init_db
from app.core.security import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    revoke_token,
    token_blacklist,
)
from app.services.ai_reporter import generate_report
from app.services.detector import detect_anomalies

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))

# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Système de détection d'anomalies transactionnelles propulsé par l'IA",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Dev  : toutes origines (*) — Production : définissez CORS_ORIGINS dans .env
#        ex: CORS_ORIGINS=https://votredomaine.com,https://app.votredomaine.com
import os
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

_raw_origins = os.getenv("CORS_ORIGINS", "")
cors_origins = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)

# ── Headers de sécurité HTTP ─────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next) -> StarletteResponse:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]         = "DENY"
        response.headers["X-XSS-Protection"]        = "1; mode=block"
        response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

templates = Jinja2Templates(directory="app/templates")

init_db()
validate_config()


# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 caractères")
    full_name: Optional[str] = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8, description="Laisser vide pour conserver le mot de passe actuel")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class RiskSummary(BaseModel):
    score: float
    level: str
    anomaly_rate: float
    by_type: dict[str, int]
    by_severity: dict[str, int]


class UploadResponse(BaseModel):
    file_id: int
    filename: str
    rows_processed: int
    anomalies_detected: int
    truncated: bool
    status: str
    risk_summary: RiskSummary


class ReportSummary(BaseModel):
    report_id: int
    filename: str
    upload_date: str
    total_transactions: int
    anomalies_count: int


class ReportDetail(ReportSummary):
    summary: str
    anomalies: list[dict]
    risk_summary: Optional[dict] = None


class PaginatedReports(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReportSummary]


# ── Pages Web ─────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("login_v2.html", {"request": request})


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard_fixed_v2.html", {"request": request})


@app.get("/app-simple", response_class=HTMLResponse, include_in_schema=False)
async def simple_app(request: Request):
    return templates.TemplateResponse("app_fallback_v2.html", {"request": request})


# ── Routes publiques ──────────────────────────────────────────────────────────

@app.get("/", tags=["Général"])
def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Général"])
def health():
    return {
        "status":          "healthy",
        "database":        "connected",
        "blacklist_size":  token_blacklist.size,
        "ml_enabled":      settings.ML_ENABLED,
        "ai_configured":   bool(settings.GROQ_API_KEY),
    }


# ── Authentification ──────────────────────────────────────────────────────────

@app.post(
    "/auth/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentification"],
    summary="Créer un compte",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email})
    return Token(access_token=token)


@app.post(
    "/auth/login",
    response_model=Token,
    tags=["Authentification"],
    summary="Se connecter",
)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user.email})
    return Token(access_token=token)


@app.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Authentification"],
    summary="Se déconnecter (révoque le token JWT)",
)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: User = Depends(get_current_user),  # valide le token avant révocation
):
    """
    Révoque le token JWT actuel.
    Toute requête ultérieure avec ce token retournera HTTP 401.
    """
    revoke_token(credentials.credentials)
    logger.info("Token révoqué pour l'utilisateur %s", current_user.email)


# ── Profil utilisateur ────────────────────────────────────────────────────────

@app.get(
    "/users/me",
    response_model=UserResponse,
    tags=["Utilisateurs"],
    summary="Mon profil",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.put(
    "/users/me",
    response_model=UserResponse,
    tags=["Utilisateurs"],
    summary="Mettre à jour mon profil",
)
def update_me(
    update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permet de modifier le nom complet et/ou le mot de passe.
    Les champs non renseignés conservent leur valeur actuelle.
    """
    if update.full_name is not None:
        current_user.full_name = update.full_name

    if update.password is not None:
        current_user.hashed_password = get_password_hash(update.password)

    db.commit()
    db.refresh(current_user)
    return current_user


# ── Upload & Analyse ──────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {"transaction_id", "user_id", "amount", "timestamp"}


@app.post(
    "/upload",
    response_model=UploadResponse,
    tags=["Analyse"],
    summary="Uploader et analyser un fichier CSV de transactions",
)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ── Validation du fichier ─────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les fichiers .csv sont acceptés")

    contents = await file.read()

    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux : {len(contents) // 1024} Ko (max {settings.MAX_UPLOAD_SIZE // 1024} Ko)",
        )

    if len(contents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le fichier est vide")

    # ── Lecture CSV ───────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(BytesIO(contents))
        df.columns = df.columns.str.strip().str.lower()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erreur de lecture CSV : {exc}")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Colonnes manquantes : {sorted(missing)}. Colonnes requises : {sorted(REQUIRED_COLUMNS)}",
        )

    if df.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le CSV ne contient aucune ligne de données")

    # ── Détection ─────────────────────────────────────────────────────────────
    anomalies, risk_summary = detect_anomalies(df)
    truncated = len(df) > 0 and (
        risk_summary.get("by_type") and
        sum(risk_summary["by_type"].values()) >= settings.MAX_ANOMALIES_RETURNED
    )

    # ── Rapport IA ────────────────────────────────────────────────────────────
    summary = await generate_report(anomalies, len(df), risk_summary)

    # ── Persistance ───────────────────────────────────────────────────────────
    upload_record = Upload(
        user_id=current_user.id,
        filename=file.filename,
        total_rows=len(df),
        anomalies_count=len(anomalies),
        status="completed",
        report_json=json.dumps(
            {"summary": summary, "anomalies": anomalies, "risk_summary": risk_summary},
            ensure_ascii=False,
        ),
    )
    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)

    for a in anomalies:
        import dateutil.parser as dparser
        tx_at = None
        if a["timestamp"]:
            try:
                tx_at = dparser.parse(a["timestamp"])
            except Exception:
                pass

        db.add(Anomaly(
            upload_id=upload_record.id,
            transaction_id=a["transaction_id"],
            user_id_transaction=a["user_id"],
            amount=a["amount"],
            transaction_at=tx_at,
            anomaly_type=a["anomaly_type"],
            reason=a["reason"],
            severity=a["severity"],
            confidence_score=a["confidence_score"],
        ))

    db.commit()

    return UploadResponse(
        file_id=upload_record.id,
        filename=file.filename,
        rows_processed=len(df),
        anomalies_detected=len(anomalies),
        truncated=truncated,
        status="completed",
        risk_summary=RiskSummary(**risk_summary),
    )


# ── Rapports ──────────────────────────────────────────────────────────────────

@app.get(
    "/reports",
    response_model=PaginatedReports,
    tags=["Rapports"],
    summary="Mes rapports (paginés)",
)
def list_reports(
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Upload)
        .filter(Upload.user_id == current_user.id)
        .order_by(Upload.upload_date.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedReports(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            ReportSummary(
                report_id=u.id,
                filename=u.filename,
                upload_date=str(u.upload_date),
                total_transactions=u.total_rows,
                anomalies_count=u.anomalies_count,
            )
            for u in items
        ],
    )


@app.get(
    "/reports/{report_id}",
    response_model=ReportDetail,
    tags=["Rapports"],
    summary="Détail d'un rapport",
)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upload = (
        db.query(Upload)
        .filter(Upload.id == report_id, Upload.user_id == current_user.id)
        .first()
    )
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapport introuvable")

    data = json.loads(upload.report_json)
    return ReportDetail(
        report_id=upload.id,
        filename=upload.filename,
        upload_date=str(upload.upload_date),
        total_transactions=upload.total_rows,
        anomalies_count=upload.anomalies_count,
        summary=data["summary"],
        anomalies=data["anomalies"],
        risk_summary=data.get("risk_summary"),
    )


@app.get(
    "/reports/user/{user_id}",
    response_model=PaginatedReports,
    tags=["Rapports"],
    summary="Rapports d'un utilisateur spécifique (admin)",
)
def get_user_reports(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accès aux rapports d'un autre utilisateur.
    Pour l'instant ouvert à tout utilisateur authentifié (à restreindre
    via un champ `is_admin` dans une prochaine version).
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    query = (
        db.query(Upload)
        .filter(Upload.user_id == user_id)
        .order_by(Upload.upload_date.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedReports(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            ReportSummary(
                report_id=u.id,
                filename=u.filename,
                upload_date=str(u.upload_date),
                total_transactions=u.total_rows,
                anomalies_count=u.anomalies_count,
            )
            for u in items
        ],
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get(
    "/dashboard",
    tags=["Général"],
    summary="Statistiques globales de mon compte",
)
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uploads = db.query(Upload).filter(Upload.user_id == current_user.id).all()
    total_tx    = sum(u.total_rows for u in uploads)
    total_anom  = sum(u.anomalies_count for u in uploads)

    return {
        "user_email":        current_user.email,
        "total_files":       len(uploads),
        "total_transactions": total_tx,
        "total_anomalies":   total_anom,
        "anomaly_rate":      f"{(total_anom / total_tx * 100):.2f}%" if total_tx else "0%",
    }


# ── Lancement direct ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    print(f"\n{'╔' + '═'*41 + '╗'}")
    print(f"║   🔍 {settings.APP_NAME} v{settings.APP_VERSION:<27}║")
    print(f"║   Détection d'Anomalies Intelligente    ║")
    print(f"{'╚' + '═'*41 + '╝'}\n")
    print(f"📍 API  : http://{settings.HOST}:{settings.PORT}")
    print(f"📖 Docs : http://{settings.HOST}:{settings.PORT}/docs\n")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )