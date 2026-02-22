# Changelog — AnomaFlow

Toutes les modifications notables sont documentées ici.
Format : [Semantic Versioning](https://semver.org/lang/fr/)

---

## [2.0.0] — 2026-02-22

### 🆕 Ajouté
- `POST /auth/logout` — révocation JWT via blacklist en mémoire avec TTL automatique
- `PUT /users/me` — modification du nom complet et du mot de passe
- `GET /reports/user/{user_id}` — accès aux rapports d'un utilisateur
- Pagination sur `GET /reports` (`?page=1&page_size=20`)
- Détection **hors-heures** (`off_hours`) : transactions entre 22h–6h UTC
- Détection **montants quasi-ronds** avec tolérance ±2% (configurable)
- Détection **IsolationForest** (scikit-learn) si `ML_ENABLED=true`
- **Score de risque global** 0–100 avec niveaux FAIBLE / MODÉRÉ / ÉLEVÉ / CRITIQUE
- Retry automatique avec backoff exponentiel sur erreur 429/5xx Groq (3 tentatives)
- Vérification de la taille du fichier uploadé (`MAX_UPLOAD_SIZE`, HTTP 413)
- Dashboard v2 : SPA complète, sidebar dark, modal rapport, score de risque visuel
- Page login v2 : onglets connexion/inscription, redirect automatique
- `app_fallback.html` : upload fonctionnel en mode dégradé
- 55+ tests pytest (`test_detector`, `test_auth`, `test_upload`, `conftest`)
- `migrate_v1_to_v2.py` : migration base de données avec backup auto et `--dry-run`
- `generate_sample_csv.py` : générateur de CSV de test avec anomalies injectées
- `Dockerfile` multi-stage (builder + runtime, utilisateur non-root)
- `docker-compose.yml` avec profil `prod` (Caddy HTTPS automatique)
- `Makefile` avec commandes dev quotidiennes (`make dev`, `make test`, etc.)
- `.pre-commit-config.yaml` : hooks ruff + trailing whitespace
- `CHANGELOG.md` et `README.md` v2 complets

### 🐛 Corrigé
- **Détection de fréquence** : comptait le total du fichier entier → corrigé en fenêtre glissante d'1 heure réelle
- **Montants ronds** : égalité stricte manquait 999.99€ → remplacé par tolérance ±2%
- **Doublons** : une même transaction pouvait apparaître plusieurs fois → déduplication par `(transaction_id, anomaly_type)`
- **`analyze_anomaly_patterns()`** : fonction orpheline jamais appelée → devient la fonction principale de `ai_reporter.py`
- **Modèle Groq** : hardcodé dans `ai_reporter.py` → centralisé via `settings.GROQ_MODEL`
- **`declarative_base()`** : déprécié en SQLAlchemy 2.x → remplacé par `DeclarativeBase`
- **`Anomaly.timestamp`** : type `String` → `DateTime` pour requêtes temporelles
- **`LOG_LEVEL`** : présent dans `.env.example` mais absent de la classe `Settings`
- **`passlib` + Python 3.12+** : warnings bcrypt → fallback `pbkdf2_sha256` par défaut

### 🔄 Modifié
- `config.py` : `SECRET_KEY` auto-générée si absente (dev), avertissement en prod
- `ai_reporter.py` : fallback dégradé enrichi avec sévérités et top 5 anomalies
- `detector.py` : anomalies triées par sévérité puis score de confiance décroissant
- `main.py` : schéma `LoginRequest` séparé de `UserCreate`, HTTP 409 pour email dupliqué
- `requirements.txt` : versions `>=` / `~=` au lieu de `==` fixes pour compatibilité Python 3.11–3.13

---

## [1.0.0] — 2025-01-01

### 🆕 Initial
- Détection d'anomalies : montants élevés, montants ronds, haute fréquence
- Intégration Groq (`mixtral-8x7b-32768`)
- Authentification JWT (register, login)
- Upload CSV et stockage SQLite
- Dashboard HTML (Jinja2)
- `GET /reports`, `GET /reports/{id}`, `GET /dashboard`
