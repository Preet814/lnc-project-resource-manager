# Project & Resource Management Tool

## Business Requirements Document (BRD)

### Learn & Code — Final Project

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [User Roles](#3-user-roles)
4. [End-to-End Console Application](#4-end-to-end-console-application)
  - [4.1 Scope](#41-scope)
    - [What developers design themselves](#what-developers-design-themselves)
  - [4.2 Console Screens](#42-console-screens)
  - [4.3 Technical Requirements](#43-technical-requirements)

## 1. Overview

The **Project & Resource Management (PRM) Tool** is a console-based client-server application built to solve real operational problems faced by service-based IT companies. It replaces manual spreadsheet-driven resource planning with a single, intelligent system that tracks employees, projects, allocations, and timesheets — and uses an LLM (Large Language Model) to intelligently match people to projects and surface project health risks in plain English.

This document specifies a fully functional console client and REST server. An optional web or desktop UI may be added as a bonus but is never a requirement.

---

## 2. Problem Statement

### The Context

TechServe Solutions is an IT services company. Every week, delivery managers across the organisation face the same frustrating cycle: they receive a new project requirement, spend hours searching through Excel sheets, asking around in chat groups, and making phone calls to figure out who is available, who has the right skills, and whether the current projects are on track.

This is not a technology problem — it is an **information problem**. The data exists, but it is scattered, outdated, and inaccessible in the moment it is needed.

### The Pain Points


| Pain Point                                   | Business Impact                                                                                                                                                  |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **No visibility of who is free (on bench)**  | Managers hire contractors unnecessarily while skilled employees sit idle. Bench cost increases.                                                                  |
| **Manual skill search**                      | A manager needs a Java + Microservices developer. They send emails, check spreadsheets. Hours are lost. Sometimes the wrong person is chosen.                    |
| **Over-allocation**                          | An employee is put on two projects totalling 130% utilisation. Both projects slow down. The employee burns out. Neither manager knew about the other allocation. |
| **No project health visibility**             | A milestone slips by two weeks before the manager notices. By then, it is too late to recover without cost.                                                      |
| **Timesheet inaccuracy**                     | Engineers fill timesheets at month-end, from memory. Hours are approximated. Billing to clients becomes inaccurate.                                              |
| **No evidence of skill growth**              | An employee learned WebSocket development on their last project, but nobody updated their profile. The next manager searching for that skill won't find them.    |
| **Managers spend too much time on planning** | An average delivery manager spends 6–8 hours per week on spreadsheet-based resource planning — time that should be spent on delivery.                            |


### The Solution

The PRM Tool provides a **single source of truth** for all project and people data. It answers the questions that currently cost hours of manual work:

- *"Who is on bench right now and what can they do?"*
- *"Who is the best match for this new project requirement?"*
- *"Is Project Alpha on track or at risk?"*
- *"Did everyone on my team submit their timesheets this week?"*

The system enforces allocation rules automatically (preventing over-allocation), captures real skill usage through timesheet activity tags, and uses an LLM to turn raw data into actionable, plain-English recommendations.

---

## 3. User Roles

The application has **three** roles. Each role sees a different menu and has different capabilities.

### 3.1 Admin

The Admin is the **system operator** — typically an HR or operations team member. They manage the master data that the rest of the system depends on. They do not manage day-to-day project operations.

**Responsibilities:**

- Create user accounts for all roles in scope — Admin, Manager, and Employee
- Add, update, and deactivate employee profiles
- Assign and manage skills per employee (with proficiency levels)
- Create and update projects and their milestones
- View the full company-wide allocation matrix
- Configure system settings: LLM API key, scheduler interval, max weekly hours
- Reset passwords and deactivate user accounts

**Access:** Admin menu only. Cannot allocate resources or view timesheets.

> **First Admin Bootstrap:** The very first Admin account cannot be created through the application (since there is no Admin yet to create it). It is inserted directly into the database using a one-time seed/setup script included with the project. Default credentials (`admin` / `Admin@1234`) must be changed on first login. All subsequent Admin accounts are created by an existing Admin from within the application.

---

### 3.2 Manager

The Manager is the **delivery manager** — the person responsible for running projects and planning the team. They are the primary day-to-day user of the system.

**Responsibilities:**

- Search for available employees using natural language AI queries
- Allocate employees to their projects (with utilisation % and date range)
- Monitor project health (milestone status, effort tracking)
- View submitted employee timesheets for their team (read-only)
- Use the AI Assistant to get skill match suggestions and project risk summaries
- See team timesheet status, including weeks flagged as missed, from the Timesheets screen

**Access:** Manager menu only. Cannot modify employee profiles or system settings.

---

### 3.3 Employee

The Employee is the **individual contributor** — a developer, tester, designer, or any resource who is allocated to projects and logs their own work.

**Responsibilities:**

- Submit weekly timesheets: log hours worked per project
- Tag the type of work done (activity tags) — this powers the skill matching AI
- View their own allocation history and timesheet history
- See their own timesheet status (submitted or missed) in history

**Access:** Employee menu only. Cannot view other employees, projects, or allocation data.

> **Why this role matters:** Only the employee knows exactly what they worked on in a given week. Activity tags filled by the employee (e.g., "Microservices", "WebSocket", "Database Design") become the real evidence of skill usage — more accurate than a static profile set at onboarding. This data directly improves the quality of the AI Skill Matcher.

---

## 4. End-to-End Console Application

### 4.1 Scope

The deliverable is a complete, working console application for **Admin**, **Manager**, and **Employee** roles. Every feature described in this section must be functional and connected to the server via REST APIs.

**In scope:**

- Authentication: Login, Logout for all roles in scope — accounts are created by Admin only
- Admin: Full employee and project management
- Manager: Resource search (AI natural language query), allocation, project health view, basic timesheet view
- Employee: Timesheet submission with hours and activity tags, allocation view
- Background scheduler: Utilisation computation + project health flagging
- AI Skill Matcher: Natural language resource search
- AI Risk Summary: Plain-English project health paragraph

Optional web or desktop UI is never required.

#### What developers design themselves

This BRD defines **what** the system must do (screens, rules, outcomes). It intentionally does **not** prescribe full technical design. Teams are expected to find their own solutions for:

- Database schema (tables, keys, types, migrations) — names mentioned in screens and AI flows are illustrative, not a specification
- REST API contracts beyond behavior implied by screens (URL layout, DTOs, status codes, error format)
- Programming language, frameworks, project structure, and console UI implementation
- How login and logged-in access are handled between client and server, scheduler threading, and deployment
- LLM prompt text, parsing of hours from natural language, and API key storage

---

### 4.2 Console Screens

Each screen below shows the exact console layout the user sees. Every screen has a `[B] Back` option that returns to the previous screen, except the main menus which have a `Logout` option.

---

#### Screen 1 — Application Start / Login

This is the first screen the user sees when the application launches.

```
╔══════════════════════════════════════════════╗
║    PROJECT & RESOURCE MANAGEMENT TOOL        ║
║    Learn & Code — Final Project              ║
╚══════════════════════════════════════════════╝

1. Login
2. Exit

Enter option: _
```

**Option 1 — Login:** Prompts for username and password. Credentials are validated via the server. On success, the server checks if it is a first login (accounts created by Admin have `force_password_change = true`). If yes, the user is redirected to the **Change Password** screen before reaching their menu. On failure, shows an error and returns to this screen.

**Forced Password Change Screen** (shown only on first login for Admin-created accounts):

```
╔══════════════════════════════════════════════╗
║    CHANGE PASSWORD                           ║
║    You must set a new password to continue.  ║
╚══════════════════════════════════════════════╝

New Password        : _
Confirm Password    : _

──────────────────────────────────────────────
[S] Save and Continue

Password updated. Welcome! ✓
```

This screen cannot be skipped. The application blocks access to all menus until the password is changed. The `force_password_change` flag is set to `false` once saved.

**Option 2 — Exit:** Terminates the application gracefully.

---

#### Screen 3 — Admin Menu

Shown after a successful Admin login.

```
╔══════════════════════════════════════════════╗
║    ADMIN PANEL                               ║
║    Welcome, [Name]  |  [DD-MM-YYYY  HH:MM]  ║
╚══════════════════════════════════════════════╝

1. Manage Employees
2. Manage Projects
3. View All Allocations
4. Manage Users
5. System Configuration
6. Logout

Enter option: _
```

---

#### Screen 3.1 — Manage Employees

```
╔══════════════════════════════════════════════╗
║    MANAGE EMPLOYEES                          ║
╚══════════════════════════════════════════════╝

1. View All Employees
2. Update Employee
3. Deactivate Employee
4. Manage Employee Skills
5. Assign Manager
6. Back

Enter option: _
```

---

#### Screen 3.1.1 — View All Employees

```
╔══════════════════════════════════════════════╗
║    ALL EMPLOYEES                             ║
╚══════════════════════════════════════════════╝

ID    Name             Department    Status
──────────────────────────────────────────────
101   Ravi Kumar        Backend       ALLOCATED
102   Priya Sharma      Frontend      BENCH
103   Anil Mehta        DevOps        BENCH
104   Neha Joshi        Backend       ALLOCATED
105   Sara Khan         QA            BENCH
──────────────────────────────────────────────
Total: 5   |   Allocated: 2   |   Bench: 3

[F] Filter by Status / Department     [B] Back
```

---

#### Screen 3.1.2 — Deactivate Employee

```
╔══════════════════════════════════════════════╗
║    DEACTIVATE EMPLOYEE                       ║
╚══════════════════════════════════════════════╝

Enter Employee ID: 101

── Ravi Kumar ─────────────────────────────────
Department : Backend
Status     : ALLOCATED (100%)

⚠  Warning: This employee has 2 active allocations.
   Ending their employment will remove them from:
     - Alpha Portal  (50%,  ends 30-Jun-26)
     - Beta CRM      (50%,  ends 31-Jul-26)

Are you sure you want to deactivate Ravi Kumar?
This will: set is_active = false, end all active allocations today,
and block their login account.

[Y] Yes, Deactivate     [B] Cancel

Employee deactivated. ✓
```

> **Deactivation Rules:**
>
> - All active allocations are ended immediately (to_date set to today)
> - The linked user account is also blocked (cannot log in)
> - All historical data (timesheets, past allocations) is preserved
> - Employee can be reactivated by Admin from Manage Users → View All Users

---

#### Screen 3.1.3 — Manage Employee Skills

```
╔══════════════════════════════════════════════╗
║    MANAGE SKILLS                             ║
╚══════════════════════════════════════════════╝

Enter Employee ID: 101

── Ravi Kumar ─────────────────────────────────
Current Skills:
  1.  Java               Intermediate
  2.  Spring Boot        Advanced
  3.  MySQL              Intermediate
──────────────────────────────────────────────

1. Add Skill
2. Update Proficiency Level
3. Remove Skill
4. Back

Enter option: _
```

**Add Skill sub-prompt:**

```
Skill Name        : WebSocket
Category          : (1) Backend  (2) Frontend  (3) DevOps  (4) QA  (5) Other
Enter choice      : 1
Proficiency Level : (1) Beginner  (2) Intermediate  (3) Advanced
Enter choice      : 2

Skill added. ✓
```

> **Skill Category Rule:** Category is selected from a fixed list at the time of adding the skill. It cannot be blank. Admin picks the closest match. This is used in the Resource Dashboard's skill availability summary to group skills by domain.

---

#### Screen 3.1.4 — Assign Manager

```
╔══════════════════════════════════════════════╗
║    ASSIGN MANAGER                            ║
╚══════════════════════════════════════════════╝

Employee User ID : _
Manager User ID  : _

──────────────────────────────────────────────
[S] Save     [B] Back
```

On save, the server links the employee to the specified manager by updating the `manager_id` field on the employee record.

---

#### Screen 3.2 — Manage Projects

```
╔══════════════════════════════════════════════╗
║    MANAGE PROJECTS                           ║
╚══════════════════════════════════════════════╝

1. Create Project
2. View All Projects
3. Update Project Details
4. Manage Milestones
5. Back

Enter option: _
```

---

#### Screen 3.2.1 — Create Project

```
╔══════════════════════════════════════════════╗
║    CREATE PROJECT                            ║
╚══════════════════════════════════════════════╝

Project Name        : _
Description         : _
Start Date          : (DD-MM-YYYY) _
End Date            : (DD-MM-YYYY) _
Status              : (1) PLANNED   (2) ACTIVE   (3) ON_HOLD
Assign Manager      : (Enter Manager ID) _
Total Story Points  : _

──────────────────────────────────────────────
[S] Save     [B] Back
```

---

#### Screen 3.2.2 — View All Projects

```
╔══════════════════════════════════════════════╗
║    ALL PROJECTS                              ║
╚══════════════════════════════════════════════╝

ID    Name              Manager        End Date     Status     SP Done/Total
──────────────────────────────────────────────────────────────────────────────
201   Alpha Portal       Ankit Shah     30-Jun-26    ACTIVE     40 / 120
202   Beta CRM           Ankit Shah     15-Aug-26    ACTIVE     25 / 80
203   Gamma Rewrite      Neha Joshi     01-Jul-26    ACTIVE     10 / 60
204   Delta Migrate      Rohan Verma    30-Sep-26    PLANNED     0 / 100
──────────────────────────────────────────────────────────────────────────────
[B] Back
```

---

#### Screen 3.2.3 — Update Project Details

```
╔══════════════════════════════════════════════╗
║    UPDATE PROJECT DETAILS                    ║
╚══════════════════════════════════════════════╝

Enter Project ID: _

── Alpha Portal ───────────────────────────────
Project Name         : Alpha Portal          (editable)
Description          : Customer web portal   (editable)
Start Date           : 01-Jan-26             (editable)
End Date             : 30-Jun-26             (editable)
Status               : (1) PLANNED   (2) ACTIVE   (3) ON_HOLD   (4) COMPLETED
Assign Manager       : (Enter Manager ID)    (editable)
Total Story Points   : 120                   (editable)
──────────────────────────────────────────────
[S] Save     [B] Back
```

---

#### Screen 3.2.4 — Manage Milestones

```
╔══════════════════════════════════════════════╗
║    MILESTONES                                ║
╚══════════════════════════════════════════════╝

Enter Project ID: 201

── Alpha Portal ───────────────────────────────
#    Title               Due Date     Story Pts   Status
────────────────────────────────────────────────────────
1.   Design Complete      01-Apr-26       20       DONE
2.   Backend API          15-Apr-26       40       IN_PROGRESS
3.   Testing              30-Apr-26       35       NOT_STARTED
4.   Go Live              15-May-26       25       NOT_STARTED
────────────────────────────────────────────────────────
Total: 120 SP   |   Completed: 20 SP   |   Remaining: 100 SP

1. Add Milestone
2. Update Milestone Status
3. Back

Enter option: _
```

**Add Milestone sub-prompt:**

```
Milestone Title  : _
Due Date         : (DD-MM-YYYY) _
Story Points     : _

Milestone added. ✓
```

**Update Milestone Status sub-prompt:**

```
Enter Milestone # : _
New Status        : (1) NOT_STARTED   (2) IN_PROGRESS   (3) DONE

Milestone updated. ✓
```

---

#### Screen 3.3 — View All Allocations (Admin)

```
╔══════════════════════════════════════════════╗
║    ALL ALLOCATIONS                           ║
╚══════════════════════════════════════════════╝

Employee          Project            %      From         To
──────────────────────────────────────────────────────────────
Ravi Kumar         Alpha Portal       50%    01-Mar-26    30-Jun-26
Ravi Kumar         Beta CRM           50%    01-Apr-26    31-Jul-26
Neha Joshi         Alpha Portal      100%    01-Mar-26    30-Jun-26
Sara Khan          Gamma Rewrite      75%    01-Feb-26    01-Jul-26
──────────────────────────────────────────────────────────────
Total Active Allocations: 4

[F] Filter by Employee / Project     [B] Back
```

---

#### Screen 3.4 — Manage Users

```
╔══════════════════════════════════════════════╗
║    MANAGE USERS                              ║
╚══════════════════════════════════════════════╝

1. Create User Account
2. View All Users
3. Reset User Password
4. Deactivate User
5. Back

Enter option: _
```

---

#### Screen 3.4.1 — Create User Account

This is the only place in the application where all user accounts are created — Admin, Manager, and Employee. There is no self-registration.

```
╔══════════════════════════════════════════════╗
║    CREATE USER ACCOUNT                       ║
╚══════════════════════════════════════════════╝

Full Name         : _
Email             : _
Username          : _
Temporary Password: _
Role              : (1) Admin  (2) Manager  (3) Employee

──────────────────────────────────────────────
[S] Save     [B] Back

Account created. User must change password on first login. ✓
```

**Rules:**

- All fields are mandatory
- Username and email must be unique — server rejects duplicates
- Temporary password must meet the same strength requirements (8+ chars, one uppercase, one number)
- The user will be prompted to change this password the first time they log in

---

#### Screen 3.4.2 — View All Users

```
╔══════════════════════════════════════════════╗
║    ALL USERS                                 ║
╚══════════════════════════════════════════════╝

ID    Username          Role        Status
──────────────────────────────────────────────
1     admin             ADMIN       Active
2     ankit.shah        MANAGER     Active
3     neha.joshi        MANAGER     Active
4     ravi.kumar        EMPLOYEE    Active
5     rohan.verma       MANAGER     Active
6     priya.sharma      EMPLOYEE    Inactive
──────────────────────────────────────────────
Total: 6   |   Active: 5   |   Inactive: 1

[R] Reactivate a user     [B] Back
```

**On [R] — Reactivate:**

```
Enter User ID to reactivate: 6

User: Priya Sharma (EMPLOYEE) — currently Inactive

Reactivate this account?
[Y] Yes     [B] Cancel

Account reactivated. Priya Sharma can now log in. ✓
Note: Previous allocations are NOT restored. Admin must re-allocate manually if needed.
```

---

#### Screen 3.4.3 — Reset User Password

```
╔══════════════════════════════════════════════╗
║    RESET USER PASSWORD                       ║
╚══════════════════════════════════════════════╝

Enter Username or User ID: ravi.kumar

User found: Ravi Kumar (EMPLOYEE)

New Temporary Password: _

──────────────────────────────────────────────
[S] Save     [B] Back

Password reset. User will be prompted to change it on next login. ✓
```

---

#### Screen 3.4.4 — Deactivate User

```
╔══════════════════════════════════════════════╗
║    DEACTIVATE USER                           ║
╚══════════════════════════════════════════════╝

Enter Username or User ID: priya.sharma

User found: Priya Sharma (EMPLOYEE)
Status     : Active

Are you sure you want to deactivate this account?
Deactivated users cannot log in. Their data is preserved.

[Y] Yes, Deactivate     [B] Back

User deactivated. ✓
```

**Note:** Deactivation is not deletion. The user's timesheet, allocation, and employee records are preserved. Only the login access is blocked. Accounts can be reactivated from View All Users.

---

#### Screen 3.5 — System Configuration

```
╔══════════════════════════════════════════════╗
║    SYSTEM CONFIGURATION                      ║
╚══════════════════════════════════════════════╝

Current Settings:
  LLM Provider        :  Google Gemini
  LLM API Key         :  ****************************
  Scheduler Interval  :  4 hours
  Max Weekly Hours    :  40

──────────────────────────────────────────────
1. Update LLM API Key
2. Change LLM Provider  (Gemini / Groq)
3. Update Scheduler Interval
4. Update Max Weekly Hours
5. Back

Enter option: _
```

---

#### Screen 4 — Manager Menu

Shown after a successful Manager login.

```
╔══════════════════════════════════════════════╗
║    Welcome, Ankit Shah!  |  14-May-2026  10:30║
╚══════════════════════════════════════════════╝

1. Resource Dashboard
2. Allocate Resource
3. My Projects
4. Timesheets
5. AI Assistant
6. Logout

Enter option: _
```

---

#### Screen 4.1 — Resource Dashboard

> **Manager Visibility Scope:** Managers can only see employees assigned to their own team. All views on this dashboard — bench, partially allocated, and fully allocated — are scoped to the Manager's direct team. There is no company-wide employee visibility for Managers.

```
╔══════════════════════════════════════════════╗
║    RESOURCE DASHBOARD — May 2026             ║
╚══════════════════════════════════════════════╝

ON BENCH  (3 employees available)
──────────────────────────────────────────────
ID    Name             Department    Skills
101   Priya Sharma      Frontend      React, TypeScript, CSS
103   Anil Mehta        DevOps        Docker, Kubernetes, CI/CD
105   Sara Khan         Backend       Python, Django, PostgreSQL

ACTIVE EMPLOYEES
──────────────────────────────────────────────
ID    Name             Alloc %   Availability
102   Ravi Kumar         100%     FULL
104   Neha Joshi          75%     25% free
106   Dev Patel           50%     50% free

──────────────────────────────────────────────
Bench: 3   |   Partial: 2

[D] Drill into employee details     [B] Back
```

**On [D] — Enter Employee ID:**

```
── Ravi Kumar ─────────────────────────────────
Department     : Backend
Current Status : ALLOCATED (100%)
Profile Skills : Java, Spring Boot, MySQL

Active Allocations:
  Project          %     From         To
  Alpha Portal     50%   01-Mar-26    30-Jun-26
  Beta CRM         50%   01-Apr-26    31-Jul-26

Recent Activity Tags (last 4 weeks):
  Microservices Architecture, WebSocket, Backend API, Bug Fixing

[B] Back
```

---

#### Screen 4.2 — Allocate Resource

> **Manager Visibility Scope:** Managers can only search for and allocate employees within their own assigned team. No cross-team or company-wide employee lookup is available from this screen.

This screen has two paths: **AI-assisted search** (recommended) and **direct allocation** (when the Manager already knows who they want). The Manager can also end an existing allocation from this screen.

```
╔══════════════════════════════════════════════╗
║    ALLOCATE RESOURCE                         ║
╚══════════════════════════════════════════════╝

1. Find resource using AI (recommended)
2. Allocate directly (I already know who I want)
3. End an existing allocation
4. Back

Enter option: _
```

```
╔══════════════════════════════════════════════╗
║    ALLOCATE RESOURCE                         ║
╚══════════════════════════════════════════════╝

Step 1 — Select Project
Enter project name or ID: Alpha Portal (201)

Step 2 — Describe your requirement
Type what kind of resource you need:
> I need a backend developer with Java and microservices
  experience, available for at least 3 months from June

Searching... (AI matching in progress)

──────────────────────────────────────────────
AI-MATCHED RESULTS
──────────────────────────────────────────────
#   Name           Skills Match           Availability   Recent Activity
1   Anil Mehta     Microservices, Docker  100% free      Microservices ✓
2   Dev Patel      Java, Spring Boot       50% free      Backend API ✓

Note: Suggestions are AI-generated. Verify before confirming.
──────────────────────────────────────────────

Select employee (enter #, or 0 to search again): 1

── Anil Mehta ─────────────────────────────────
Current Utilisation: 0%   (fully on bench)

Set Allocation:
  Utilisation %   : 50
  From Date       : 01-Jun-2026
  To Date         : 30-Sep-2026

Validating...
  Anil Mehta total in this period: 0% + 50% = 50%   ✓ Valid

[C] Confirm Allocation     [B] Back

Allocation saved. Anil Mehta → Alpha Portal (50%, Jun–Sep 2026) ✓
```

**Validation rules enforced by server:**

- Total utilisation across all overlapping allocations cannot exceed 100%
- From Date must be before To Date
- Project must be in ACTIVE or PLANNED status

---

**Option 2 — Direct Allocation (skip AI):**

```
╔══════════════════════════════════════════════╗
║    DIRECT ALLOCATION                         ║
╚══════════════════════════════════════════════╝

Select Project    : Alpha Portal (201)
Enter Employee ID : 103

── Anil Mehta ─────────────────────────────────
Current Utilisation: 0%   (fully on bench)

Set Allocation:
  Utilisation %   : 50
  From Date       : 01-Jun-2026
  To Date         : 30-Sep-2026

Validating...
  Anil Mehta total in this period: 0% + 50% = 50%   ✓ Valid

[C] Confirm     [B] Back
```

The same server-side validation rules apply as with AI-assisted allocation.

---

**Option 3 — End an Existing Allocation:**

```
╔══════════════════════════════════════════════╗
║    END ALLOCATION                            ║
╚══════════════════════════════════════════════╝

Select Project: Alpha Portal (201)

Active Allocations on this project:
  #   Employee        %     From         To
  1.  Ravi Kumar      50%   01-Mar-26    30-Jun-26
  2.  Neha Joshi      50%   01-Mar-26    30-Jun-26
──────────────────────────────────────────────

Select allocation to end: 1

End Ravi Kumar's allocation on Alpha Portal?
Set end date to today (14-May-2026)?

[Y] Yes, End Now    [B] Back

Allocation ended. Ravi Kumar freed from Alpha Portal as of 14-May-2026. ✓
Employee status updated to BENCH if no other active allocations remain.
```

> **Rule:** Only the Manager who owns the project can end allocations on that project. Ending an allocation sets the `to_date` to today's date and recompute the employee's status.

---

#### Screen 4.3 — My Projects

```
╔══════════════════════════════════════════════╗
║    MY PROJECTS                               ║
╚══════════════════════════════════════════════╝

#    Project          End Date     Health
──────────────────────────────────────────────
1.   Alpha Portal     30-Jun-26    🔴 AT RISK
2.   Beta CRM         15-Aug-26    🟢 ON TRACK
3.   Gamma Rewrite    01-Jul-26    🟡 ATTENTION
──────────────────────────────────────────────

Select project number to view details: 1
```

**Project Detail view:**

```
── Alpha Portal ───────────────────────────────
Health Status : 🔴 AT RISK

Risk Flags:
  ✗  Backend API milestone is 5 days overdue
  ✗  Ravi Kumar logged only 4 hrs last week (expected 20 hrs)
  ✓  Resources are correctly allocated

Milestones:
  #    Title              Due Date     Status
  1.   Design Complete    01-Apr-26    DONE
  2.   Backend API        15-Apr-26    IN_PROGRESS  ⚠ OVERDUE
  3.   Testing            30-Apr-26    NOT_STARTED
  4.   Go Live            15-May-26    NOT_STARTED

Allocated Resources:
  Name           %      From         To
  Ravi Kumar     50%    01-Mar-26    30-Jun-26
  Neha Joshi     50%    01-Mar-26    30-Jun-26

──────────────────────────────────────────────
[A] Get AI Risk Summary     [B] Back
```

**On [A] — AI Risk Summary:**

```
── AI Risk Summary — Alpha Portal ────────────

"The Backend API milestone is at risk of delay. Ravi Kumar
logged only 4 of the expected 20 hours last week, which
suggests a blocker or unavailability that should be investigated.
Testing has not yet started and the deadline is approaching.
The manager should check in with Ravi directly and consider
whether timeline adjustments or additional resources are needed."

  Note: This summary is AI-generated from milestone and timesheet data.

[B] Back
```

---

#### Screen 4.4 — Timesheets (Manager View)

The Manager can view submitted timesheets for their team. Timesheets are read-only from the Manager's perspective (no approve/reject actions in the console flows described here).

```
╔══════════════════════════════════════════════╗
║    TIMESHEETS — MY TEAM                      ║
╚══════════════════════════════════════════════╝

Filter by week (DD-MM-YYYY) or press Enter for current week:
Week: 12-May-2026

──────────────────────────────────────────────
Employee         Project          Hrs    Status
──────────────────────────────────────────────
Ravi Kumar        Alpha Portal     18     SUBMITTED
Ravi Kumar        Beta CRM         20     SUBMITTED
Neha Joshi        Alpha Portal     20     SUBMITTED
Dev Patel         Beta CRM         35     SUBMITTED
Anil Mehta        Gamma Rewrite     0     MISSED ⚠
──────────────────────────────────────────────

[V] View employee timesheet detail     [B] Back
```

---

#### Screen 4.5 — AI Assistant

```
╔══════════════════════════════════════════════╗
║    AI ASSISTANT                              ║
╚══════════════════════════════════════════════╝

1. Skill Match    — Find best employees for a project requirement
2. Risk Summary   — Get a health analysis for a project
3. Back

Enter option: _
```

**Option 1 — Skill Match:**

```
── Skill Match ────────────────────────────────

Describe your project requirement in plain English:
> We need a full-stack developer with React and Node.js experience
  who can join a new project in July for 6 months

Searching... (calling AI)

Results:
  1.  Priya Sharma
      Reason: React and TypeScript expertise; currently on bench and
      fully available from any date; recently active in frontend work.

  2.  Dev Patel
      Reason: React and some Node.js background; currently 50% free
      and available for a new allocation.

  Note: These are AI-generated suggestions. Always verify availability
  and skills with the employee before allocating.

[A] Go to Allocate Resource     [B] Back
```

**Option 2 — Risk Summary:**

```
── Risk Summary ───────────────────────────────

Select project:
  1.  Alpha Portal    🔴 AT RISK
  2.  Beta CRM        🟢 ON TRACK
  3.  Gamma Rewrite   🟡 ATTENTION

Enter project number: 1

Generating AI summary...

"The Backend API milestone is currently overdue by 5 days and
effort logging by Ravi Kumar has been significantly below
expectations at 4 hours versus a projected 20 hours last week.
Testing has not started and the go-live date is less than 6 weeks
away. Immediate action is recommended: a direct conversation with
Ravi to identify blockers, and a realistic assessment of whether
the Testing phase can begin in parallel."

  Note: AI-generated from current milestone and timesheet data.

[B] Back
```

---

#### How the AI Works Under the Hood

This section describes **what happens** when a manager or employee uses AI features — in plain terms, not as a technical build guide.

**The core idea**

All answers come from **data already stored in the system** (people, skills, allocations, timesheets, milestones). The application gathers and checks that data first, then asks the language model to **explain and rank** — the model does not log into the database or search the company on its own. Only information the application selects is shared with the model. Suggestions are **recommendations**; the manager still confirms allocation and availability before anything is final.

---

##### Skill Match — Full-time or open-ended need

**When it applies:** The manager has chosen a project and describes a need without a small weekly hours figure — for example, *"I need a Java developer with microservices experience for three months."*

**What happens:**

1. The manager enters the requirement on the Allocate Resource or AI Assistant screen (together with the selected project).
2. The application loads relevant employee information: profile skills, current allocations, bench or allocated status, and recent work tags from timesheets.
3. The application works out who has enough **free capacity** for a full-time style request (based on utilisation and the organisation’s maximum weekly hours setting). People who are fully booked or do not have enough free time are left out before any AI step.
4. For the remaining candidates, the application sends the manager’s wording plus a summary of those people to the AI service.
5. The AI returns a short ranked list of names with a plain-English **reason** for each (skills, availability, recent work).
6. The console shows the list with a clear note that results are AI-generated and must be verified before allocation.

**Example outcome:** Anil Mehta might appear first (microservices skills, on bench); Priya Sharma second (partial availability, suitable skills). Someone at 100% allocation would not appear because they were excluded in step 3.

---

##### Skill Match — Part-time or limited hours

**When it applies:** The manager specifies a limited commitment — for example, *"about ten hours a week for UI testing."*

**What happens:**

1. Same starting point: project selected and requirement typed in natural language.
2. The application interprets how many hours per week are needed from the manager’s text.
3. Only employees with **at least that much free time** are considered. If nobody qualifies, the application tells the manager immediately and does not call the AI.
4. Qualified employees are summarized (skills, free hours, recent activity tags) and sent with the requirement to the AI service.
5. The AI suggests the best fits and may indicate a reasonable weekly commitment; the application can relate that to an allocation percentage for the manager’s review.
6. The manager sees names, reasons, free hours, and a suggested allocation level, then chooses whether to proceed.

**What the Manager sees:**

```
AI-MATCHED RESULTS  (for: "10 hrs/week, UI testing")
──────────────────────────────────────────────────────
1.  Priya Sharma     30 hrs free/week
    "React and TypeScript directly relevant to UI testing;
     recent QA activity confirmed in timesheets."
    Suggested allocation: 25%  (≈ 10 hrs/week)

2.  Neha Joshi       10 hrs free/week
    "Exactly 10 free hours available. Backend background —
     UI testing may need a short ramp-up."
    Suggested allocation: 25%  (≈ 10 hrs/week)

Note: AI-generated. Verify before confirming allocation.
──────────────────────────────────────────────────────
Select employee (or 0 to cancel): _
```

---

##### Risk Summary

**When it applies:** The manager views a project (My Projects or AI Assistant) and asks for an AI risk summary for that project.

**What happens:**

1. The manager selects the project to analyse.
2. The application collects factual inputs for that project: milestone titles, due dates and status, who is allocated and at what level, and how many hours were logged on the project in recent weeks compared to what was expected.
3. Those facts are passed to the AI service with a request for a brief, readable summary of **risks and concerns** — not a raw data dump.
4. The AI returns a short paragraph in everyday language (for example, an overdue milestone combined with low logged hours on a key person).
5. The console displays the paragraph with a note that it was generated from milestone and timesheet data and should be used alongside normal project management judgment.

**Example outcome:** The summary might state that a backend milestone is overdue, that one developer logged far fewer hours than expected, and that testing has not started while the go-live date is approaching — prompting the manager to follow up with the team.

---

#### Screen 5 — Employee Menu

Shown after a successful Employee login.

```
╔══════════════════════════════════════════════╗
║    Welcome, Ravi Kumar!  |  14-May-2026      ║
╚══════════════════════════════════════════════╝

  ⚠  Reminder: Timesheet for week 06-May-2026 has not been submitted.

──────────────────────────────────────────────
1. Submit Timesheet
2. View My Timesheets
3. View My Allocations
4. Logout

Enter option: _
```

The reminder is shown only if a timesheet is missing for the most recent completed week. It disappears once submitted.

---

#### Screen 5.1 — Submit Timesheet

```
╔══════════════════════════════════════════════╗
║    SUBMIT TIMESHEET                          ║
╚══════════════════════════════════════════════╝

Employee  : Ravi Kumar
Week Start: Enter date (DD-MM-YYYY) or press Enter for last Monday
          > 12-05-2026

Checking your active allocations for this week...

──────────────────────────────────────────────
PROJECT 1 OF 2 — Alpha Portal
  Allocation: 50%   |   Expected: 20 hrs max
──────────────────────────────────────────────
Hours worked this week: 18

What did you work on? Select activity tags:

  1.  Backend API Development
  2.  Microservices / Architecture
  3.  Database Design & Queries
  4.  WebSocket / Real-time Features
  5.  Frontend Development
  6.  Code Review / Mentoring
  7.  Bug Fixing
  8.  DevOps / Deployment
  9.  Testing & QA
  10. Documentation
  11. Other (type manually)

Select tags (comma-separated): 2, 4

──────────────────────────────────────────────
PROJECT 2 OF 2 — Beta CRM
  Allocation: 50%   |   Expected: 20 hrs max
──────────────────────────────────────────────
Hours worked this week: 20

Select tags (comma-separated): 1, 7

──────────────────────────────────────────────
SUMMARY
  Alpha Portal    18 hrs    [Microservices, WebSocket]
  Beta CRM        20 hrs    [Backend API, Bug Fixing]
  ─────────────────────────────────────────
  Total           38 hrs / 40 hrs max   ✓

──────────────────────────────────────────────
[S] Submit Timesheet     [B] Back

Timesheet submitted successfully. Status: SUBMITTED ✓
```

**Validation rules enforced by server:**

- Employee can only log hours for projects they are allocated to during that week
- Hours per project cannot exceed `(allocation % × max weekly hours)`
- Total hours across all projects cannot exceed the system's configured max weekly hours (default: 40)
- A timesheet for the same week cannot be submitted twice (duplicate check)
- Employee cannot submit for a future week

---

#### Screen 5.2 — View My Timesheets

```
╔══════════════════════════════════════════════╗
║    MY TIMESHEETS                             ║
╚══════════════════════════════════════════════╝

Week Start      Total Hrs    Status
──────────────────────────────────────────────
12-May-2026      38 hrs       SUBMITTED
05-May-2026      40 hrs       SUBMITTED
28-Apr-2026      35 hrs       SUBMITTED
21-Apr-2026       0 hrs       MISSED    ⚠
14-Apr-2026      40 hrs       SUBMITTED
──────────────────────────────────────────────

[V] View week details     [B] Back
```

**On [V] — week detail:**

```
── Week: 05-May-2026 — Status: SUBMITTED ─────

Project          Hrs    Activity Tags
──────────────────────────────────────────────
Alpha Portal     20     Microservices, WebSocket
Beta CRM         20     Backend API, Bug Fixing
──────────────────────────────────────────────
Total: 40 hrs

[B] Back
```

---

#### Screen 5.3 — View My Allocations

```
╔══════════════════════════════════════════════╗
║    MY ALLOCATIONS                            ║
╚══════════════════════════════════════════════╝

Project           %      From         To           Status
──────────────────────────────────────────────────────────
Alpha Portal      50%    01-Mar-26    30-Jun-26    ACTIVE
Beta CRM          50%    01-Apr-26    31-Jul-26    ACTIVE
──────────────────────────────────────────────────────────
Total Utilisation: 100%

[B] Back
```

---

### 4.3 Technical Requirements

The following engineering practices must be reflected in the codebase and explained in project documentation (for example in the README).


| Requirement           | Description                                                                                                                         |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **SOLID Principles**  | Each of the five SOLID principles must be demonstrable in the codebase, with brief examples showing where and how they are applied. |
| **Design Patterns**   | At least one design pattern must be used and documented (e.g. Repository, Adapter, Singleton, Strategy, Factory, or Observer).      |
| **Design Principles** | At least two design principles must be applied and documented (e.g. DRY, YAGNI, Separation of Concerns, Fail Fast, Law of Demeter). |
| **Clean Code**        | Meaningful names, small focused functions, no magic numbers, and no dead or commented-out code.                                     |


