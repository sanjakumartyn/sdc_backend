# Sales Intelligence Backend Steps

This document summarizes the current backend codebase and the steps needed to set up, run, understand, and extend it.

## 1. Project Overview

The backend is a Django 5 project using Django Ninja for API routes.

The code follows a Repository-Service-Route structure:

- `config/` contains Django settings, URL registration, ASGI/WSGI entrypoints, and shared constants.
- `common/` contains shared response envelopes, exception handling, and utility helpers.
- `features/signals/` contains the Signals domain.
- `features/deals/` contains the Deals domain.
- `features/callAgents/` contains the question endpoint that calls external microservices and synthesizes an answer.
- `tests/` is present for global tests, while feature tests live inside each feature folder.

## 2. Install Dependencies

From the `sdc_backend` folder:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Main dependencies:

- `Django`
- `django-ninja`
- `pydantic`
- `python-dotenv`
- `django-cors-headers`
- `django-mongodb-backend`
- `pymongo`
- `dnspython`
- `requests`

## 3. Configure Environment

Create a `.env` file in the `sdc_backend` folder.

Supported environment variables:

```env
SECRET_KEY=replace-me
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=mongodb://localhost:27017/sdc_backend

AGENT_MICROSERVICE_BASE_URL=http://localhost:8001
AGENT_MICROSERVICE_QUESTION_PATH=/question
AGENT_MICROSERVICE_TIMEOUT=30

RAG_MICROSERVICE_BASE_URL=http://localhost:8002
RAG_MICROSERVICE_QUESTION_PATH=/question
RAG_MICROSERVICE_TIMEOUT=30

OCR_MICROSERVICE_BASE_URL=http://127.0.0.1:8001
OCR_EXTRACT_DOCUMENTS_PATH=/extract/documents
OCR_MICROSERVICE_TIMEOUT=60

COMPANY_DATA_ENABLED=true
COMPANY_DATA_LIMIT_PER_COLLECTION=10

LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
GEMINI_TIMEOUT=30

GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions
GROQ_TIMEOUT=30
GROQ_KEYWORD_LIMIT=8
```

Database behavior is resolved from `DATABASE_URL` in `config/settings.py`:

- `mongodb://` or `mongodb+srv://` uses `django_mongodb_backend`.
- `postgres://` or `postgresql://` uses PostgreSQL.
- Any other value is treated like SQLite, with `sqlite:///filename.sqlite3` mapped under the project base directory.

## 4. Run Database Setup

Run migrations from the `sdc_backend` folder:

```powershell
python manage.py migrate
```

The default database URL points to local MongoDB:

```text
mongodb://localhost:27017/sdc_backend
```

Make sure MongoDB is running locally or replace `DATABASE_URL` with a reachable database connection string.

## 5. Start The API Server

Run:

```powershell
python manage.py runserver
```

Useful URLs:

- API base: `http://127.0.0.1:8000/api/`
- Swagger docs: `http://127.0.0.1:8000/api/docs`
- ReDoc docs: `http://127.0.0.1:8000/api/redoc`

## 6. API Registration Flow

The Django URL entrypoint is `config/urls.py`.

Steps:

1. A `NinjaAPI` instance is created with title `Sales Intelligence API`.
2. Global exception handlers are registered through `register_exception_handlers(api)`.
3. Feature routers are imported.
4. Routers are mounted under `/api/`.

Current router prefixes:

- `features.callAgents.routes` is mounted at `/api/question`.
- `features.signals.routes` is mounted at `/api/signals`.
- `features.deals.routes` is mounted at `/api/deals`.
- `features.companydata.routes` is mounted at `/api/companydata`.
- `features.companyAnalysis.routes` is mounted at `/api/company-analysis`.

## 7. Standard Response Format

All successful and error responses are wrapped by `common/response/response_builder.py`.

