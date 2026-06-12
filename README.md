# Project & Resource Management (PRM) Tool

**Learn & Code — Final Project**

Console client + REST server for resource planning, allocations, timesheets, and LLM-assisted matching — per [PRM_BRD.md](requirements/PRM_BRD.md).

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
│   └── scheduler/                 # APScheduler wiring (lifespan + runner)
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

On startup the `api` service runs Alembic migrations and seeds the bootstrap Admin plus initial system configuration from `.env` (`BOOTSTRAP_ADMIN_*`, `BOOTSTRAP_LLM_*`, `JWT_SECRET_KEY` — see `.env.example`). Env values apply **only on first run** when no config row exists; later changes use the admin API.

For a clean first run with the unified ERD schema:

```bash
docker compose down -v
docker compose up --build
```

If the API logs `could not translate host name "postgres"`, wait a few seconds and run `docker compose up` again — the API startup script retries DB connectivity. Ensure `.env` uses `DATABASE_URL=...@postgres:5432/...` for Docker (not `localhost`).

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
  -d '{"full_name":"Ravi Kumar","email":"ravi@example.test","username":"ravi.kumar","temporary_password":"TempPass1","role":"ENGINEER"}'

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

### Admin employee and skills (BRD §3.1, V4)

**Onboarding (V4):** Create the login with `POST /admin/users`, then create the work profile with `POST /admin/employees` (the console “Add Employee” menu is removed in V4; the API remains the profile-creation step). Assign the employee to a manager with `POST /admin/employees/assign-manager` so managers only see their team on the resource dashboard.

Requires an **ENGINEER** or **MANAGER** user account first (`POST /admin/users`), then link the work profile with `user_id`. Admin accounts cannot have engineer profiles.

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

# Assign manager (BRD §3.1.4 — user ids, not employee ids)
curl -s -X POST http://localhost:8000/admin/employees/assign-manager \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"engineer_user_id":2,"manager_user_id":3}'

# Get / update / deactivate by user id
curl -s http://localhost:8000/admin/employees/2 -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/admin/employees/2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"department":"DevOps","designation":"Lead Developer"}'
curl -s -X POST http://localhost:8000/admin/employees/2/deactivate \
  -H "Authorization: Bearer $TOKEN"

# Manage skills on user id (user_skill_id in PATCH/DELETE paths)
curl -s http://localhost:8000/admin/employees/2/skills -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/admin/employees/2/skills \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"skill_name":"Docker","category":"DEVOPS","proficiency":"BEGINNER"}'
curl -s -X PATCH http://localhost:8000/admin/employees/2/skills/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"proficiency":"ADVANCED"}'
curl -s -X DELETE http://localhost:8000/admin/employees/2/skills/1 \
  -H "Authorization: Bearer $TOKEN"
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /admin/employees` | Admin JWT | List employees + bench/allocated counts |
| `POST /admin/employees` | Admin JWT | Create employee work profile (link `user_id`; V4 profile step) |
| `POST /admin/employees/assign-manager` | Admin JWT | Assign engineer to manager (`engineer_user_id`, `manager_user_id`) |
| `GET /admin/employees/{user_id}` | Admin JWT | Get engineer profile |
| `PATCH /admin/employees/{user_id}` | Admin JWT | Update department, designation, etc. |
| `POST /admin/employees/{user_id}/deactivate` | Admin JWT | Deactivate profile; end allocations; block login |
| `GET /admin/employees/{user_id}/skills` | Admin JWT | List user skills |
| `POST /admin/employees/{user_id}/skills` | Admin JWT | Add skill with category + proficiency |
| `PATCH /admin/employees/{user_id}/skills/{user_skill_id}` | Admin JWT | Update proficiency |
| `DELETE /admin/employees/{user_id}/skills/{user_skill_id}` | Admin JWT | Remove skill assignment |

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

# Create project (manager_user_id from POST /admin/users; V4 adds total_story_points)
curl -s -X POST http://localhost:8000/admin/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Alpha Portal","description":"Customer portal rewrite","start_date":"2026-03-01","end_date":"2026-06-30","status":"ACTIVE","manager_user_id":2,"total_story_points":120}'

# Get / update by project id (V4: status may be COMPLETED; total_story_points editable)
curl -s http://localhost:8000/admin/projects/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PATCH http://localhost:8000/admin/projects/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Alpha Portal v2","status":"COMPLETED","total_story_points":120}'

# V4: COMPLETED and ON_HOLD projects reject new allocations (managers may still end existing ones)

# Manage milestones on project id (V4: story_points on add; list returns SP totals)
curl -s http://localhost:8000/admin/projects/1/milestones -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/admin/projects/1/milestones \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"Backend API","due_date":"2026-04-15","story_points":40}'
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

Requires a **MANAGER** user and employee profiles assigned to that manager via `POST /admin/employees/assign-manager`. The resource dashboard, direct allocation, and AI skill match only include employees on the manager's direct team. Assign `manager_user_id` when creating the project so the manager owns it.

```bash
export TOKEN="YOUR_MANAGER_ACCESS_TOKEN"

