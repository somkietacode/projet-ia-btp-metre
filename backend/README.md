# Backend — Plateforme IA BTP Métré

API backend FastAPI pour la plateforme d'automatisation du métré BTP par intelligence artificielle.

## Stack Technique

| Composant | Technologie |
|-----------|------------|
| Framework API | FastAPI (Python) |
| Orchestration IA | LangGraph |
| Vision IA | Claude 3.5 Sonnet / GPT-4o |
| Base de données | PostgreSQL (SQLAlchemy) |
| Base vectorielle | Qdrant |
| Conversion PDF | pdf2image (poppler) |
| Monitoring LLM | Arize Phoenix |
| Export | openpyxl (Excel), reportlab (PDF) |
| Auth | JWT |

## Structure

```
backend/
├── app/
│   ├── api/                     # Routes REST + WebSocket
│   ├── models/                  # Modèles SQLAlchemy
│   ├── schemas/                 # Schémas Pydantic
│   ├── services/
│   │   ├── auth.py              # Authentification JWT
│   │   ├── quota.py             # Gestion quotas tokens
│   │   └── export.py            # Export PDF/Excel/CSV
│   ├── agents/                  # Pipeline LangGraph
│   │   ├── graph.py             # Graphe principal d'orchestration
│   │   ├── nodes/
│   │   │   ├── vision.py        # Extraction cotes via LLM vision
│   │   │   ├── detection.py     # Identification des éléments
│   │   │   ├── calcul.py        # Calculs métré
│   │   │   └── validation.py    # Validation des résultats
│   │   └── tools/
│   │       ├── pdf_converter.py # Conversion PDF → images
│   │       ├── ocr_tool.py      # OCR complémentaire
│   │       ├── geometry.py      # Calculs géométriques
│   │       └── metre_calculator.py # Formules métier
│   └── db/                      # Configuration BDD
├── documentation/
│   ├── plan.md                  # Plan d'exécution technique
│   └── model-economique.md      # Modèle économique client
├── Dockerfile
└── requirements.txt
```

## Installation

### Prérequis

- Python 3.11+
- PostgreSQL 15+
- Qdrant
- Poppler (pour pdf2image)

### Setup

```bash
# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos clés API et connexions BDD

# Lancer les migrations
alembic upgrade head

# Démarrer le serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Avec Docker

```bash
docker-compose up backend
```

## Variables d'Environnement

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL PostgreSQL |
| `QDRANT_URL` | URL du serveur Qdrant |
| `ANTHROPIC_API_KEY` | Clé API Claude |
| `OPENAI_API_KEY` | Clé API OpenAI |
| `JWT_SECRET` | Secret pour les tokens JWT |
| `PHOENIX_ENDPOINT` | URL Arize Phoenix |

## Pipeline IA — Flux de Traitement

```
Upload PDF/Image
    → Conversion en images HD (si PDF)
    → Analyse vision LLM (extraction cotes + éléments)
    → Vérification des données (graphe de dépendances)
    → Demande de compléments à l'utilisateur (si données manquantes)
    → Calcul des quantités (Surface, Volume, Comptage, Linéaire)
    → Validation utilisateur
    → Export (PDF / Excel / CSV)
```

## API Endpoints (prévu)

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/auth/register` | Inscription |
| `POST` | `/api/auth/login` | Connexion |
| `POST` | `/api/projects` | Créer un projet |
| `POST` | `/api/projects/{id}/plans` | Uploader un plan |
| `POST` | `/api/projects/{id}/analyze` | Lancer l'analyse IA |
| `GET` | `/api/projects/{id}/results` | Récupérer les résultats |
| `POST` | `/api/projects/{id}/export` | Exporter (PDF/Excel/CSV) |
| `GET` | `/api/params` | Paramètres métier utilisateur |
| `PUT` | `/api/params` | Modifier les paramètres |
| `WS` | `/ws/progress/{id}` | Progression temps réel |

## Documentation

- [Plan d'exécution technique](documentation/plan.md)
- [Modèle économique (client)](documentation/model-economique.md)
