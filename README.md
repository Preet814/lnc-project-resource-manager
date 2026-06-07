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

On startup the `api` service runs Alembic migrations and seeds the bootstrap Admin plus initial system configuration from `.env` (`BOOTSTRAP_ADMIN_*`, `BOOTSTRAP_LLM_*`, `JWT_SECRET_KEY` — see `.env.example`). Env values apply **only on first run** when no config row exists; later changes use the admin API (console in Phase 5).

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

### Admin employee and skills (BRD §3.1)

Requires an **EMPLOYEE** or **MANAGER** user account first (`POST /admin/users`), then link the work profile with `user_id`. Admin accounts cannot have employee profiles.

```bash
export TOKEN="YOUR_ACCESS_TOKEN"

# List employees (optional filters: work_status, department, active_only)
curl -s http://localhost:8000/admin/employees \
  -H "Authorization: Bearer $TOKEN"

# Create employee profile (user_id from POST /admin/users)
curl -s -X POST http://localhost:8000/admin/employees \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id":2,"full_name":"Ravi Kumar","email":"ravi@example.test","department":"Backend","designation":"Senior Developer"}'

# Get / update / deactivate by employee id (not user id)
curl -s http://localhost:8000/admin/employees/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/admin/employees/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"department":"DevOps","designation":"Lead Developer"}'
curl -s -X POST http://localhost:8000/admin/employees/1/deactivate \
  -H "Authorization: Bearer $TOKEN"

# Manage skills on employee id
curl -s http://localhost:8000/admin/employees/1/skills -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/admin/employees/1/skills \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"skill_name":"Docker","category":"DEVOPS","proficiency":"BEGINNER"}'
curl -s -X PATCH http://localhost:8000/admin/employees/1/skills/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"proficiency":"ADVANCED"}'
curl -s -X DELETE http://localhost:8000/admin/employees/1/skills/1 \
  -H "Authorization: Bearer $TOKEN"
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /admin/employees` | Admin JWT | List employees + bench/allocated counts |
| `POST /admin/employees` | Admin JWT | Create employee profile (link `user_id`) |
| `GET /admin/employees/{id}` | Admin JWT | Get employee profile |
| `PATCH /admin/employees/{id}` | Admin JWT | Update department, designation, etc. |
| `POST /admin/employees/{id}/deactivate` | Admin JWT | Deactivate profile; end allocations; block login |
| `GET /admin/employees/{id}/skills` | Admin JWT | List employee skills |
| `POST /admin/employees/{id}/skills` | Admin JWT | Add skill with category + proficiency |
| `PATCH /admin/employees/{id}/skills/{skill_id}` | Admin JWT | Update proficiency |
| `DELETE /admin/employees/{id}/skills/{skill_id}` | Admin JWT | Remove skill assignment |

### Admin projects and milestones (BRD §3.2)

Requires a **MANAGER** user account first (`POST /admin/users` with `"role":"MANAGER"`), then assign `manager_user_id` when creating the project.

