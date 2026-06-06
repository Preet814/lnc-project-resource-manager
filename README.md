# Project & Resource Management (PRM) Tool

**Learn & Code — Final Project**

Console client + REST server for resource planning, allocations, timesheets, and LLM-assisted matching — per the business requirements document.

**Implementation language:** Python 3.11+ (console client, REST API, background scheduler).

## Repository layout

```
.
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── alembic/                       # Database migrations
├── requirements/
│   └── PRM_BRD.md                 # Business requirements (source of truth)
├── docs/
│   ├── README.md
│   ├── diagrams/
│   └── architecture/
│       └── DESIGN.md              # SOLID, patterns, Python package layout (BRD §4.3)
├── src/prm/
│   ├── domain/                    # Entities, enums, exceptions, constants
│   ├── application/               # Services
│   ├── infrastructure/            # DB, LLM clients, hashing
│   ├── api/                       # FastAPI REST server
│   ├── console/                   # CLI client (stub)
│   └── scheduler/                 # Background jobs (later)
└── tests/
    ├── unit/
    └── integration/
```

## Run with Docker (recommended)

Prerequisites: Docker and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

On startup the `api` service runs Alembic migrations and seeds the bootstrap Admin from `.env` (`BOOTSTRAP_ADMIN_*`, `JWT_SECRET_KEY` — see `.env.example`; BRD defaults `admin` / `Admin@1234`, `force_password_change=true`).

Verify the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"PRM API","version":"0.1.0"}
```

### Auth (login + forced password change)

Set bootstrap credentials and JWT secret in `.env`, then:

```bash
# Login (bootstrap admin — password from BOOTSTRAP_ADMIN_PASSWORD in .env)
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_BOOTSTRAP_PASSWORD"}'
```

Response includes `access_token`, `force_password_change`, and `role`. When `force_password_change` is `true`, change password before using other features:

```bash
curl -s -X POST http://localhost:8000/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"new_password":"NewSecure1","confirm_password":"NewSecure1"}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /auth/login` | None | Username/password → JWT |
| `POST /auth/change-password` | Bearer JWT | Set new password; clears `force_password_change` |

### Admin user management (BRD §3.4)

All endpoints require a Bearer JWT for an **ADMIN** account.

```bash
# After login, set TOKEN from access_token in the login response
export TOKEN="YOUR_ACCESS_TOKEN"

# List all users
curl -s http://localhost:8000/admin/users \
  -H "Authorization: Bearer $TOKEN"

# Create user account (temporary password — user must change on first login)
curl -s -X POST http://localhost:8000/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"full_name":"Ravi Kumar","email":"ravi@example.test","username":"ravi.kumar","temporary_password":"TempPass1","role":"EMPLOYEE"}'

# Deactivate / reactivate by user id
curl -s -X POST http://localhost:8000/admin/users/2/deactivate -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/admin/users/2/reactivate -H "Authorization: Bearer $TOKEN"

# Reset password by username or numeric id
curl -s -X POST http://localhost:8000/admin/users/reset-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"identifier":"ravi.kumar","temporary_password":"ResetPass1"}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /admin/users` | Admin JWT | List users + active/inactive counts |
| `POST /admin/users` | Admin JWT | Create user account |
| `POST /admin/users/{id}/deactivate` | Admin JWT | Deactivate account |
| `POST /admin/users/{id}/reactivate` | Admin JWT | Reactivate account |
| `POST /admin/users/reset-password` | Admin JWT | Reset password (username or id) |

Stop services:

```bash
docker compose down
```

Services:

| Service | Purpose |
|---------|---------|
| `postgres` | PostgreSQL 16 database |
| `api` | FastAPI REST server on port `8000` |
| `console` | Console stub — waits for API health (menus in Phase 5) |

## Local development (WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Apply migrations and seed the bootstrap Admin (requires PostgreSQL and `BOOTSTRAP_ADMIN_*` in `.env`):

```bash
cp .env.example .env
docker compose up -d postgres
DATABASE_URL=postgresql://prm:prm@localhost:5432/prm alembic upgrade head
python -m prm.infrastructure.db.seed
```

Run the API locally:

```bash
cp .env.example .env
# edit DATABASE_URL if needed for local postgres
python -m prm.api
```

## Tests

Unit tests (no running server required):

```bash
pytest tests/unit -v
```

Integration smoke tests (API must be running — Docker or `python -m prm.api`):

```bash
docker compose up --build -d
set -a && source .env && set +a   # WSL/bash — bootstrap creds for auth smoke
pytest tests/integration -v -m integration
docker compose down
```

Integration smoke reads `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD` from the environment. The auth forced password-change test skips if the admin already changed password; reset with `docker compose down -v` to re-test that flow. Admin user smoke tests create uniquely named users each run.

Override API URL if needed:

```bash
PRM_API_URL=http://localhost:8000 pytest tests/integration -v -m integration
```

## Documentation

1. Read [requirements/PRM_BRD.md](requirements/PRM_BRD.md).
2. Open diagram HTML in a browser:
   - [docs/diagrams/class/class-diagram.html](docs/diagrams/class/class-diagram.html)
   - [docs/diagrams/sequence/sequence-diagram.html](docs/diagrams/sequence/sequence-diagram.html)
   - [docs/diagrams/use-case/use-case-diagram.html](docs/diagrams/use-case/use-case-diagram.html)
3. Class diagram notes: [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
4. Engineering guide: [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md).
5. Doc index: [docs/README.md](docs/README.md).

## Stack

| Layer | Technology |
|-------|------------|
| REST API | FastAPI + Uvicorn |
| Persistence | SQLAlchemy + PostgreSQL + Alembic |
| Console client | httpx calling REST |
| Scheduler | APScheduler (later) |
| LLM | Gemini / Groq behind shared interface (later) |
| Tests | pytest |

## Status

| Area | Status |
|------|--------|
| Requirements | [PRM_BRD.md](requirements/PRM_BRD.md) |
| Diagrams | `docs/diagrams/` |
| Design compliance | [DESIGN.md](docs/architecture/DESIGN.md) |
| Project scaffold | Done — Docker, health check, DB/Alembic init |
| ORM models & seed | Done — class diagram tables, migration, bootstrap Admin |
| Auth API | Done — login, change-password, JWT (`POST /auth/login`, `POST /auth/change-password`) |
| Admin users API | Done — create, list, deactivate, reactivate, reset password (`/admin/users/*`) |
| Domain features | In progress (admin employees/skills next) |

## Engineering compliance (BRD §4.3)

Documented in [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) with Python-oriented examples. Domain model matches [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
