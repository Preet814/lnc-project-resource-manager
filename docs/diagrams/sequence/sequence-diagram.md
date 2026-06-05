# PRM Tool — Master Sequence Diagram

**Purpose:** One **BRD-aligned** sequence diagram ([PRM_BRD.md](../../../requirements/PRM_BRD.md)). Early SVG drafts may live in `archive/`.

**Live view:** [sequence-diagram.html](./sequence-diagram.html) — **six panels**, each with its own actors (Console, REST API, etc.) at the top of that section.

**Export:** Copy one § block from [sequence-diagram.mmd](./sequence-diagram.mmd) or the HTML script into [mermaid.live](https://mermaid.live).

**Reading order:** §1 Login → §2 Admin → §3–§4 Manager (allocate, then risk) → §5 Employee → §6 Scheduler.

---

## Why Admin was not in the first version (and what we did now)

| Reason | Explanation |
|--------|-------------|
| **Same technical pattern** | Admin screens (3.1, 3.2, 3.4, 3.5) are all **Console → REST → service → DB**. Drawing every CRUD screen would repeat the same arrows and make one diagram unreadable. |
| **BRD emphasis** | §4.1 highlights **AI matching**, **allocation rules**, **timesheets**, and the **scheduler** — not Admin data entry. |
| **Admin is not a “special” runtime path** | Admin does not call the LLM or the scheduler as a user; they only **configure** the system (Screen 3.5). |
| **What reviewers need in one diagram** | Cross-role **auth** plus the **three distinctive flows** (Manager + Employee + background). |

**Now included:** a **short §6 Admin onboard** (Create User + Add Employee — BRD Screen 3.4.1 + 3.1.1), because your question is valid for completeness. Other Admin menus (projects, milestones, config) still follow the same pattern and are listed in the catalogue below.

---

## Merge: your 4 SVGs vs master diagram

| Your SVG | Covered in master? | Added / improved in merge |
|----------|-------------------|---------------------------|
| `seq_login_password.svg` | §1 | Generic **User** actor; invalid login **alt**; **PATCH/change password** branch; token + role menu |
| `seq_allocate_resource_ai.svg` | §2 | **GET** load candidates; capacity **filter** note; **409** over-allocation **alt**; **ALLOCATED** status update |
| `seq_timesheet_submit.svg` | §3 | **GET** allocations for week; per-project form; **loop** server validation; persist week + entries |
| `seq_scheduler_risk_summary.svg` | §4 + **§5** | Scheduler **MISSED** flag; health from milestones + hours; **§5 AI risk summary** (was missing before) |
| *(none)* Admin CRUD | **§6** (short) | Create user + add employee only |

---

## Master sequence diagram (6 BRD sections)

```mermaid
sequenceDiagram
    autonumber

    actor User as User (any role)
    actor Admin
    actor Manager
    actor Employee
    participant Console as Console App
    participant API as REST API
    participant Auth as Auth Service
    participant Authz as Authorization Service
    participant Alloc as Allocation Service
    participant Skill as Skill Match Service
    participant Risk as Risk Summary Service
    participant Calc as Utilisation Calculator
    participant TS as Timesheet Service
    participant Sched as Scheduler Job
    participant LLM as LLM Provider
    participant DB as Database

    rect rgb(232, 244, 252)
        Note over User, DB: 1. Login and forced password change (BRD Screen 1)
        User->>Console: enter username and password
        Console->>API: POST /auth/login
        API->>Auth: login(username, password)
        Auth->>DB: validate credentials and load user
        alt invalid credentials
            Auth-->>Console: 401 unauthorized
            Console-->>User: show error return to login
        else valid
            Auth->>DB: read forcePasswordChange flag
            alt forcePasswordChange is true
                API-->>Console: must change password first
                Console-->>User: Change Password screen
                User->>Console: submit new password
                Console->>API: POST /auth/change-password
                API->>Auth: changePassword()
                Auth->>DB: update hash set forcePasswordChange false
            end
            Auth->>DB: issue session or token
            API-->>Console: 200 token and role
            Console-->>User: display role menu
        end
    end

    rect rgb(255, 243, 224)
        Note over Manager, LLM: 2. Manager AI find and allocate (BRD Screen 4.2 option 1)
        Manager->>Console: select project and describe requirement
        Console->>API: GET employees skills allocations for match
        API->>Skill: loadCandidates(projectId)
        Skill->>DB: query employees skills allocations activity tags
        DB-->>Skill: candidate data
        Note over Skill: filter out 100 percent utilised before AI
        alt no one with enough free capacity
            Skill-->>Console: message no matches skip LLM
        else has candidates
            API->>Authz: assertProjectOwner(managerUserId, projectId)
            Skill->>LLM: rankCandidates(context, candidates)
            LLM-->>Skill: ranked matches and reasons
            Skill-->>Console: AI results with verify note
        end
        Manager->>Console: select employee percent dates confirm
        Console->>API: POST /allocations
        API->>Authz: assertCanAllocate(managerUserId, projectId)
        API->>Alloc: allocate(request)
        Alloc->>DB: project status ACTIVE or PLANNED
        Alloc->>Calc: validateNewAllocation(employeeId, percent, from, to)
        Calc->>DB: sum overlapping allocation percent
        alt total exceeds 100 percent
            Alloc-->>Console: 409 over-allocation error
            Console-->>Manager: show conflict warning
        else valid
            Alloc->>DB: persist Allocation ACTIVE
            Alloc->>DB: update Employee workStatus ALLOCATED if needed
            Alloc-->>Console: 201 allocation confirmed
            Console-->>Manager: allocation saved
        end
    end

    rect rgb(232, 245, 233)
        Note over Employee, DB: 3. Employee submit timesheet (BRD Screen 5.1)
        Employee->>Console: select week start date
        Console->>API: GET /employees/me/allocations?week=
        API->>TS: loadActiveAllocationsForWeek(employeeId, week)
        TS->>DB: query active allocations
        DB-->>TS: projects and expected hours
        TS-->>Console: 200 project list
        Console-->>Employee: per-project hours and activity tags form
        Employee->>Console: enter hours and tags per project submit
        Console->>API: POST /timesheets
        API->>TS: submitWeek(employeeId, weekStart, entries)
        loop each entry server validation
            TS->>DB: check allocated duplicate week future week
            TS->>TS: hours cap vs allocation percent and max weekly hours
        end
        alt validation fails
            TS-->>Console: 400 validation error
        else valid
            TS->>DB: save TimesheetWeek SUBMITTED and entries
            TS-->>Console: 201 SUBMITTED
            Console-->>Employee: timesheet submitted
        end
    end

    rect rgb(245, 240, 250)
        Note over Sched, DB: 4. Background scheduler (BRD section 4.1)
        loop every schedulerIntervalHours
            Sched->>DB: load SystemConfiguration interval
            Sched->>DB: recompute employee utilisation and BENCH or ALLOCATED
            Sched->>DB: query milestones and recent timesheet hours
            Sched->>DB: update Project healthStatus and risk flags
            Sched->>DB: mark TimesheetWeek MISSED if week ended unsubmitted
        end
    end

    rect rgb(255, 248, 230)
        Note over Manager, LLM: 5. Manager AI risk summary (BRD Screen 4.3 A and 4.5)
        Manager->>Console: request risk summary for project
        Console->>API: GET /projects/{id}/risk-summary
        API->>Authz: assertProjectOwner(managerUserId, projectId)
        API->>Risk: buildRiskContext(projectId)
        Risk->>DB: milestones allocations recent timesheet hours
        DB-->>Risk: factual project data only
        Note over Risk, LLM: LLM never queries database
        Risk->>LLM: summarizeRisk(context)
        LLM-->>Risk: plain English paragraph
        Risk-->>Console: 200 summary text
        Console-->>Manager: display paragraph and AI-generated note
    end

    rect rgb(240, 248, 255)
        Note over Admin, DB: 6. Admin onboard user and employee (BRD 3.4.1 and 3.1.1)
        Admin->>Console: create user account
        Console->>API: POST /users
        API->>Auth: createUser(role, temp password)
        Auth->>DB: insert User forcePasswordChange true
        Admin->>Console: add employee with userId
        Console->>API: POST /employees
        API->>DB: validate userId link insert Employee BENCH
        API-->>Console: 201 employee created
        Console-->>Admin: success note link user and employee
    end
```

> **Note:** REST paths are illustrative (BRD does not mandate URLs). Behaviour matches BRD screens and validation rules.

---

## BRD coverage catalogue

| § | Flow | BRD |
|---|------|-----|
| 1 | Login + change password | Screen 1 |
| 2 | Admin create user + add employee | Screen 3.4.1, 3.1.1 |
| 3 | Manager AI skill match + allocate + utilisation guard | Screen 4.2, “How the AI Works” |
| 4 | Manager AI risk summary | Screen 4.3 [A], 4.5 |
| 5 | Employee submit timesheet | Screen 5.1 |
| 6 | Background scheduler | §4.1 |

**Same pattern, not drawn separately:** Admin manage projects/milestones (3.2), view allocations (3.3), system config (3.5), Manager dashboard (4.1), direct allocate without AI (4.2 opt 2), end allocation (4.2 opt 3). **V3:** no Sign Up — all accounts via §2 only.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-03 | Initial master sequence diagram |
| 2026-06-03 | Merged Claude SVG flows; added §5 risk summary, §6 Admin onboard, enhanced §1–§4 |
| 2026-06-03 | **BRD V3:** §6 is sole account-creation path; Sign Up removed from catalogue |
| 2026-06-03 | Reordered §1–§6; split HTML into six diagrams with per-section actors |