Interactive API docs (Swagger UI): [http://localhost:8000/docs](http://localhost:8000/docs) — use **Authorize** with `Bearer YOUR_ACCESS_TOKEN` after login.

```bash
export TOKEN="YOUR_ACCESS_TOKEN"

# Create manager account (if not already present)
curl -s -X POST http://localhost:8000/admin/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"full_name":"Ankit Shah","email":"ankit@example.test","username":"ankit.shah","temporary_password":"TempPass1","role":"MANAGER"}'

# List projects (optional filter: ?status=ACTIVE)
curl -s http://localhost:8000/admin/projects \
  -H "Authorization: Bearer $TOKEN"

# Create project (manager_user_id from POST /admin/users)
curl -s -X POST http://localhost:8000/admin/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Alpha Portal","description":"Customer portal rewrite","start_date":"2026-03-01","end_date":"2026-06-30","status":"ACTIVE","manager_user_id":2}'

# Get / update by project id
curl -s http://localhost:8000/admin/projects/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/admin/projects/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Alpha Portal v2","status":"ON_HOLD"}'

# Manage milestones on project id
curl -s http://localhost:8000/admin/projects/1/milestones -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/admin/projects/1/milestones \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Backend API","due_date":"2026-04-15"}'
curl -s -X PATCH http://localhost:8000/admin/projects/1/milestones/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status":"IN_PROGRESS"}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /admin/projects` | Admin JWT | List projects + status counts |
| `POST /admin/projects` | Admin JWT | Create project |
| `GET /admin/projects/{id}` | Admin JWT | Get project detail |
| `PATCH /admin/projects/{id}` | Admin JWT | Update project details |
| `GET /admin/projects/{id}/milestones` | Admin JWT | List milestones |
| `POST /admin/projects/{id}/milestones` | Admin JWT | Add milestone |
| `PATCH /admin/projects/{id}/milestones/{milestone_id}` | Admin JWT | Update milestone |

### Admin allocations and system config (BRD §3.3, §3.5)

Allocations are **read-only** for Admin (create/end allocation is Manager API — PR #8). Initial system config is seeded once from `.env` (`BOOTSTRAP_LLM_PROVIDER`, optional `BOOTSTRAP_LLM_API_KEY`, `BOOTSTRAP_SCHEDULER_INTERVAL_HOURS`, `BOOTSTRAP_MAX_WEEKLY_HOURS`); ongoing updates use the endpoints below.

```bash
export TOKEN="YOUR_ACCESS_TOKEN"

# View all active allocations (optional filters: employee_id, project_id)
curl -s http://localhost:8000/admin/allocations \
  -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/admin/allocations?employee_id=1" \
  -H "Authorization: Bearer $TOKEN"

# Get current system configuration (API key masked)
curl -s http://localhost:8000/admin/config \
  -H "Authorization: Bearer $TOKEN"

# Update settings (BRD Screen 3.5 options)
curl -s -X PATCH http://localhost:8000/admin/config/llm-api-key \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"api_key":"your-provider-api-key"}'
curl -s -X PATCH http://localhost:8000/admin/config/llm-provider \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"provider":"GROQ"}'
curl -s -X PATCH http://localhost:8000/admin/config/scheduler-interval \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"scheduler_interval_hours":6}'
curl -s -X PATCH http://localhost:8000/admin/config/max-weekly-hours \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"max_weekly_hours":35}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /admin/allocations` | Admin JWT | List active allocations + total count |
| `GET /admin/config` | Admin JWT | Current system settings (masked API key) |
| `PATCH /admin/config/llm-api-key` | Admin JWT | Set LLM API key (stored encrypted) |
| `PATCH /admin/config/llm-provider` | Admin JWT | Switch Gemini / Groq |
| `PATCH /admin/config/scheduler-interval` | Admin JWT | Update scheduler interval (hours) |
| `PATCH /admin/config/max-weekly-hours` | Admin JWT | Update max weekly hours cap |

### Manager resource dashboard and allocation (BRD §4.1, §4.2)

Requires a **MANAGER** user and an employee profile (create via Admin API). Assign `manager_user_id` when creating the project so the manager owns it.

```bash
export TOKEN="YOUR_MANAGER_ACCESS_TOKEN"

# Resource dashboard (bench + active employees)
curl -s http://localhost:8000/manager/resources \
  -H "Authorization: Bearer $TOKEN"

# Employee drill-down
curl -s http://localhost:8000/manager/resources/1 \
  -H "Authorization: Bearer $TOKEN"

# Active allocations on a project (for end-allocation flow)
curl -s http://localhost:8000/manager/projects/1/allocations \
  -H "Authorization: Bearer $TOKEN"

# Direct allocate (returns 409 if total utilisation would exceed 100%)
curl -s -X POST http://localhost:8000/manager/allocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"project_id":1,"employee_id":2,"utilisation_percent":50,"from_date":"2026-06-01","to_date":"2026-09-30"}'

# End an allocation (optional as_of date; defaults to today)
curl -s -X POST http://localhost:8000/manager/allocations/1/end \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"as_of":"2026-06-14"}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /manager/resources` | Manager JWT | Resource dashboard + counts |
| `GET /manager/resources/{employee_id}` | Manager JWT | Employee drill-down |
| `GET /manager/projects/{project_id}/allocations` | Manager JWT | Active allocations on owned project |
| `POST /manager/allocations` | Manager JWT | Direct allocate |
| `POST /manager/allocations/{allocation_id}/end` | Manager JWT | End allocation |

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

Apply migrations and seed bootstrap Admin + default system config (requires PostgreSQL and `BOOTSTRAP_ADMIN_*` in `.env`):

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

Integration smoke reads `BOOTSTRAP_ADMIN_USERNAME` / `BOOTSTRAP_ADMIN_PASSWORD` from the environment. The auth forced password-change test skips if the admin already changed password; reset with `docker compose down -v` to re-test that flow. Admin user and employee smoke tests create uniquely named users each run.

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
| Admin employees API | Done — create, list, update, deactivate, skills CRUD (`/admin/employees/*`) |
| Admin projects API | Done — create, list, update, milestones CRUD (`/admin/projects/*`) |
| Admin allocations & config API | Done — view allocations, system settings (`/admin/allocations`, `/admin/config/*`) |
| Manager allocation API | Done — resource dashboard, direct allocate/end (`/manager/resources`, `/manager/allocations/*`) |
| Domain features | In progress (manager projects & timesheets next — PR #9) |

## Engineering compliance (BRD §4.3)

Documented in [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) with Python-oriented examples. Domain model matches [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