Success shape:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "timestamp": "2026-06-05T00:00:00+00:00"
}
```

Error shape:

```json
{
  "success": false,
  "data": null,
  "error": {
    "message": "Error message",
    "code": "ERROR_CODE",
    "details": {}
  },
  "timestamp": "2026-06-05T00:00:00+00:00"
}
```

## 8. Exception Handling Flow

Global exception handlers live in `common/exception/global_exception.py`.

Handled cases:

- Custom `APIException` subclasses return their configured HTTP status and error code.
- Django Ninja validation errors return HTTP `422` with field-level validation details.
- Any unhandled exception returns HTTP `500`.
- When `DEBUG=True`, internal exception details are included in the response.

Custom exception types:

- `BadRequestException` maps to HTTP `400`.
- `UnauthorizedException` maps to HTTP `401`.
- `ForbiddenException` maps to HTTP `403`.
- `NotFoundException` maps to HTTP `404`.
- `ServiceUnavailableException` maps to HTTP `503`.
- `GroqApiKeyMissingException` maps to HTTP `503` with code `GROQ_API_KEY_MISSING`.

## 9. Signals Feature Flow

Files:

- Model: `features/signals/models.py`
- Schemas: `features/signals/schema.py`
- Repository: `features/signals/repository.py`
- Service: `features/signals/service.py`
- Routes: `features/signals/routes.py`
- Tests: `features/signals/tests.py`

Model table: `signals`

Fields:

- `title`
- `source`
- `score`
- `payload`
- `status`
- `created_at`
- `updated_at`

Allowed statuses:

- `NEW`
- `PROCESSED`
- `ARCHIVED`

Business rules:

- `title` is stripped and HTML-escaped.
- `source` is stripped, HTML-escaped, and converted to uppercase.
- Empty signal titles are rejected.
- Status updates must match the allowed status list.

Endpoints:

```text
GET    /api/signals
GET    /api/signals/{signal_id}
POST   /api/signals
PUT    /api/signals/{signal_id}
DELETE /api/signals/{signal_id}
```

List filters:

- `status`
- `source`
- `page`
- `limit`

Pagination rules:

- `page` defaults to `1`.
- `limit` defaults to `10`.
- `limit` is capped at `100`.

Create example:

```json
{
  "title": "High Priority Intent Signal",
  "source": "linkedin",
  "score": 90,
  "payload": {
    "source_campaign": "q2_outbound"
  }
}
```

## 10. Deals Feature Flow

Files:

- Model: `features/deals/models.py`
- Schemas: `features/deals/schema.py`
- Repository: `features/deals/repository.py`
- Service: `features/deals/service.py`
- Routes: `features/deals/routes.py`
- Tests: `features/deals/tests.py`

Model table: `deals`

Fields:

- `name`
- `value`
- `stage`
- `probability`
- `close_date`
- `created_at`
- `updated_at`

Allowed stages:

- `PROSPECTING`
- `QUALIFICATION`
- `PROPOSAL`
- `NEGOTIATION`
- `CLOSED_WON`
- `CLOSED_LOST`

Business rules:

- `name` is stripped and HTML-escaped.
- Empty deal names are rejected.
- Deal stage must match the allowed stage list.
- `CLOSED_WON` automatically sets `probability` to `100`.
- `CLOSED_LOST` automatically sets `probability` to `0`.

Endpoints:

```text
GET    /api/deals
GET    /api/deals/{deal_id}
POST   /api/deals
PUT    /api/deals/{deal_id}
DELETE /api/deals/{deal_id}
```

List filters:

- `stage`
- `min_value`
- `page`
- `limit`

Create example:

```json
{
  "name": "Acme Renewal",
  "value": "50000.00",
  "stage": "CLOSED_WON",
  "probability": 60,
  "close_date": "2026-12-31"
}
```

The created deal will store `probability` as `100` because the stage is `CLOSED_WON`.

## 11. Call Agents Question Flow

Files:

- Schemas: `features/callAgents/schema.py`
- Service: `features/callAgents/service.py`
- Routes: `features/callAgents/routes.py`

Endpoint:

```text
POST /api/question
```

Request body:

```json
{
  "account_id": "asian_paints_001",
  "company_name": "Asian Paints",
  "website_url": "https://www.asianpaints.com",
  "company": "Asian Paints",
  "documents": ["document-id-or-url"],
  "question": "optional product question"
}
```

Multipart request with OCR document extraction:

```http
POST http://127.0.0.1:8000/api/question
Content-Type: multipart/form-data

