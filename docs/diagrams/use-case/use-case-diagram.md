# PRM Tool — Master Use Case Diagram

**Source:** [PRM_BRD.md](../../../requirements/PRM_BRD.md) · No Sign Up (Admin-only accounts)

---

## Recommended: open in browser (no PlantUML server)

| File | How |
|------|-----|
| **[use-case-diagram.html](./use-case-diagram.html)** | Open in Chrome/Edge — four Mermaid sections (overview, Admin, Manager, Employee+Scheduler). **No URL size limit.** |

Same approach as [class-diagram.html](./class-diagram.html) and [sequence-diagram.html](./sequence-diagram.html).

---

## Why plantuml.com shows “Request header is too large”

The public site sends your **entire diagram source in the HTTP request** (encoded in the URL). The full `use-case-diagram.puml` is too big → Tomcat rejects the header.

**Fixes:**

1. Use **`use-case-diagram.html`** (above) — best for viewing.
2. Paste **one small file** at a time into plantuml.com:
   - [01-overview.puml](./plantuml/use-case-diagram-01-overview.puml)
   - [02-admin.puml](./plantuml/use-case-diagram-02-admin.puml)
   - [03-manager.puml](./plantuml/use-case-diagram-03-manager.puml)
   - [04-employee-scheduler.puml](./plantuml/use-case-diagram-04-employee-scheduler.puml)
3. **Local PlantUML** (VS Code extension or `java -jar plantuml.jar file.puml`) — reads from disk, no URL limit.
4. **mermaid.live** — copy a section from the HTML `<script>` block or use the flowcharts below.

---

## Alternatives to one big PlantUML file

| Tool | Pros | Cons |
|------|------|------|
| **HTML + Mermaid** (`use-case-diagram.html`) | Works offline in browser; matches your other diagrams | Flowchart style, not strict UML ovals |
| **Split `.puml` (01–04)** | Real UML on plantuml.com | Four exports for submission |
| **VS Code PlantUML** | Full UML, local file | Needs Java + extension |
| **mermaid.live** | Online, no header limit | Paste one diagram at a time |
| **Draw.io / Lucidchart** | Manual polish | Not in repo unless you export |

The monolithic [use-case-diagram-full.puml](./plantuml/use-case-diagram-full.puml) is for local/VS Code only — **do not paste into plantuml.com**.

---

## BRD traceability (summary)

| Section | BRD |
|---------|-----|
| Auth | Screen 1 — Login, forced Change Password, Logout |
| Admin | Screen 3 — users, employees, projects, allocations, config |
| Manager | Screen 4 — dashboard, allocate (AI/direct/end), projects, timesheets, AI assistant |
| Employee | Screen 5 — submit timesheet (hours, tags, validation), view history |
| Scheduler | §4.1 — utilisation, project health, MISSED timesheets |
| LLM | §4.1 — skill match & risk summary (external) |

Full tables and exclusions: see previous revision content in git history or expand in your submission doc from BRD screens.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-03 | BRD V3: no Guest / Sign Up |
| 2026-06-03 | Split PlantUML 01–04; added `use-case-diagram.html` (Mermaid) for browser viewing |