# Resource dashboard (bench + active employees on your team only)
curl -s http://localhost:8000/manager/resources \
  -H "Authorization: Bearer $TOKEN"

# Employee drill-down
curl -s http://localhost:8000/manager/resources/1 \
  -H "Authorization: Bearer $TOKEN"

# Active allocations on a project (for end-allocation flow)
curl -s http://localhost:8000/manager/projects/1/allocations \
  -H "Authorization: Bearer $TOKEN"

# Direct allocate (returns 409 if total utilisation would exceed 100%; 400 if project is ON_HOLD or COMPLETED)
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
| `GET /manager/resources` | Manager JWT | Resource dashboard + team counts (bench/active) |
| `GET /manager/resources/{employee_id}` | Manager JWT | Employee drill-down |
| `GET /manager/projects/{project_id}/allocations` | Manager JWT | Active allocations on owned project |
| `POST /manager/allocations` | Manager JWT | Direct allocate (ACTIVE/PLANNED projects only) |
| `POST /manager/allocations/{allocation_id}/end` | Manager JWT | End allocation |

### Manager My Projects and team timesheets (BRD §4.3, §4.4)

Requires a **MANAGER** user who owns the project (`manager_user_id` on create). Team timesheet rows come from active allocations on owned projects; weeks with no submission show **MISSED** (persisted by the background scheduler or inferred at read time before the first scheduler tick).

```bash
export TOKEN="YOUR_MANAGER_ACCESS_TOKEN"

# My Projects list (name, end date, health)
curl -s http://localhost:8000/manager/projects \
  -H "Authorization: Bearer $TOKEN"

# Project health detail (milestones, risk flags, allocated resources)
curl -s http://localhost:8000/manager/projects/1 \
  -H "Authorization: Bearer $TOKEN"

# Team timesheets for a week (optional week_start_date; defaults to current ISO week Monday)
curl -s "http://localhost:8000/manager/timesheets?week_start_date=2026-05-12" \
  -H "Authorization: Bearer $TOKEN"

# Employee timesheet drill-down for that week
curl -s "http://localhost:8000/manager/timesheets/2?week_start_date=2026-05-12" \
  -H "Authorization: Bearer $TOKEN"
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /manager/projects` | Manager JWT | List owned projects with health |
| `GET /manager/projects/{project_id}` | Manager JWT | Project health detail |
| `GET /manager/timesheets` | Manager JWT | Team timesheets for week (incl. MISSED) |
| `GET /manager/timesheets/{employee_id}` | Manager JWT | Employee timesheet detail for week |

### Employee timesheets and allocations (BRD Screen 5)

Requires an **EMPLOYEE** user with a linked employee profile and at least one **ACTIVE** allocation for the selected week. `week_start_date` must be a **Monday**; the for-week endpoint defaults to the current ISO week Monday when omitted.