account_id=asian_paints_001
company_name=Asian Paints
website_url=https://www.asianpaints.com
file=@C:\Users\rmsan\Downloads\EV_Fleet_Incident_Management (1).pdf
```

Processing steps:

1. Validate that `company_name` or backward-compatible `company` is present and not blank.
2. Accept `documents` from the request body.
3. Convert document values to trimmed strings and remove blanks.
4. If files are uploaded, send each file to the OCR microservice at `OCR_MICROSERVICE_BASE_URL + OCR_EXTRACT_DOCUMENTS_PATH`.
5. Retrieve internal company data through `CompanyDataService.get_all_data()`.
6. Send `account_id`, `company_name`, and `website_url` to the agent microservice.
7. Ask Groq to generate search keywords and a product RAG question from the company, documents, user question, agent response, OCR extraction, and company data.
8. Send the generated product question to the product RAG microservice with configured project and filter values.
9. Send the generated product question to the case-study RAG microservice with the `casestudy` project and `MY_Company_product_Studies` filter tag.
10. Treat the OCR microservice as required when a file is uploaded.
11. Treat the company-data lookup as optional; if it fails, include `company_data_unavailable` in the internal Groq context.
12. Treat the agent microservice as required.
13. Treat product RAG and case-study RAG as optional; if either service fails, include the upstream error in the internal Groq context and continue.
14. Build a synthesis prompt from the agent, product RAG, case-study RAG, OCR extraction, company-data responses, generated keywords, and product question.
15. Call Groq chat completions for the final answer. `GROQ_API_KEY` is required for this endpoint to succeed.
16. Return only the final answer. Upstream responses, company data, OCR extraction data, generated keywords, and RAG source chunks are used internally but are not exposed in the normal response.

Response data shape:

```json
{
  "answer": "Final Groq-generated answer for the user's question."
}
```

If `GROQ_API_KEY` is missing, the endpoint returns an error instead of raw upstream data:

```json
{
  "success": false,
  "data": null,
  "error": {
    "message": "Groq API key is required to generate the final answer",
    "code": "GROQ_API_KEY_MISSING",
    "details": {}
  },
  "timestamp": "2026-06-05T00:00:00+00:00"
}
```

## 12. Shared Utility Steps

## 12. Company Analysis Dashboard Flow

Files:

- Schemas: `features/companyAnalysis/schema.py`
- Service: `features/companyAnalysis/service.py`
- Routes: `features/companyAnalysis/routes.py`

Endpoints:

```text
POST /api/company-analysis
POST /api/company-analysis/deal-coach
```

Dashboard request:

```json
{
  "account_id": "asian_paints_001",
  "company_name": "Asian Paints",
  "website_url": "https://www.asianpaints.com",
  "documents": [],
  "question": "Create full company analysis dashboard"
}
```

Dashboard response data shape:

```json
{
  "company_name": "Asian Paints",
  "strategic_fit": {
    "score": 94,
    "alignment_level": "High Alignment Probability",
    "explanation": "Evidence-based explanation"
  },
  "meeting_prep": {
    "key_discussion_topics": [],
    "business_priorities": [],
    "executive_talking_points": [],
    "potential_objections": [],
    "recommended_agenda": [],
    "qbr_summary": "Evidence-based QBR summary"
  },
  "intelligence_overview": {
    "company_overview": "Evidence-based overview",
    "industry_position": "Evidence-based position",
    "business_model": "Evidence-based model",
    "strategic_goals": [],
    "expansion_initiatives": [],
    "digital_transformation_efforts": [],
    "sustainability_commitments": []
  },
  "ai_needs_prediction": [],
  "solution_mapping": []
}
```

Deal coach request:

```json
{
  "company_name": "Asian Paints",
  "account_id": "asian_paints_001",
  "message": "Which products should I pitch?"
}
```

Deal coach response data shape:

```json
{
  "answer": "Context-aware sales coaching answer"
}
```

Processing steps:

1. Validate that `company_name` or backward-compatible `company` is present.
2. Gather agent/web intelligence, company data, CRM deals, OCR extraction, product RAG, and case-study RAG.
3. Compact all evidence before sending it to Groq so raw `source_chunks` and debug payloads are not sent.
4. Ask Groq for strict JSON matching the dashboard schema.
5. Validate the Groq JSON with Pydantic before returning it.
6. Return structured dashboard data only; raw upstream payloads are not exposed.
7. For deal coach, use the same compact context plus the user message and return only `answer`.

## 13. Shared Utility Steps

`common/utils/helpers.py` contains reusable helpers:

- `clean_input_string(value)` trims strings and HTML-escapes content.
- `parse_query_param_int(value, default, min_val, max_val)` safely parses integers and applies bounds.

These helpers are used by route and service layers to keep validation behavior consistent.

## 14. Run Tests

Run all Django tests:

```powershell
python manage.py test
```

Feature tests currently cover:

- Signal creation cleaning rules.
- Signal invalid title validation.
- Signal not-found behavior.
- Signal status update validation.
- Deal probability rules.
- Deal invalid stage validation.
- Deal stage-to-probability transitions.

## 15. Add A New Feature

Use the existing Repository-Service-Route pattern.

Steps:

1. Create a folder under `features/`.
2. Add `models.py` for database models.
3. Add `schema.py` for request and response Pydantic schemas.
4. Add `repository.py` for database access.
5. Add `service.py` for business rules and validation.
6. Add `routes.py` for Django Ninja endpoints.
7. Add `apps.py` for Django app configuration.
8. Register the app in `INSTALLED_APPS` inside `config/settings.py`.
9. Import and mount the router in `config/urls.py`.
10. Add focused tests for service rules and important endpoint behavior.
11. Run migrations and tests.

## 16. Notes And Current Gaps

- `features.callAgents` is imported in `config/urls.py`, but it is not listed in `INSTALLED_APPS`. This is acceptable because it has no Django models, but add it if app configuration or signals are introduced later.
- The current `README.md` contains stale folder names like `core`, `shared`, and `modules`; the actual folders are `config`, `common`, and `features`.
- The current `README.md` also contains corrupted trailing text. This new file reflects the current code structure.
- Authentication is not active. Existing routes are open endpoints.
- CORS currently allows all origins. Restrict this for production.
- `DEBUG=True` exposes internal error details. Use `DEBUG=False` in production.
