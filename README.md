# 🚀 AnomaFlow - Système de Détection d'Anomalies avec IA

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-AI-7CFC00?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)

**Analyse automatique de transactions financières avec intelligence artificielle**

[Fonctionnalités](#-fonctionnalités) •
[Installation](#-installation) •
[Utilisation](#-utilisation) •
[API](#-api) •
[Structure](#-structure-du-projet)

</div>

## 📋 Table des Matières
- [🌟 Aperçu](#-aperçu)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🛠️ Installation](#️-installation)
- [🚀 Utilisation](#-utilisation)
- [🔧 API Endpoints](#-api-endpoints)
- [🏗️ Structure du Projet](#️-structure-du-projet)
- [🤖 Intégration IA](#-intégration-ia)
- [📊 Exemples](#-exemples)
- [🤝 Contribution](#-contribution)
- [📄 Licence](#-licence)

## 🌟 Aperçu

**AnomaFlow** est une application web moderne de détection d'anomalies dans les transactions financières, alimentée par l'intelligence artificielle de **Groq**. Le système analyse automatiquement les fichiers CSV de transactions, détecte les comportements suspects et génère des rapports intelligents avec recommandations actionnables.

### Cas d'utilisation
- 🏦 **Bancaire** : Détection de fraude et transactions suspectes
- 💳 **Fintech** : Surveillance des paiements en temps réel
- 🏢 **Entreprises** : Audit des flux financiers
- 🔍 **Compliance** : Conformité réglementaire (AML/KYC)

## ✨ Fonctionnalités

### 🔍 **Détection d'Anomalies**
- ✅ **Montants ronds suspects** (500€, 1000€, etc.)
- ✅ **Dépassements de seuil** (transactions anormalement élevées)
- ✅ **Fréquences suspectes** (multiples transactions rapides)
- ✅ **Patterns inhabituels** (heures non standards, etc.)

### 🤖 **Intelligence Artificielle**
- 📊 **Analyse contextuelle** avec Groq (mixtral-8x7b-32768)
- 🎯 **Rapports intelligents** avec recommandations spécifiques
- ⚡ **Temps réel** : Génération de rapports en quelques secondes
- 📈 **Évolutif** : Ajoutez vos propres règles de détection

### 🛡️ **Sécurité & Gestion**
- 🔐 **Authentification JWT** sécurisée
- 📁 **Upload sécurisé** de fichiers CSV
- 🗄️ **Base de données** SQLite avec historique
- 📊 **Dashboard** web intuitif

## 🛠️ Installation

### Prérequis
- Python 3.8 ou supérieur
- pip (gestionnaire de packages Python)
- Clé API Groq (gratuite sur [console.groq.com](https://console.groq.com))

### 🚀 Installation Rapide

```bash
# 1. Cloner ou télécharger le projet
cd /chemin/vers/votre/dossier

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env et ajouter votre clé Groq: GROQ_API_KEY=votre_clé_ici

# 4. Lancer le serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

📦 Dépendances Principales

```txt
fastapi==0.104.1           # Framework web
uvicorn[standard]==0.24.0  # Serveur ASGI
sqlalchemy==2.0.23         # ORM base de données
pandas==2.1.4              # Analyse de données
groq==0.3.0                # API IA Groq
python-jose[cryptography]==3.3.0  # JWT tokens
```

🚀 Utilisation

🌐 Interface Web

1. Accédez à http://localhost:8000 dans votre navigateur
2. Inscrivez-vous avec votre email
3. Connectez-vous à votre compte
4. Téléchargez un fichier CSV de transactions
5. Visualisez le rapport d'analyse généré automatiquement

📁 Format du Fichier CSV

```csv
transaction_id,user_id,amount,timestamp
TX001,USER_A,150.50,2025-01-01 09:00:00
TX002,USER_B,2200.00,2025-01-01 09:15:00
TX003,USER_C,500.00,2025-01-01 10:00:00
```

💻 Ligne de Commande

```bash
# Tester l'API avec curl
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password","full_name":"Test User"}'

# Uploader un fichier
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer VOTRE_TOKEN_JWT" \
  -F "file=@transactions.csv"
```

🔧 API Endpoints

🔐 Authentification

Méthode Endpoint Description
POST /auth/register Inscription utilisateur
POST /auth/login Connexion (obtention token)
POST /auth/logout Déconnexion

📊 Analyse de Transactions

Méthode Endpoint Description
POST /upload Upload et analyse de fichier CSV
GET /reports/{id} Récupération d'un rapport
GET /reports/user/{user_id} Liste des rapports d'un utilisateur

👤 Gestion Utilisateur

Méthode Endpoint Description
GET /users/me Informations du profil
PUT /users/me Mise à jour du profil

🏗️ Structure du Projet

```
anomaflow/
├── 📁 app/                    # Application principale
│   ├── 📁 api/               # Endpoints API
│   ├── 📁 core/              # Configuration et sécurité
│   ├── 📁 models/            # Modèles de données
│   ├── 📁 services/          # Logique métier
│   │   ├── detector.py       # Détection d'anomalies
│   │   └── ai_reporter.py    # Service IA Groq
│   ├── 📁 templates/         # Templates HTML
│   └── main.py              # Point d'entrée FastAPI
├── 📁 uploads/               # Fichiers uploadés
├── .env                     # Variables d'environnement
├── requirements.txt         # Dépendances Python
├── anomaflow.db            # Base de données SQLite
└── README.md               # Documentation
```

🤖 Intégration IA

🔗 Connexion à Groq

AnomaFlow utilise l'API Groq pour générer des rapports intelligents :

```python
# Exemple de prompt IA
prompt = f"""
Tu es un expert en analyse financière et détection de fraude.

ANALYSE À EFFECTUER:
- Fichier: {total_transactions} transactions
- Anomalies détectées: {anomalies_count}
- Type d'anomalies: {anomaly_types}

TON RÔLE:
Fournir une analyse concise avec:
1. Évaluation du risque
2. Recommandations actionnables
3. Priorités de surveillance
"""
```

🎯 Modèles Groq Supportés

· mixtral-8x7b-32768 (recommandé)
· gemma2-9b-it
· llama3-70b-8192

⚙️ Configuration IA

```env
# Fichier .env
GROQ_API_KEY=votre_clé_api_groq_ici
IA_MODEL=mixtral-8x7b-32768
IA_MAX_TOKENS=500
IA_TEMPERATURE=0.7
```

📊 Exemples

📈 Exemple de Rapport IA

```
🤖 RAPPORT IA - ANALYSE DE TRANSACTIONS
========================================
📊 STATISTIQUES:
• Total transactions: 50
• Anomalies détectées: 8 (16%)

🎯 RISQUE PRINCIPAL:
Transactions rondes répétées chez 3 utilisateurs différents

⚡ RECOMMANDATIONS:
1. Vérifier les transactions > 1000€ de USER_123
2. Examiner la fréquence de USER_456 (5 transactions/heure)
3. Surveiller les montants ronds de USER_789

🔍 SURVEILLANCE:
• Transactions rondes > 500€
• Fréquence > 3 transactions/heure
• Montants > 5000€
```

📁 Exemple de CSV

```csv
transaction_id,user_id,amount,timestamp,description
TX2025001,CUST001,250.75,2025-01-15 09:30:00,Paiement café
TX2025002,CUST002,1000.00,2025-01-15 10:15:00,Virement
TX2025003,CUST003,500.00,2025-01-15 11:00:00,Achat en ligne
TX2025004,CUST001,300.25,2025-01-15 11:30:00,Course
TX2025005,CUST004,1500.00,2025-01-15 12:00:00,Transfert
```

🚀 Déploiement

🐳 Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

☁️ Cloud

· Render.com (backend gratuit)
· Railway.app (déploiement facile)
· PythonAnywhere (hébergement Python)
· Heroku (avec Docker)

🔒 Sécurité Production

```python
# Conseils de sécurité
SECRET_KEY = os.getenv("SECRET_KEY")  # Longueur > 32 caractères
CORS_ORIGINS = ["https://votredomaine.com"]  # Restreindre les origines
RATE_LIMIT = "100/hour"  # Limiter les requêtes
```

🤝 Contribution

Les contributions sont les bienvenues ! Voici comment contribuer :

1. Fork le projet
2. Créez une branche (git checkout -b feature/AmazingFeature)
3. Commitez vos changements (git commit -m 'Add some AmazingFeature')
4. Push vers la branche (git push origin feature/AmazingFeature)
5. Ouvrez une Pull Request

📋 Checklist de Développement

· Tests unitaires écrits
· Documentation mise à jour
· Code conforme à PEP8
· Pas de secrets dans le code
· Logging approprié

📄 Licence

Ce projet est sous licence MIT - voir le fichier LICENSE pour plus de détails.

📞 Support & Contact

Pour toute question, suggestion ou problème :

· 📧 Email : clarelbamigbe@gmail.com 
· 🐛 Issues : 
· 💬 Discussions :
° Github : Sirius464 

🙏 Remerciements

· FastAPI pour le framework web incroyable
· Groq pour l'API IA performante
· SQLAlchemy pour l'ORM Python
· Tous les contributeurs qui améliorent ce projet

---

<div align="center">

Fait avec ❤️ pour la communauté des développeurs

⬆ Revenir en haut

</div>