```bash
export TOKEN="YOUR_EMPLOYEE_ACCESS_TOKEN"

# Allocations for a week (expected max hours per project)
curl -s "http://localhost:8000/engineer/allocations/for-week?week_start_date=2026-06-01" \
  -H "Authorization: Bearer $TOKEN"

# My active allocations + total utilisation
curl -s http://localhost:8000/engineer/allocations \
  -H "Authorization: Bearer $TOKEN"

# Submit weekly timesheet
curl -s -X POST http://localhost:8000/engineer/timesheets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"week_start_date":"2026-06-01","entries":[{"project_id":1,"hours_worked":18,"activity_tags":["MICROSERVICES","WEBSOCKET"]}]}'

# Timesheet history and week detail
curl -s http://localhost:8000/engineer/timesheets \
  -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/engineer/timesheets/2026-06-01 \
  -H "Authorization: Bearer $TOKEN"
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /engineer/allocations/for-week` | Engineer JWT | Week allocations + expected max hrs |
| `GET /engineer/allocations` | Engineer JWT | My active allocations |
| `POST /engineer/timesheets` | Engineer JWT | Submit a week |
| `GET /engineer/timesheets` | Engineer JWT | My timesheet history |
| `GET /engineer/timesheets/{week_start_date}` | Engineer JWT | Week detail |

### Background scheduler (BRD §4.1)

The `api` service starts **APScheduler** on boot (when `SCHEDULER_ENABLED=true`). Each tick runs three jobs in order:

1. Recompute employee utilisation and `BENCH` / `ALLOCATED` status
2. Evaluate **ACTIVE** project health (`ON_TRACK` / `ATTENTION` / `AT_RISK`) and store risk flags
3. Flag **MISSED** timesheet weeks for closed weeks with allocations (lookback: 52 weeks)

**Interval:** bootstrap default from `.env` (`BOOTSTRAP_SCHEDULER_INTERVAL_HOURS`, default 4). Runtime value lives in `system_configuration.scheduler_interval_hours`. Admin updates via `PATCH /admin/config/scheduler-interval` or the console — APScheduler is **rescheduled immediately** (no API restart).

```bash
# Optional .env flags (see .env.example)
# SCHEDULER_ENABLED=true
# SCHEDULER_RUN_ON_STARTUP=true

# Watch scheduler logs (look for "rescheduled" after Admin changes interval)
docker compose logs -f api
```

Look for log lines such as `Background scheduler started` and `Scheduler tick complete`. Project health is recomputed for **ACTIVE** projects only (PLANNED, ON_HOLD, and COMPLETED are skipped each tick).

| Setting | Where | Notes |
|---------|--------|--------|
| `scheduler_interval_hours` | DB via Admin API | Rescheduled immediately on PATCH |
| `max_weekly_hours` | DB via Admin API | Applies on next request / scheduler tick |
| `SCHEDULER_ENABLED` | `.env` | Disable background jobs without code changes |
| `SCHEDULER_RUN_ON_STARTUP` | `.env` | Run one tick immediately when API starts |

Integration smoke (API + DB):

```bash
set -a && source .env && set +a
pytest tests/integration/test_scheduler_smoke.py -v -m integration
```

### Manager AI skill match and risk summary (BRD §4.2 AI, §4.3 [A], §4.5)

Requires a **MANAGER** JWT, project ownership, and an LLM API key configured by Admin (`PATCH /admin/config/llm-api-key`). Only employees assigned to the manager via `assign-manager` are considered for skill match. The project must be **ACTIVE** or **PLANNED** (same rule as direct allocation). Provider and deploy-time model/URL come from system config and `.env` (`GEMINI_*`, `GROQ_*`). Results are AI-generated suggestions — managers still confirm allocation via `POST /manager/allocations`.

