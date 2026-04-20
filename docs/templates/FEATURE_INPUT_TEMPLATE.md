# 🎯 FEATURE Brief: [Feature Name]

**Author:** [Your Name] ([your.email@company.com])
**Project:** [project-id] (optional - defaults to config.yml → project_key)
**Route:** [route-name] (feature, epic, story, spike, hotfix)

---

## 🎯 The Goal

[Describe what you're building and why. Write in narrative form - explain the problem, current state, desired future state, and key technical considerations. Be as detailed as you need.]


---

## 🔗 Business Context & Links

*Provide IDs, links, or relative file paths below. AI will fetch data from Jira/Confluence automatically.*

* **Jira Epic/Stories:** `PROJ-123, PROJ-456` (comma-separated issue keys)
* **Confluence Pages:** `123456789, 987654321` (comma-separated page IDs from URL)
* **Local Documents:** `./specs/design.md, ./docs/architecture.pdf` (relative paths)
* **Legacy Code Entrypoints:**
    - `repo-name/.../ClassName.java` (file paths to understand existing patterns)
    - `repo-name/.../AnotherClass.kt`

---

## Git Repository & Modules

- repo-name
- repo-name/module-name

---

## 📐 Known Constraints & NFRs

*List any constraints, non-functional requirements, performance targets, compliance needs, etc.*

* **Performance:** Must handle 1 billion queries/day, <2ms p95 latency
* **Architecture:** Must follow [pattern/standard], require OpenAPI documentation
* **Observability:** Must add Micrometer metrics, Grafana dashboards
* **Compliance:** GDPR data retention, audit logging required
* **Technology:** Kotlin, Java 17, Spring Boot 3.5, Elasticsearch 9.x
* **Migration:** Zero-downtime migration, dual-write strategy during transition
* **Compatibility:** No breaking changes to existing search behavior
