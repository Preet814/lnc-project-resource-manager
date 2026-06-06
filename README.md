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

On startup the `api` service runs Alembic migrations and seeds the bootstrap Admin from `.env` (`BOOTSTRAP_ADMIN_*` variables — see `.env.example`; BRD defaults `admin` / `Admin@1234`, `force_password_change=true`).

Verify the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"PRM API","version":"0.1.0"}
```

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

Integration smoke test (API must be running — Docker or `python -m prm.api`):

```bash
docker compose up --build -d
pytest tests/integration -v -m integration
docker compose down
```

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
| Domain features | In progress (auth API next) |

## Engineering compliance (BRD §4.3)

Documented in [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) with Python-oriented examples. Domain model matches [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