```bash
export TOKEN="YOUR_MANAGER_ACCESS_TOKEN"

# Skill match for an owned project
curl -s -X POST http://localhost:8000/manager/projects/1/skill-match \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"requirement":"Java developer with microservices experience"}'

# AI risk summary for an owned project
curl -s http://localhost:8000/manager/projects/1/risk-summary \
  -H "Authorization: Bearer $TOKEN"
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /manager/projects/{project_id}/skill-match` | Manager JWT | AI-ranked employee suggestions |
| `GET /manager/projects/{project_id}/risk-summary` | Manager JWT | Plain-English project risk paragraph |

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

BRD alignment end-to-end flows (onboarding, story points, team scoping, COMPLETED allocation rules):

```bash
pytest tests/integration/test_brd_v4_smoke.py -v -m integration
```

Override API URL if needed:

```bash
PRM_API_URL=http://localhost:8000 pytest tests/integration -v -m integration
```

## Documentation

1. Read [requirements/PRM_BRD.md](requirements/PRM_BRD.md).
2. [docs/Implementation_roadmap.md](docs/Implementation_roadmap.md) — phases, status, and console checklist (incl. BRD changes for Phase 5).
3. [docs/BRD_V4_ALIGNMENT.md](docs/BRD_V4_ALIGNMENT.md) — backend alignment summary and gap analysis.
4. Open diagram HTML in a browser:
   - [docs/diagrams/class/class-diagram.html](docs/diagrams/class/class-diagram.html)
   - [docs/diagrams/sequence/sequence-diagram.html](docs/diagrams/sequence/sequence-diagram.html)
   - [docs/diagrams/use-case/use-case-diagram.html](docs/diagrams/use-case/use-case-diagram.html)
6. Class diagram notes: [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
7. Engineering guide: [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md).
8. Doc index: [docs/README.md](docs/README.md).

## Stack

| Layer | Technology |
|-------|------------|
| REST API | FastAPI + Uvicorn |
| Persistence | SQLAlchemy + PostgreSQL + Alembic |
| Console client | httpx calling REST |
| Scheduler | APScheduler (in api container; interval from Admin config) |
| LLM | Gemini / Groq behind `LLMClient` protocol + factory; Admin configures provider/key |
| Tests | pytest |

## Status

| Area | Status |
|------|--------|
| Requirements | [PRM_BRD.md](requirements/PRM_BRD.md) |
| BRD API alignment (backend) | Done — `manager_id`, assign-manager, story points, team scoping, `COMPLETED` allocation rules |
| Diagrams | `docs/diagrams/` |
| Design compliance | [DESIGN.md](docs/architecture/DESIGN.md) |
| Project scaffold | Done — Docker, health check, DB/Alembic init |
| ORM models & seed | Done — class diagram tables, migration, bootstrap Admin |
| Auth API | Done — login, change-password, JWT (`POST /auth/login`, `POST /auth/change-password`) |
| Admin users API | Done — create, list, deactivate, reactivate, reset password (`/admin/users/*`) |
| Admin employees API | Done — create, list, update, deactivate, assign manager, skills CRUD (`/admin/employees/*`) |
| Admin projects API | Done — create, list, update, milestones CRUD (`/admin/projects/*`) |
| Admin allocations & config API | Done — view allocations, system settings (`/admin/allocations`, `/admin/config/*`) |
| Manager allocation API | Done — resource dashboard, direct allocate/end (`/manager/resources`, `/manager/allocations/*`) |
| Manager projects & timesheets API | Done — My Projects, health detail, team timesheets read-only (`/manager/projects`, `/manager/timesheets/*`) |
| Manager LLM API | Done — skill match + risk summary (`/manager/projects/{id}/skill-match`, `/manager/projects/{id}/risk-summary`) |
| Engineer timesheets API | Done — submit week, view history, my allocations (`/engineer/timesheets/*`, `/engineer/allocations/*`) |
| Background scheduler | Done — utilisation, project health, MISSED timesheets (`src/prm/scheduler/`, `SchedulerService`) |
| Domain features | Phase 4 complete — console client next (PR #13+) |

## Engineering compliance (BRD §4.3)

Documented in [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) with Python-oriented examples. Domain model matches [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
