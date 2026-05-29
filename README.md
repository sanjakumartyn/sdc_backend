# Sales Intelligence Backend (Flat Architecture)

A modern, highly modular Django and Django Ninja backend designed with a **Repository-Service-Route** (Controller) architecture, laid out flat in the repository root.

## Architecture Highlights
- **Django & Django Ninja:** Ultra-fast, type-safe API endpoints using Pydantic schemas. Includes automatic interactive OpenAPI/Swagger documentation at `/api/docs`.
- **Decoupled Architecture (Repository-Service Pattern):**
  - **Models:** Pure database tables defined via Django ORM.
  - **Repositories:** Encapsulated database operations. Services query databases only via repositories, ensuring easy swapping of databases or querying layers.
  - **Services:** Pure business logic. All validations, logic checks, external integrations, and calculations reside here.
  - **Routes (Controllers):** Handles HTTP parameters, schema validations, calling services, and returning structured JSON API responses.
- **Shared Middleware & Utility Layer:**
  - **JWT Handler:** (removed) JSON Web Token support has been disabled.
  - **Global Exception handling:** Catches domain, validation, and database exceptions, formatting them into standardized, beautiful API error schemas.
  - **JSON Response Builders:** Guarantees all responses follow a standard envelope.

---

## Directory Structure
```
SDC_backend/
├── manage.py                   # Root Django management entrypoint
├── core/                       # Configuration settings, route routing definitions, constants
├── shared/                     # Cross-cutting concerns: exceptions, responses, security, utils
├── modules/                    # Business feature domains (e.g. signals, deals)
├── tests/                      # Global end-to-end and integrations tests
├── .env.example                # Local environment setup template
└── requirements.txt            # Dependency configuration
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+
- Pip & Virtual Environment tools

### 2. Setup environment
Create a virtual environment and activate it from the repository root:
```bash
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Create a local `.env` configuration file from the template:
```bash
cp .env.example .env
```

### 3. Run migrations & Server
Create the initial database structures:
```bash
python manage.py migrate
```

Start the local development server:
```bash
python manage.py runserver
```

Open the Swagger documentation in your browser to inspect and interact with the endpoints:
- [Interactive API Documentation (Swagger)](http://127.0.0.1:8000/api/docs)
- [Alternative Redoc Documentation](http://127.0.0.1:8000/api/redoc)
