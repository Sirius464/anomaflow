# ══════════════════════════════════════════════════════════════════
#  AnomaFlow v2.0 — Makefile
#  Usage : make <cible>
# ══════════════════════════════════════════════════════════════════

.PHONY: help install dev test test-cov lint format migrate docker-build docker-up docker-down clean sample-csv

# Détection automatique de l'interpréteur Python
PYTHON   := $(shell command -v python3 2>/dev/null || echo python)
PIP      := $(PYTHON) -m pip
UVICORN  := $(PYTHON) -m uvicorn
PYTEST   := $(PYTHON) -m pytest
DB_PATH  := ./anomaflow.db

# Couleurs
CYAN  := \033[36m
RESET := \033[0m
BOLD  := \033[1m

help: ## Affiche cette aide
	@echo ""
	@echo "$(BOLD)AnomaFlow v2.0 — Commandes disponibles$(RESET)"
	@echo "────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Installation ──────────────────────────────────────────────────

install: ## Installer toutes les dépendances (prod + dev)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "✅ Dépendances installées"

install-dev: install ## Installer les dépendances + outils de dev
	$(PIP) install pre-commit ruff mypy
	pre-commit install
	@echo "✅ Environnement dev prêt"

# ── Développement ─────────────────────────────────────────────────

dev: ## Démarrer le serveur en mode développement (hot-reload)
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

prod: ## Démarrer en mode production (2 workers)
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --workers 2

sample-csv: ## Générer un CSV de test avec anomalies
	$(PYTHON) generate_sample_csv.py
	@echo "✅ Fichier sample_transactions.csv généré"

# ── Tests ─────────────────────────────────────────────────────────

test: ## Lancer tous les tests
	$(PYTEST)

test-cov: ## Tests avec rapport de couverture
	$(PYTEST) --cov=app --cov-report=term-missing --cov-report=html
	@echo "📊 Rapport HTML : htmlcov/index.html"

test-fast: ## Tests rapides (sans ML)
	ML_ENABLED=false $(PYTEST) -x -q

test-auth: ## Tests d'authentification uniquement
	$(PYTEST) tests/test_auth.py -v

test-detector: ## Tests du détecteur uniquement
	$(PYTEST) tests/test_detector.py -v

# ── Qualité de code ───────────────────────────────────────────────

lint: ## Vérifier le code avec ruff
	$(PYTHON) -m ruff check app/ tests/

format: ## Formater le code avec ruff
	$(PYTHON) -m ruff format app/ tests/
	$(PYTHON) -m ruff check --fix app/ tests/

typecheck: ## Vérification de types avec mypy
	$(PYTHON) -m mypy app/ --ignore-missing-imports

# ── Base de données ───────────────────────────────────────────────

migrate-dry: ## Prévisualiser la migration v1→v2 (sans modifier)
	$(PYTHON) migrate_v1_to_v2.py --db-path $(DB_PATH) --dry-run

migrate: ## Appliquer la migration v1→v2
	$(PYTHON) migrate_v1_to_v2.py --db-path $(DB_PATH)

db-reset: ## ⚠️  Supprimer la base de données (IRRÉVERSIBLE)
	@read -p "Supprimer $(DB_PATH) ? [y/N] " ans; \
	[ "$$ans" = "y" ] && rm -f $(DB_PATH) && echo "✅ Base supprimée" || echo "Annulé"

# ── Docker ────────────────────────────────────────────────────────

docker-build: ## Construire l'image Docker
	docker build -t anomaflow:v2 .

docker-up: ## Démarrer avec Docker Compose
	docker compose up -d
	@echo "✅ AnomaFlow démarré sur http://localhost:8000"

docker-up-prod: ## Démarrer en mode production (Caddy HTTPS)
	docker compose --profile prod up -d

docker-down: ## Arrêter les conteneurs
	docker compose down

docker-logs: ## Afficher les logs en temps réel
	docker compose logs -f anomaflow

docker-shell: ## Ouvrir un shell dans le conteneur
	docker compose exec anomaflow /bin/sh

# ── Nettoyage ─────────────────────────────────────────────────────

clean: ## Supprimer les fichiers temporaires et caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	@echo "✅ Nettoyage terminé"

clean-all: clean db-reset ## Tout nettoyer (cache + DB)
