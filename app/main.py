"""ANOMAFLOW - Application Principale"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import json
from io import BytesIO

# Import config
from app.config import settings, validate_config

# Import database
from app.core.database import init_db, get_db, User, Upload, Anomaly

# Import security
from app.core.security import get_password_hash, create_access_token, get_current_user, authenticate_user

# Import services
from app.services.detector import detect_anomalies
from app.services.ai_reporter import generate_report

# ============= INITIALISATION =============

# Créer l'app
app = FastAPI(
    title=settings.APP_NAME,
    description="Système de détection d'anomalies transactionnelles",
    version=settings.APP_VERSION
)

# Templates pour l'interface web
templates = Jinja2Templates(directory="app/templates")

# Initialiser les tables
init_db()

# Valider config
validate_config()

# ============= SCHÉMAS PYDANTIC =============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class UploadResponse(BaseModel):
    file_id: int
    filename: str
    rows_processed: int
    anomalies_detected: int
    status: str

# ============= PAGES WEB (doivent être APRÈS app = FastAPI()) =============

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/app", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Page dashboard - version simple"""
    return templates.TemplateResponse("dashboard_fixed.html", {"request": request})
# ============= ENDPOINTS API =============

@app.get("/")
def root():
    """Page d'accueil"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "register": "/auth/register",
            "login": "/auth/login"
        }
    }

@app.get("/health")
def health():
    """Health check"""
    return {"status": "healthy", "database": "connected"}

# ============= AUTHENTIFICATION =============

@app.post("/auth/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Créer un nouveau compte"""
    
    # Vérifier si l'email existe
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    # Créer l'utilisateur
    new_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Générer token
    token = create_access_token({"sub": user.email})
    
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    """Se connecter"""
    
    # Authentifier
    auth_user = authenticate_user(db, user.email, user.password)
    
    if not auth_user:
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )
    
    # Générer token
    token = create_access_token({"sub": user.email})
    
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Informations utilisateur"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active
    }

# ============= UPLOAD & ANALYSE =============

@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload et analyse un fichier CSV"""
    
    # Validation
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers CSV sont acceptés")
    
    # Lecture
    try:
        contents = await file.read()
        df = pd.read_csv(BytesIO(contents))
        
        # Nettoyer colonnes
        df.columns = df.columns.str.strip().str.lower()
        
        # Vérifier colonnes requises
        required = ['transaction_id', 'user_id', 'amount', 'timestamp']
        if not all(col in df.columns for col in required):
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes requises : {required}"
            )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture CSV : {str(e)}")
    
    # Détection d'anomalies
    anomalies = detect_anomalies(df)
    
    # Génération rapport IA
    summary = await generate_report(anomalies, len(df))
    
    # Sauvegarde en base
    upload_record = Upload(
        user_id=current_user.id,
        filename=file.filename,
        total_rows=len(df),
        anomalies_count=len(anomalies),
        status="completed",
        report_json=json.dumps({
            "summary": summary,
            "anomalies": anomalies
        })
    )
    
    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)
    
    # Sauvegarder anomalies
    for anomaly in anomalies:
        anomaly_record = Anomaly(
            upload_id=upload_record.id,
            transaction_id=anomaly['transaction_id'],
            user_id_transaction=anomaly['user_id'],
            amount=anomaly['amount'],
            timestamp=anomaly['timestamp'],
            anomaly_type=anomaly['anomaly_type'],
            reason=anomaly['reason'],
            severity=anomaly['severity'],
            confidence_score=anomaly['confidence_score']
        )
        db.add(anomaly_record)
    
    db.commit()
    
    return {
        "file_id": upload_record.id,
        "filename": file.filename,
        "rows_processed": len(df),
        "anomalies_detected": len(anomalies),
        "status": "completed"
    }

# ============= RAPPORTS =============

@app.get("/reports")
def get_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste tous les rapports"""
    
    uploads = db.query(Upload)\
        .filter(Upload.user_id == current_user.id)\
        .order_by(Upload.upload_date.desc())\
        .all()
    
    return [
        {
            "report_id": u.id,
            "filename": u.filename,
            "upload_date": str(u.upload_date),
            "total_transactions": u.total_rows,
            "anomalies_count": u.anomalies_count
        }
        for u in uploads
    ]

@app.get("/reports/{report_id}")
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère un rapport spécifique"""
    
    upload = db.query(Upload)\
        .filter(Upload.id == report_id, Upload.user_id == current_user.id)\
        .first()
    
    if not upload:
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    report_data = json.loads(upload.report_json)
    
    return {
        "report_id": upload.id,
        "filename": upload.filename,
        "upload_date": str(upload.upload_date),
        "total_transactions": upload.total_rows,
        "anomalies_count": upload.anomalies_count,
        "summary": report_data['summary'],
        "anomalies": report_data['anomalies']
    }

@app.get("/dashboard")
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Statistiques globales"""
    
    uploads = db.query(Upload).filter(Upload.user_id == current_user.id).all()
    
    total_files = len(uploads)
    total_transactions = sum(u.total_rows for u in uploads)
    total_anomalies = sum(u.anomalies_count for u in uploads)
    
    return {
        "user_email": current_user.email,
        "total_files": total_files,
        "total_transactions": total_transactions,
        "total_anomalies": total_anomalies,
        "anomaly_rate": f"{(total_anomalies/total_transactions*100):.2f}%" if total_transactions > 0 else "0%"
    }
@app.get("/app-simple", response_class=HTMLResponse)
async def simple_app(request: Request):
    return templates.TemplateResponse("app_fallback.html", {"request": request})
# ============= LANCEMENT =============

if __name__ == "__main__":
    import uvicorn
    
    print(f"\n╔═══════════════════════════════════════╗")
    print(f"║   🔍 ANOMAFLOW v{settings.APP_VERSION}              ║")
    print(f"║  Détection d'Anomalies Intelligente  ║")
    print(f"╚═══════════════════════════════════════╝\n")
    print(f"📍 API : http://{settings.HOST}:{settings.PORT}")
    print(f"📖 Docs : http://{settings.HOST}:{settings.PORT}/docs\n")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
