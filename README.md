<div align="center">

```
█████╗ ███╗   ██╗ ██████╗ ███╗   ███╗ █████╗ ███████╗██╗      ██████╗ ██╗    ██╗
██╔══██╗████╗  ██║██╔═══██╗████╗ ████║██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║
███████║██╔██╗ ██║██║   ██║██╔████╔██║███████║█████╗  ██║     ██║   ██║██║ █╗ ██║
██╔══██║██║╚██╗██║██║   ██║██║╚██╔╝██║██╔══██║██╔══╝  ██║     ██║   ██║██║███╗██║
██║  ██║██║ ╚████║╚██████╔╝██║ ╚═╝ ██║██║  ██║██║     ███████╗╚██████╔╝╚███╔███╔╝
╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝
```

**Détection d'anomalies dans les transactions financières — propulsée par l'IA**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-07405E?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Groq](https://img.shields.io/badge/Groq_AI-LLaMA_3.3-00B37E?style=flat-square)](https://console.groq.com)
[![scikit-learn](https://img.shields.io/badge/sklearn-IsolationForest-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-76%20passed-2dd4bf?style=flat-square)](./tests)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](./LICENSE)

[**Démo rapide**](#-démarrage-rapide) · [**API**](#-endpoints-api) · [**Docker**](#-docker) · [**v1 → v2**](#-migration-v1--v2)

</div>

---

## 🧠 Ce que fait AnomaFlow

AnomaFlow analyse des fichiers CSV de transactions financières et détecte automatiquement les comportements suspects grâce à **5 méthodes combinées** :

| Méthode | Ce qu'elle détecte | Sévérité |
|---|---|---|
| **Montant anormal** | Dépassement statistique (µ + N×σ) | 🔴 HIGH |
| **Haute fréquence** | > 10 tx/heure par utilisateur (fenêtre glissante) | 🔴 HIGH |
| **Montant quasi-rond** | Proches de 500€, 1000€… à ±2% | 🟡 MEDIUM |
| **Hors-heures** | Transactions entre 22h et 6h UTC | 🟢 LOW |
| **IsolationForest** | Comportement multivarié anormal (ML) | 🟡/🔴 |

Chaque analyse produit un **score de risque 0–100** et un **rapport narratif généré par Groq AI**.

---

## ✨ Nouveautés v2.0 vs v1

<details>
<summary>Voir le tableau complet des changements</summary>

| Fonctionnalité | v1 | v2 |
|---|---|---|
| Détection fréquence | Total fichier ❌ | Fenêtre glissante 1h ✅ |
| Montants quasi-ronds | Égalité stricte ❌ | Tolérance ±2% ✅ |
| Heures suspectes | Absent ❌ | 22h–6h configurable ✅ |
| Machine Learning | Non codé ❌ | IsolationForest ✅ |
| Score de risque | Absent ❌ | 0–100 avec niveaux ✅ |
| Rapport IA | Prompt 3 lignes ❌ | Analyse enrichie 5 sections ✅ |
| Retry API Groq | Absent ❌ | Backoff exponentiel ✅ |
| `POST /auth/logout` | Absent ❌ | JWT blacklist + TTL ✅ |
| `PUT /users/me` | Absent ❌ | Nom + mot de passe ✅ |
| `GET /reports/user/{id}` | Absent ❌ | Présent ✅ |
| Pagination | Absent ❌ | `?page=1&page_size=20` ✅ |
| Vérification taille CSV | Absent ❌ | HTTP 413 si > 10Mo ✅ |
| Dashboard | Basique ❌ | SPA dark, score de risque ✅ |
| Tests | Aucun ❌ | 76 tests pytest ✅ |
| Docker | Absent ❌ | Multi-stage + Caddy HTTPS ✅ |

</details>

---

## 🚀 Démarrage rapide

### Prérequis

- **Python 3.11+** — `python --version`
- **Git**
- Clé API Groq **gratuite** : [console.groq.com](https://console.groq.com) *(optionnelle — mode dégradé si absente)*

### Installation en 5 commandes

```bash
# 1. Cloner
git clone https://github.com/Sirius464/anomaflow.git
cd anomaflow

# 2. Environnement virtuel
python -m venv venv && source venv/bin/activate
# Windows : venv\Scripts\activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
# Éditez .env : ajoutez SECRET_KEY et optionnellement GROQ_API_KEY

# 5. Lancer
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Générer une SECRET_KEY sécurisée :**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

✅ Ouvrez [http://localhost:8000/login](http://localhost:8000/login)
📖 Documentation API : [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📋 Format CSV attendu

```csv
transaction_id,user_id,amount,timestamp
TX001,CUST_A,150.50,2025-01-15 09:30:00
TX002,CUST_B,1000.00,2025-01-15 10:15:00
TX003,CUST_C,500.01,2025-01-15 23:45:00
```

**Colonnes obligatoires :** `transaction_id` · `user_id` · `amount` · `timestamp`

> Générer un CSV de test avec anomalies injectées :
> ```bash
> python generate_sample_csv.py
> # → sample_transactions.csv (106 lignes, 26 anomalies de 4 types)
> ```

---

## 🔧 Endpoints API

```
POST /auth/register             Créer un compte
POST /auth/login                Obtenir un token JWT
POST /auth/logout               Révoquer le token (blacklist)

GET  /users/me                  Mon profil
PUT  /users/me                  Modifier nom / mot de passe

POST /upload                    Uploader et analyser un CSV
GET  /reports                   Mes rapports (paginés)
GET  /reports/{id}              Détail d'un rapport + rapport IA
GET  /reports/user/{user_id}    Rapports d'un utilisateur
GET  /dashboard                 Statistiques globales
GET  /health                    État du serveur
```

<details>
<summary>Exemples curl complets</summary>

```bash
# Inscription
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"vous@exemple.com","password":"motdepasse123","full_name":"Votre Nom"}'

# Login + récupération du token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vous@exemple.com","password":"motdepasse123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Uploader un CSV
curl -s -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_transactions.csv" | python -m json.tool

# Modifier son profil
curl -s -X PUT http://localhost:8000/users/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Nouveau Nom"}'

# Logout (révoque le token)
curl -s -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP %{http_code}\n"
```

</details>

---

## ⚙️ Configuration `.env`

```env
# Obligatoire
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">

# Groq AI (optionnel)
GROQ_API_KEY=votre_cle_groq
GROQ_MODEL=llama-3.3-70b-versatile

# Détection
ANOMALY_THRESHOLD_MULTIPLIER=3.0
MAX_TRANSACTIONS_PER_HOUR=10
ROUND_AMOUNT_TOLERANCE=0.02
SUSPICIOUS_HOUR_START=22
SUSPICIOUS_HOUR_END=6

# ML
ML_ENABLED=true
ML_CONTAMINATION=0.05

# App
DEBUG=false
LOG_LEVEL=INFO
```

---

## 🐳 Docker

```bash
cp .env.example .env   # puis ajouter SECRET_KEY

# Développement
docker compose up

# Production (HTTPS automatique via Caddy + Let's Encrypt)
DOMAIN=votredomaine.com docker compose --profile prod up -d
```

---

## 🧪 Tests

```bash
python -m pytest -v                              # 76 tests
python -m pytest --cov=app --cov-report=term-missing  # avec couverture
python -m pytest tests/test_detector.py -v      # détection uniquement
```

Les tests utilisent SQLite **en mémoire isolée** (StaticPool) — aucune donnée de production touchée.

---

## 🗄️ Migration v1 → v2

```bash
# Prévisualiser
python migrate_v1_to_v2.py --dry-run

# Appliquer (sauvegarde automatique créée)
python migrate_v1_to_v2.py --db-path ./anomaflow.db
```

---

## 🏗️ Structure du projet

```
anomaflow/
├── app/
│   ├── main.py                  # Routes + CORS + middleware sécurité
│   ├── config.py                # Configuration centralisée
│   ├── core/
│   │   ├── database.py          # Modèles SQLAlchemy 2.x
│   │   └── security.py          # JWT + blacklist logout
│   ├── services/
│   │   ├── detector.py          # 4 règles + IsolationForest
│   │   └── ai_reporter.py       # Rapports Groq + retry + fallback
│   └── templates/               # Dashboard, login, fallback
├── tests/                       # 76 tests pytest
├── generate_sample_csv.py        # CSV de test avec anomalies
├── migrate_v1_to_v2.py          # Migration base de données
├── Dockerfile                   # Multi-stage, utilisateur non-root
├── docker-compose.yml           # Dev + profil prod Caddy
├── Makefile                     # make dev / test / migrate…
├── requirements.txt
└── .env.example
```

---

## 📊 Score de risque

| Score | Niveau | Action recommandée |
|---|---|---|
| 0–24 | 🟢 FAIBLE | Surveillance normale |
| 25–49 | 🔵 MODÉRÉ | Révision conseillée |
| 50–74 | 🟡 ÉLEVÉ | Investigation nécessaire |
| 75–100 | 🔴 CRITIQUE | Action immédiate |

---

## 📄 Licence

MIT — voir [LICENSE](LICENSE)

---

<div align="center">

**AnomaFlow v2.0** · [@Sirius464](https://github.com/Sirius464)

*[⭐ Star ce projet si il vous a été utile](https://github.com/Sirius464/anomaflow)*

</div>