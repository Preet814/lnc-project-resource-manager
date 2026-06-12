# PRM — Documentation

| Area | Location |
|------|----------|
| **BRD** | [../requirements/PRM_BRD.md](../requirements/PRM_BRD.md) |
| **Diagrams** | [diagrams/](diagrams/) — open `.html` in a browser |
| **Design & Python structure** | [architecture/DESIGN.md](architecture/DESIGN.md) |

## Diagrams

| Type | Browser | Markdown / source |
|------|---------|-------------------|
| Class | [class/class-diagram.html](diagrams/class/class-diagram.html) | [class-diagram.md](diagrams/class/class-diagram.md) · [class-diagram.mmd](diagrams/class/class-diagram.mmd) |
| Sequence | [sequence/sequence-diagram.html](diagrams/sequence/sequence-diagram.html) | [sequence-diagram.md](diagrams/sequence/sequence-diagram.md) |
| Use case | [use-case/use-case-diagram.html](diagrams/use-case/use-case-diagram.html) | [use-case-diagram.md](diagrams/use-case/use-case-diagram.md) · [plantuml/](diagrams/use-case/plantuml/) |

There is **one** class diagram markdown file: `diagrams/class/class-diagram.md` (pairs with `class-diagram.html`).

## Architecture folder

Only **[architecture/DESIGN.md](architecture/DESIGN.md)** — SOLID, design patterns, clean code, and recommended **Python** package layout for implementation.

## Team Builder (AI — Complexity 1)

Managers describe a **whole team in one plain-English paragraph**. The system assigns the best available people on the manager's direct team in a **single pass** (no double-booking) and reports honest gaps when a role cannot be filled.

### How it works

1. **LLM #1 — parse** — requirement text → fixed `TeamPlan` JSON (`team_slots[]` with nullable filters; `null` = do not filter).
2. **Code — search & assign** — `TeamCandidateSearchService` queries the DB; `TeamAssignmentService` picks unique engineers and classifies gaps. The LLM never touches the database.
3. **LLM #2 — explain** — one-sentence reason per filled slot from DB facts. Gaps stay **code-generated** (`SKILL_GAP` or `AVAILABILITY_GAP`). If explain fails, a template reason is kept.

Hard rules always enforced in code: manager's active team only, unique `user_id` per slot, proficiency and capacity filters when set in the plan.

### API

Requires **MANAGER** JWT, project ownership, project **ACTIVE** or **PLANNED**, and an LLM API key configured by Admin (same as skill match).

```bash
curl -s -X POST http://localhost:8000/manager/projects/1/team-match \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"requirement":"Banking portal needs a Senior Java Developer, a DevOps Engineer with Docker, and a QA Tester with Selenium experience"}'
```

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /manager/projects/{project_id}/team-match` | Manager JWT | Parse requirement, assign team, return assignments + gaps |

Response includes `assignments` (role, person, suggested allocation %, reason) and `gaps` (typed gap + detail, with optional availability hints).

### Console

**Manager → AI Assistant → Team Builder** — select project, type the paragraph, review filled roles and gaps. Shortcut to **Allocate Resource** to create allocations after review.

### Demo scenario (banking portal)

Seed or ensure engineers on the manager's team have skills such as **Java** (ADVANCED), **Docker** (DEVOPS), and **Manual Testing** / **Selenium** (QA). Then try:

> Banking portal needs a Senior Java Developer, a DevOps Engineer with Docker, and a QA Tester with Selenium experience.

Expected outcome: Java and DevOps slots fill when qualified bench/available people exist; QA may show `SKILL_GAP` if no Selenium skill is on the team, or `AVAILABILITY_GAP` if skills match but capacity is blocked.

### Related code

| Layer | Module |
|-------|--------|
| Parse | `infrastructure/llm/team_plan_parsing.py`, `parse_team_plan` on `LLMClient` |
| Search | `application/team_candidate_search_service.py` |
| Assign | `application/team_assignment_service.py` |
| Orchestrate | `application/team_match_service.py` |
| Explain | `infrastructure/llm/team_assignment_explain_parsing.py` |
| API | `api/routes/manager.py` — `POST .../team-match` |
| Console | `console/screens/manager/team_builder.py` |
