# ══════════════════════════════════════════════════════════════════
#  AnomaFlow v2.0 — Dockerfile multi-stage
#  Stage 1 (builder) : installation des dépendances
#  Stage 2 (runtime) : image minimale sans outils de build
# ══════════════════════════════════════════════════════════════════

# ── Stage 1 : builder ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Dépendances système pour numpy/pandas/scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Installer dans un dossier isolé pour le copier proprement ensuite
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2 : runtime ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="AnomaFlow <clarelbamigbe@gmail.com>" \
      version="2.0.0" \
      description="Détection d'anomalies transactionnelles"

# Utilisateur non-root pour la sécurité
RUN groupadd -r anomaflow && useradd -r -g anomaflow -d /app -s /sbin/nologin anomaflow

WORKDIR /app

# Dépendances runtime uniquement (pas gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages Python depuis le builder
COPY --from=builder /install /usr/local

# Copier l'application
COPY app/ ./app/
COPY .env.example .env.example

# Dossiers avec permissions
RUN mkdir -p uploads \
    && chown -R anomaflow:anomaflow /app

USER anomaflow

# Variables d'environnement par défaut (surchargées via docker-compose ou -e)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--no-access-log"]
