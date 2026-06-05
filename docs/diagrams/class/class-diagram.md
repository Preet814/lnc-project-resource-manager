# PRM Tool — Master Class Diagram

**Purpose:** One **BRD-aligned** domain class diagram. **Only** what [PRM_BRD.md](../../../requirements/PRM_BRD.md) §3–§4 requires (Admin-only account creation).

**Live view:** Open [class-diagram.html](./class-diagram.html) in a browser (Mermaid renders in-page).

**Export:** [class-diagram.mmd](./class-diagram.mmd) → [mermaid.live](https://mermaid.live) (Menu → Open).

**Implementation (Python):** Services, repositories, REST API, and console layout — [DESIGN.md](../../architecture/DESIGN.md).

---

## Merge summary (your diagram vs BRD)

| Topic | Earlier draft | BRD / merged result |
|-------|------------------------------|---------------------|
| Skills | `Skill` owned by `Employee` (composition) | **`Skill` + `EmployeeSkill` join** (Screen 3.1.4) |
| Timesheet | `Timesheet` | **`TimesheetWeek`** (week is the aggregate, Screen 5) |
| Project manager | `managerId` | **`managerUserId`** → `User` (Admin may not have Employee profile) |
| Project health | `Project.computeHealth()` on entity | **Scheduler / rule engine** updates `healthStatus`; no method on entity |
| Project status | Included `COMPLETED` | **Removed** — BRD only PLANNED, ACTIVE, ON_HOLD |
| User status | `isActive` only | **`UserAccountStatus`** ACTIVE / INACTIVE (Screen 3.4.2) |
| User login | `login()` on `User` | **Removed from entity** — application `AuthService` (implementation) |
| `AuthToken` | On diagram | **Kept as «DTO»** — login outcome (BRD Screen 1); not a domain table |
| AI | `AIService` class | **`ILLMClient` «interface»** + `SkillMatchResult` «DTO» (BRD §4.1 AI scope) |
| Risk output | `RiskSummary` entity | **`summarizeRisk()` returns `String`** — no separate persisted entity in BRD |
| Scheduler | `SchedulerJob` | **Kept as «service»** — BRD §4.1 background job |
| Enums on diagram | Yes | **Kept** — all BRD enumerations linked to attributes |
| `ProjectHealthSnapshot` | Missing | **Added** — health flags / snapshot (BRD project detail) |
| `fullName` on `User` | Missing | **Added** — Create User Account (Screen 3.4.1) |

---

## Master class diagram

Same content as [class-diagram.html](./class-diagram.html). Copy from `class-diagram.mmd` or the block below (first line = `classDiagram`).

```mermaid
classDiagram
  direction TB

  class Role {
    <<enumeration>>
    ADMIN
    MANAGER
    EMPLOYEE
  }
  class UserAccountStatus {
    <<enumeration>>
    ACTIVE
    INACTIVE
  }
  class EmployeeWorkStatus {
    <<enumeration>>
    BENCH
    ALLOCATED
  }
  class SkillCategory {
    <<enumeration>>
    BACKEND
    FRONTEND
    DEVOPS
    QA
    OTHER
  }
  class ProficiencyLevel {
    <<enumeration>>
    BEGINNER
    INTERMEDIATE
    ADVANCED
  }
  class ProjectStatus {
    <<enumeration>>
    PLANNED
    ACTIVE
    ON_HOLD
  }
  class ProjectHealthStatus {
    <<enumeration>>
    ON_TRACK
    ATTENTION
    AT_RISK
  }
  class MilestoneStatus {
    <<enumeration>>
    NOT_STARTED
    IN_PROGRESS
    DONE
  }
  class AllocationStatus {
    <<enumeration>>
    ACTIVE
    ENDED
  }
  class TimesheetWeekStatus {
    <<enumeration>>
    SUBMITTED
    MISSED
  }
  class LLMProvider {
    <<enumeration>>
    GEMINI
    GROQ
  }
  class ActivityTag {
    <<enumeration>>
    BACKEND_API
    MICROSERVICES
    DATABASE_DESIGN
    WEBSOCKET
    FRONTEND
    CODE_REVIEW
    BUG_FIXING
    DEVOPS
    TESTING_QA
    DOCUMENTATION
    OTHER
  }

  class User {
    <<entity>>
    -Long id
    -String fullName
    -String username
    -String email
    -String passwordHash
    -Role role
    -UserAccountStatus accountStatus
    -boolean forcePasswordChange
    -LocalDateTime createdAt
    -LocalDateTime updatedAt
    +changePassword(oldPwd, newPwd) boolean
    +requiresPasswordChange() boolean
    +deactivate() void
    +reactivate() void
  }

  class Employee {
    <<entity>>
    -Long id
    -Long userId
    -String fullName
    -String email
    -String department
    -String designation
    -EmployeeWorkStatus workStatus
    -boolean isActive
    -int currentUtilisationPercent
    -LocalDateTime createdAt
    +getAvailabilityPercent(maxWeeklyHours) int
    +isOnBench() boolean
    +isOverUtilised() boolean
    +deactivate(endDate) void
  }

  class Skill {
    <<entity>>
    -Long id
    -String name
    -SkillCategory category
    -boolean isPredefined
  }

  class EmployeeSkill {
    <<entity>>
    -Long id
    -Long employeeId
    -Long skillId
    -ProficiencyLevel proficiency
    -LocalDateTime assignedAt
  }

  class Project {
    <<entity>>
    -Long id
    -String name
    -String description
    -LocalDate startDate
    -LocalDate endDate
    -ProjectStatus status
    -Long managerUserId
    -ProjectHealthStatus healthStatus
    -LocalDateTime healthComputedAt
    +isOwnedBy(managerUserId) boolean
    +allowsAllocation() boolean
  }

  class Milestone {
    <<entity>>
    -Long id
    -Long projectId
    -String title
    -LocalDate dueDate
    -MilestoneStatus status
    -int sequenceOrder
    +isOverdue(asOfDate) boolean
  }

  class Allocation {
    <<entity>>
    -Long id
    -Long employeeId
    -Long projectId
    -int utilisationPercent
    -LocalDate fromDate
    -LocalDate toDate
    -AllocationStatus status
    -Long createdByUserId
    +isActiveOn(date) boolean
    +endAsOf(date) void
    +overlaps(other) boolean
  }

  class TimesheetWeek {
    <<entity>>
    -Long id
    -Long employeeId
    -LocalDate weekStartDate
    -TimesheetWeekStatus status
    -int totalHours
    -LocalDateTime submittedAt
    +canSubmit() boolean
    +markSubmitted() void
    +markMissed() void
  }

  class TimesheetEntry {
    <<entity>>
    -Long id
    -Long timesheetWeekId
    -Long projectId
    -int hoursWorked
    -List~ActivityTag~ activityTags
    +validateAgainst(allocation, maxWeeklyHours) ValidationResult
  }

  class SystemConfiguration {
    <<entity>>
    -Long id
    -LLMProvider llmProvider
    -String llmApiKeyEncrypted
    -int schedulerIntervalHours
    -int maxWeeklyHours
    +getMaxWeeklyHours() int
    +updateLlmKey(key) void
  }

  class ProjectHealthSnapshot {
    <<entity>>
    -Long id
    -Long projectId
    -ProjectHealthStatus status
    -List~String~ riskFlags
    -LocalDateTime computedAt
  }

  class AuthToken {
    <<DTO>>
    +String token
    +Long userId
    +LocalDateTime expiresAt
    +isValid() boolean
  }

  class SkillMatchResult {
    <<DTO>>
    +Long employeeId
    +String employeeName
    +String reason
    +int suggestedAllocationPercent
    +int freeHoursPerWeek
  }

  class ILLMClient {
    <<interface>>
    +rankCandidates(context, candidates) List~SkillMatchResult~
    +summarizeRisk(context) String
  }

  class SchedulerJob {
    <<service>>
    +run() void
    +recomputeEmployeeStatus() void
    +recomputeProjectHealth() void
    +markMissedTimesheets() void
  }

  User "1" --> "0..1" Employee : userId
  User "1" --> "*" Project : managerUserId
  Employee "1" --> "*" EmployeeSkill
  Skill "1" --> "*" EmployeeSkill
  Project "1" *-- "*" Milestone
  Project "1" --> "*" Allocation
  Employee "1" --> "*" Allocation
  Employee "1" *-- "*" TimesheetWeek
  TimesheetWeek "1" *-- "*" TimesheetEntry
  TimesheetEntry "*" --> "1" Project
  Project "1" --> "0..1" ProjectHealthSnapshot

  User --> Role
  User --> UserAccountStatus
  Employee --> EmployeeWorkStatus
  Skill --> SkillCategory
  EmployeeSkill --> ProficiencyLevel
  Project --> ProjectStatus
  Project --> ProjectHealthStatus
  Milestone --> MilestoneStatus
  Allocation --> AllocationStatus
  TimesheetWeek --> TimesheetWeekStatus
  TimesheetEntry --> ActivityTag
  SystemConfiguration --> LLMProvider

  SystemConfiguration ..> SchedulerJob : interval hours
  SchedulerJob ..> Employee : workStatus utilisation
  SchedulerJob ..> Project : healthStatus
  SchedulerJob ..> TimesheetWeek : MISSED flag
  SystemConfiguration ..> ILLMClient : provider and key
  ILLMClient ..> SkillMatchResult : rankCandidates
  User ..> AuthToken : login issues token
```

> **BRD note:** `workStatus`, `healthStatus`, and MISSED timesheets are **written by `SchedulerJob`** (§4.1), not by entity methods on `Project` or `Employee`.

---

## BRD coverage

| BRD area | Classes on diagram |
|----------|-------------------|
| Auth & users (Screens 1–2, 3.4) | `User`, `AuthToken` «DTO», `Role`, `UserAccountStatus` |
| Employees & skills (3.1) | `Employee`, `Skill`, `EmployeeSkill`, enums |
| Projects & milestones (3.2, 4.3) | `Project`, `Milestone`, `ProjectHealthSnapshot` |
| Allocations (4.2) | `Allocation` |
| Timesheets (5.x) | `TimesheetWeek`, `TimesheetEntry`, `ActivityTag` |
| System config (3.5) | `SystemConfiguration`, `LLMProvider` |
| AI & scheduler (§4.1) | `ILLMClient`, `SkillMatchResult`, `SchedulerJob` |

**Explicitly not on this diagram (out of BRD domain / implementation detail):** `AuthService`, repositories, console menus, timesheet approval, web UI, `RiskSummary` table, `COMPLETED` project status.

---

## Key design rules

1. **User ≠ Employee** — optional `0..1` link; Admin may have User only.
2. **Skills** — reusable `Skill`; assignment via `EmployeeSkill` with proficiency.
3. **Manager** — `Project.managerUserId` references `User`, not `Employee`.
4. **Health** — scheduler updates `Project.healthStatus`; optional `ProjectHealthSnapshot` for flags/history.
5. **AI risk** — plain-English **string** from LLM, not a stored `RiskSummary` entity.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-03 | Domain-only master diagram |
| 2026-06-03 | Merged domain diagram: enums + scheduler + LLM; BRD corrections applied |
| 2026-06-03 | **BRD V3:** no model change; moved to `docs/diagrams/class/` |
