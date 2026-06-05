# PRM Tool — Design & Engineering Compliance

**Purpose:** Satisfy BRD §4.3 (SOLID, patterns, principles, clean code) with traceable **Python** examples.  
**Companion:** [class-diagram.md](../diagrams/class/class-diagram.md) (domain model) · [PRM_BRD.md](../../requirements/PRM_BRD.md)

**Stack:** Python 3.11+ · REST API (FastAPI recommended) · SQLAlchemy · console client via HTTP · pytest.

---

## 1. SOLID principles (all five)

### S — Single Responsibility Principle

| Class / module | Single responsibility | Must not |
|----------------|----------------------|----------|
| `AllocationService` | Create/end allocations; enforce ownership | Utilisation math, console I/O |
| `UtilisationCalculator` | Overlap and 100% cap | Persist rows, call LLM |
| `HealthRuleEngine` | ON_TRACK / ATTENTION / AT_RISK rules | Raw SQL in console |
| `EmployeeSkillService` | Employee skill CRUD | User account management |
| `AuthorizationService` | Role and project-owner checks | Timesheet hour validation |
| `GeminiClient` | HTTP + map Gemini response | Pre-filter candidates |
| `admin_menu` (module) | Admin console screens | Direct repository access |

```python
# allocation_service.py — delegates math; fails fast on invalid allocation
result = self._utilisation.validate_new_allocation(
    employee_id, percent, date_from, date_to
)
if not result.is_valid:
    raise ValidationError(result.message)
```

**Anti-pattern avoided:** No `Project.compute_health()` on the entity; health is updated by `HealthRuleEngine` / scheduler only.

### O — Open/Closed Principle

| Extension point | Extend without changing callers |
|-----------------|--------------------------------|
| `LLMClient` (Protocol) | Add `GroqClient`, another provider class |
| `llm_client_factory` | New branch for provider enum |
| Repository protocols | Swap SQLite vs PostgreSQL implementation |

```python
class SkillMatchService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client  # Strategy — injected

    def find_matches(self, project_id: int, requirement: str) -> list[SkillMatchResult]:
        candidates = self._capacity_filter.filter_available(self._load_candidates(project_id))
        return self._llm.rank_candidates(self._build_context(project_id, requirement), candidates)
```

### L — Liskov Substitution Principle

Any `LLMClient` implementation must return ranked lists / summary strings and raise `DomainError` on failure — never silently return `None` for lists.

### I — Interface Segregation Principle

Use small `typing.Protocol` types: `PasswordHasher`, `TokenService`, `AllocationRepository` — not one giant “database” interface.

### D — Dependency Inversion Principle

Services depend on protocols; infrastructure implements them.

```python
class AllocationService:
    def __init__(
        self,
        allocation_repo: AllocationRepository,
        utilisation: UtilisationCalculator,
        authorization: AuthorizationService,
    ) -> None:
        self._allocation_repo = allocation_repo
        self._utilisation = utilisation
        self._authorization = authorization
```

---

## 2. Design patterns (≥1 required — five used)

| Pattern | Python expression | Purpose |
|---------|-------------------|---------|
| **Repository** | `Protocol` + `SqlAlchemyEmployeeRepository` | Hide persistence |
| **Strategy** | `LLMClient` implementations | Gemini / Groq per Screen 3.5 |
| **Adapter** | `GeminiClient`, `GroqClient` | Vendor API → internal protocol |
| **Factory** | `create_llm_client(provider, api_key)` | Centralise client construction |
| **Singleton** | `SystemConfigService` with cached config row | One settings record |

```python
# repository example
class AllocationRepository(Protocol):
    def find_overlapping(
        self, employee_id: int, date_from: date, date_to: date
    ) -> list[Allocation]: ...
    def save(self, allocation: Allocation) -> Allocation: ...

# factory + strategy
def create_llm_client(provider: LLMProvider, api_key: str) -> LLMClient:
    if provider is LLMProvider.GEMINI:
        return GeminiClient(api_key)
    if provider is LLMProvider.GROQ:
        return GroqClient(api_key)
    raise ValueError(f"Unknown provider: {provider}")
```

---

## 3. Design principles (≥2 required)

### Separation of Concerns

```
console/  →  api/ (FastAPI routes)  →  application/ (services)  →  domain/  →  infrastructure/
```

- Console handlers call REST only — no SQL.
- Domain entities/dataclasses have no HTTP or ORM imports.
- LLM clients never query the database.

### DRY

| Logic | Central module |
|-------|----------------|
| 100% utilisation cap | `utilisation_calculator.py` |
| Role / project owner | `authorization_service.py` |
| Health rules | `health_rule_engine.py` |
| Max weekly hours | `system_config_service.py` |

### Fail Fast

Raise domain exceptions at boundaries: `ValidationError`, `UnauthorizedError`, `NotFoundError`.

```python
self._authorization.assert_project_owner(manager_user_id, project_id)
```

### YAGNI

Not in BRD — do not build unless lead asks: timesheet approval, email, web UI, extra audit tables beyond BRD.

---

## 4. Clean code rules

| BRD rule | Python practice |
|----------|-----------------|
| Meaningful names | `EmployeeWorkStatus.BENCH`, `TimesheetWeek`, `assert_can_allocate` |
| Small functions | Services orchestrate; calculators/engines do one job |
| No magic numbers | `constants.py`: `DEFAULT_MAX_WEEKLY_HOURS = 40`, etc.; override from DB config |
| No dead code | No commented blocks; run `ruff` / formatter before submit |

```python
# src/prm/domain/constants.py
DEFAULT_MAX_WEEKLY_HOURS = 40
DEFAULT_SCHEDULER_INTERVAL_HOURS = 4
MIN_PASSWORD_LENGTH = 8
MAX_UTILISATION_PERCENT = 100
```

---

## 5. Python package structure (recommended)

When you start coding, use something like:

```
src/prm/
├── domain/              # Entities, enums, exceptions, constants
├── application/         # Services (allocation, timesheet, auth, skill match, …)
├── infrastructure/      # SQLAlchemy repos, LLM clients, password hashing
├── api/                 # FastAPI app, routes, DTOs/schemas
├── console/             # CLI menus calling api via httpx/requests
└── scheduler/           # APScheduler jobs (utilisation, health, MISSED)

tests/
├── unit/
└── integration/

pyproject.toml           # dependencies: fastapi, sqlalchemy, httpx, pytest, …
requirements.txt         # optional lock/simple install
```

Entry points (examples):

- `python -m prm.api` — start REST server  
- `python -m prm.console` — start console client  
- Scheduler: started with API process or separate `python -m prm.scheduler`

---

## 6. Grader checklist (BRD §4.3)

- [ ] **S** — Services vs calculators vs console separated
- [ ] **O** — New LLM provider without changing `SkillMatchService`
- [ ] **L** — `LLMClient` implementations interchangeable in tests
- [ ] **I** — Small protocols (`PasswordHasher`, repos)
- [ ] **D** — Constructor injection of protocols / abstractions
- [ ] **Pattern** — Repository + Strategy with code references
- [ ] **Principles** — SoC, DRY, Fail Fast documented
- [ ] **Clean code** — Constants module; names match BRD domain language

---

## 7. Changelog

| Date | Change |
|------|--------|
| 2026-05-27 | Initial design compliance doc |
| 2026-06-03 | Python stack; removed duplicate CLASS_DIAGRAM.md (single class-diagram.md in diagrams/class/) |
