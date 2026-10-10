# NETRA-X — AI-Powered Criminal Network Analysis System

## Phase 1: Data Ingestion, Document Processing & Entity Extraction

NETRA-X is an AI-powered criminal network analysis system designed to help investigators convert unstructured investigation documents into structured, traceable entities.

> **⚠️ IMPORTANT**: This system uses synthetic demo data only. No real criminal or personally identifying data is used. All AI/NLP results are extraction results requiring human verification — they do not represent proof of criminal activity.

---

## Architecture

```
Document Upload → Text Extraction → OCR (if needed) → Text Cleaning
    → Entity Extraction (Regex + NER + optional LLM)
    → Entity Merging → Normalization → Confidence Scoring
    → Entity Mentions / Evidence Mapping → Human Verification
    → PostgreSQL
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Document Processing | PyMuPDF (fitz), Tesseract OCR |
| NLP | spaCy (pretrained NER) |
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- (Optional) Tesseract OCR for scanned documents

### 1. Database Setup

```bash
createdb netrax_db
```

### 2. Backend Setup

```bash
cd netrax/backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Copy and configure environment
cp ../.env.example ../.env

# Run migrations
alembic upgrade head

# Generate synthetic test data
python -m app.scripts.generate_synthetic_data

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd netrax/frontend
npm install
npm run dev
```

The application will be available at `http://localhost:5173`

### 4. Docker Setup (Alternative)

```bash
cd netrax
docker-compose up -d
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
netrax/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI routes
│   │   ├── models/              # SQLAlchemy persistence models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── scripts/             # Data generation and maintenance scripts
│   │   ├── services/
│   │   │   ├── extraction/      # Text, OCR, and regex extraction
│   │   │   ├── nlp/             # NER and optional LLM extraction
│   │   │   ├── normalization/   # Text and entity normalization
│   │   │   ├── processing/      # Document processing pipeline
│   │   │   └── resolution/      # Entity matching and graph sync
│   │   ├── config.py            # Environment-backed application settings
│   │   ├── database.py          # Database engine and sessions
│   │   └── main.py              # FastAPI application entry point
│   ├── alembic/
│   │   └── versions/            # Database migration revisions
│   ├── data/synthetic/          # Synthetic backend test/demo data
│   ├── database/                # Database-related resources
│   ├── tests/                   # Backend unit and integration tests
│   ├── Dockerfile
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── public/                  # Static frontend assets
│   ├── src/
│   │   ├── assets/              # Imported UI assets
│   │   ├── pages/               # Dashboard, case, document, and graph views
│   │   ├── services/            # Backend API client
│   │   ├── types/               # Shared TypeScript types
│   │   ├── utils/               # Frontend utilities
│   │   ├── App.tsx              # Routes and application shell
│   │   └── main.tsx             # React entry point
│   ├── package.json
│   └── vite.config.ts
├── data/synthetic/              # Shared synthetic investigation data
├── docker-compose.yml
├── .env.example
└── README.md
```

The backend is organized by responsibility: API routes call services, services process and resolve entities, and models/schemas define persistence and API data. The frontend consumes the backend through `src/services/api.ts`. Local virtual environments, caches, databases, uploads, and build outputs are generated at runtime and are not part of the source layout.

## Key Features (Phase 1)

- **Document Upload**: Drag & drop PDF, TXT, CSV files
- **Text Extraction**: PyMuPDF with OCR fallback
- **Entity Extraction**: Regex + spaCy NER + optional LLM
- **Evidence Traceability**: Every entity traced to document → page → text span
- **Human Verification**: Verify, reject, or edit extracted entities
- **Confidence Scoring**: Per-extraction confidence with documented strategy
- **Case Management**: Basic case support for organizing documents

## Entity Types

| Type | Extraction Method |
|------|------------------|
| PERSON | NER, LLM |
| PHONE | Regex |
| EMAIL | Regex |
| LOCATION | NER, LLM |
| ORGANIZATION | NER, LLM |
| VEHICLE | Regex |
| CASE/FIR | Regex |
| ACCOUNT | Regex |
| DEVICE (IMEI) | Regex |
| DATE | NER, Regex |

## License

Proprietary — Internal Use Only
