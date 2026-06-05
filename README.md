# Project & Resource Management (PRM) Tool

**Learn & Code — Final Project**

Console client + REST server for resource planning, allocations, timesheets, and LLM-assisted matching — per the business requirements document.

**Implementation language:** Python 3.11+ (console client, REST API, background scheduler).

## Repository layout

```
.
├── README.md
├── requirements/
│   └── PRM_BRD.md                 # Business requirements (source of truth)
├── docs/
│   ├── README.md
│   ├── diagrams/
│   │   ├── class/                 # Master class diagram (html + md + mmd)
│   │   ├── sequence/
│   │   └── use-case/
│   └── architecture/
│       └── DESIGN.md              # SOLID, patterns, Python package layout (BRD §4.3)
├── src/                           # (planned) Python application code
├── tests/                         # (planned) pytest
├── pyproject.toml                 # (planned) dependencies & tooling
└── .gitignore
```

## Quick start

1. Read [requirements/PRM_BRD.md](requirements/PRM_BRD.md).
2. Open diagram HTML in a browser:
   - [docs/diagrams/class/class-diagram.html](docs/diagrams/class/class-diagram.html)
   - [docs/diagrams/sequence/sequence-diagram.html](docs/diagrams/sequence/sequence-diagram.html)
   - [docs/diagrams/use-case/use-case-diagram.html](docs/diagrams/use-case/use-case-diagram.html)
3. Class diagram notes (single file): [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
4. Engineering guide: [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md).
5. Doc index: [docs/README.md](docs/README.md).

## Planned Python stack (suggested)

| Layer | Technology |
|-------|------------|
| REST API | FastAPI (or Flask) |
| Persistence | SQLAlchemy + SQLite or PostgreSQL |
| Console client | `requests` calling REST (or `httpx`) |
| Scheduler | `APScheduler` or background thread in API process |
| LLM | Google Gemini / Groq SDKs behind a shared interface |
| Tests | pytest |

Adjust in `DESIGN.md` if your lead prefers different libraries.

## Status

| Area | Status |
|------|--------|
| Requirements | [PRM_BRD.md](requirements/PRM_BRD.md) |
| Diagrams | `docs/diagrams/` (class, sequence, use case) |
| Design compliance | [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) |
| Python code | Not started |

## Engineering compliance (BRD §4.3)

Documented in [docs/architecture/DESIGN.md](docs/architecture/DESIGN.md) with Python-oriented examples. Domain model matches [docs/diagrams/class/class-diagram.md](docs/diagrams/class/class-diagram.md).
