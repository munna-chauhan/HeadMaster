# 🎯 Feature Brief: [Feature Name]

**Author:** [Your Name]
**Project:** [project-id] (optional — defaults to config.yml → projects.active)
**Route:** feature | hotfix | spike | epic

---

## 🎯 The Goal

[Describe what you're building or investigating and why. Write in narrative form — explain the problem, current state, desired future state, and key technical considerations. Be as detailed as you need.]

---

## 🔬 Research Questions (spike only)

*If this is a spike/research task, list the specific questions it must answer. Remove this section for other routes.*

1. [e.g., "Which services use Elasticsearch directly?"]
2. [e.g., "What breaking changes exist between ES 5 and 9?"]

---

## 🔗 Business Context & Links

*Provide IDs, links, or relative file paths. AI will fetch Jira/Confluence automatically.*

- **Jira:** `PROJ-123, PROJ-456` (comma-separated issue keys)
- **Confluence:** `123456789` (page IDs from URL)
- **Local Documents:** `./specs/design.md, ./docs/notes.pdf` (relative paths — copied to input/local-docs/)
- **Legacy Code Entrypoints:**
  - `repo-name/.../ClassName.java`
  - `repo-name/.../AnotherClass.kt`

---

## Repositories

### {repo-name}
- path: {relative to HeadMaster root, per config.yml project root}
- modules: [module-a, module-b]   # omit if single root
- tech: {Java 17, Spring Boot 3.2, Maven 3.9}
- build_cmd: {./mvnw clean verify -pl module-a}

---

## 📐 Known Constraints & NFRs

*List any constraints, non-functional requirements, performance targets, compliance needs, etc.*

- **Performance:** [e.g., "<2ms p95 latency"]
- **Architecture:** [e.g., "Must follow existing patterns"]
- **Compliance:** [e.g., "GDPR data retention"]
- **Technology:** [e.g., "Java 8, Spring Boot 1.5, PostgreSQL 9.4"]
- **Migration:** [e.g., "Zero-downtime, dual-write during transition"]
- **Compatibility:** [e.g., "No breaking changes to existing API"]

---

## ❓ Open Questions

*Known unknowns. These drive the Discovery stage.*

1. [e.g., "Which authentication mechanism?"]
2. [e.g., "Should this support multi-region?"]

---

## 👤 Ownership (optional)

- **Technical Owner:** [name or "TBD" — defaults from config.yml]
- **Approver:** [name or "TBD"]
