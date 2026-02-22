"""
AnomaFlow v2.0 — Fixtures pytest partagées
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Base de données en mémoire partagée ──────────────────────────────────────
# StaticPool : CRITIQUE pour SQLite :memory: en tests
# Sans StaticPool, chaque connexion ouvre une base vide distincte →
# Base.metadata.create_all() crée les tables sur la connexion A,
# mais TestSession() ouvre la connexion B et ne les voit pas.
TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """
    Engine SQLite en mémoire avec StaticPool.
    Une seule connexion partagée par tous les accès → tables toujours visibles.
    Recréé (et donc vidé) à chaque test.
    """
    from app.core.database import Base

    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # ← clé du fix : connexion unique partagée
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Session de base de données pour les tests unitaires."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db_engine):
    """TestClient FastAPI avec base de données en mémoire injectée."""
    from app.main import app
    from app.core.database import get_db
    from app.config import settings

    # Désactiver le ML pour les tests (évite les faux positifs IsolationForest)
    # On patch directement l'objet settings déjà instancié (os.environ trop tard)
    original_ml = settings.ML_ENABLED
    settings.ML_ENABLED = False

    TestSession = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    # Restaurer l'état original après le test
    app.dependency_overrides.clear()
    settings.ML_ENABLED = original_ml


@pytest.fixture
def auth_headers(client):
    """Enregistre un utilisateur test et retourne ses headers JWT."""
    client.post("/auth/register", json={
        "email": "test@anomaflow.io",
        "password": "securepass123",
        "full_name": "Test User",
    })
    res = client.post("/auth/login", json={
        "email": "test@anomaflow.io",
        "password": "securepass123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── DataFrames de test ────────────────────────────────────────────────────────

@pytest.fixture
def normal_df():
    """DataFrame sans anomalies — montants normaux, fréquence basse."""
    now = datetime(2025, 6, 15, 10, 0, 0)
    rows = []
    for i in range(20):
        rows.append({
            "transaction_id": f"TX{i:04d}",
            "user_id":        f"USER_{i % 5:02d}",
            "amount":         float(50 + i * 3),     # 50–107 €, distribution normale
            "timestamp":      now + timedelta(hours=i),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def anomalous_df():
    """DataFrame avec toutes les catégories d'anomalies."""
    now = datetime(2025, 6, 15, 10, 0, 0)
    rows = [
        # Transactions normales (base)
        *[{"transaction_id": f"TX{i:04d}", "user_id": "USER_01", "amount": 55.0 + i,
           "timestamp": now + timedelta(hours=i)} for i in range(10)],
        # Montant élevé (unusual_amount)
        {"transaction_id": "TX9001", "user_id": "USER_99", "amount": 99999.0,
         "timestamp": now + timedelta(hours=11)},
        # Montant quasi-rond (round_amount)
        {"transaction_id": "TX9002", "user_id": "USER_88", "amount": 500.01,
         "timestamp": now + timedelta(hours=12)},
        {"transaction_id": "TX9003", "user_id": "USER_88", "amount": 999.98,
         "timestamp": now + timedelta(hours=13)},
        # Haute fréquence (high_frequency) : 12 transactions en 1h pour USER_77
        *[{"transaction_id": f"TX800{i}", "user_id": "USER_77", "amount": 10.0,
           "timestamp": now + timedelta(minutes=i*4)} for i in range(12)],
        # Hors-heures (off_hours) : 23h00
        {"transaction_id": "TX9010", "user_id": "USER_66", "amount": 200.0,
         "timestamp": datetime(2025, 6, 15, 23, 0, 0)},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def minimal_csv_bytes():
    """Contenu CSV valide minimal sous forme de bytes."""
    content = (
        "transaction_id,user_id,amount,timestamp\n"
        "TX001,USER_A,150.50,2025-01-01 09:00:00\n"
        "TX002,USER_B,2200.00,2025-01-01 09:15:00\n"
        "TX003,USER_C,500.00,2025-01-01 10:00:00\n"
    )
    return content.encode("utf-8")
