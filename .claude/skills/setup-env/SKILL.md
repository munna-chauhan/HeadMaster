---
name: setup-env
description: "Scan project repos, detect tech stack per module, write repo-registry.yml. Run once per project or after repo changes."
argument-hint: [--project <name>] [--reset]
---

<SUBAGENT-STOP>
If dispatched as subagent, skip this skill.
</SUBAGENT-STOP>

# Setup Environment

Scans project repo roots → detects repos, modules, tech stack → writes `memory/projects/{project}/repo-registry.yml`. Referenced by `init-feature` Q2 to skip live scanning.

**Re-run** with `--reset` to overwrite existing registry.

---

## Step 0: Load existing registries (learn pattern)

Read all existing `memory/projects/*/repo-registry.yml` files. Extract tool patterns:
- Which tools exist (java-8, java-17, maven, etc.)
- Tool paths per workspace
- Tool compatibility mappings (which repos use which Java version)

Reuse this knowledge when scanning new projects → reduces Q&A.

---

## Step 1: Resolve projects

Read `config.yml projects:`. If `--project <name>` given → process that project only. Otherwise → process all non-`active` projects.

For each project: read `root` path. If path does not exist → warn and skip.

If registry already exists and no `--reset` flag:
> Print: "Registry exists for `{project}` (scanned: {date}). Use --reset to refresh." Skip that project.

---

## Step 2: Scan repos

For each project root — find subdirs at maxdepth 2 containing any build file marker:
`pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle`, `package.json`, `go.mod`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `*.csproj`, `*.fsproj`, `composer.json`, `Gemfile`

Exclude: `node_modules`, `.git`, `target`, `build`, `dist`.

If root itself has a build file → treat as single repo.

---

## Step 3: Detect modules per repo

Per repo, check for multi-module markers:
- Maven: `<modules>` in `pom.xml` → extract `<module>` entries
- Gradle: `include(...)` in `settings.gradle` or `settings.gradle.kts`
- npm: `workspaces` array in `package.json`

No markers → repo root is single module.

---

## Step 4: Detect tech stack per module

Scan build files in module path:

| File | Extract |
|------|---------|
| `pom.xml` | `java.version`, `maven.compiler.target`, `kotlin.version`, `spring-boot.version`, `spring.version` |
| `build.gradle` / `build.gradle.kts` | `sourceCompatibility`, `javaVersion`, `kotlinVersion` |
| `package.json` | `engines.node`, top 5 `dependencies` keys |
| `go.mod` | first line (`module` + `go` directive) |
| `pyproject.toml` / `requirements.txt` | `python_requires`, first 5 deps |
| `*.csproj` / `*.fsproj` | `TargetFramework` |
| `Cargo.toml` | `[package].rust-version`, `edition` |
| `composer.json` | `require.php` (PHP version constraint) |
| `Gemfile` | `ruby` directive |

Infer `build_cmd`:
- `./mvnw` exists → `./mvnw clean verify`; else `mvn clean verify`
- `./gradlew` exists → `./gradlew build`; else `gradle build`
- `package.json` → check `scripts.build`, `scripts.test`; default `npm run build`
- `go.mod` → `go build ./...`
- `requirements.txt` / `pyproject.toml` → `pytest`
- `Cargo.toml` → `cargo build`
- `*.csproj` / `*.fsproj` → `dotnet build`
- `composer.json` → `composer install`
- `Gemfile` → `bundle exec rake`

---

## Step 5: Auto-detect all tool versions in workspace

From tech stack → determine required tools: Java, Maven, Gradle, Python, Node, Go, .NET, Rust/Cargo, PHP/Composer, Ruby/Bundler.

For each tool:
- Search PATH: `{tool} --version` or `{tool} -version`
- Search workspace standard paths: `C:\Program Files\*`, `/opt/*`, `~/.*`
- Reuse paths from Step 0 (existing registries)
- Capture: tool-name, version, full path, status (`verified` | `unverified`)

For Java: scan for multiple versions (java-8, java-17, etc.). Extract version from path or `java -version` output.

Build tool compatibility map: `tool-version → [compatible-repos]` (from tech stack analysis).

---

## Step 5a: Extract version requirements per module

For each detected tech (Java, Python, Node, etc.):
- Maven: parse `pom.xml` → `java.version`, `maven.compiler.target`
- Gradle: parse `sourceCompatibility`, `javaVersion`
- package.json: extract `engines.node`
- go.mod: extract `go` directive
- pyproject.toml/requirements.txt: extract `python_requires`

Create requirement map: `repo → {java_req, python_req, node_req, ...}`

---

## Step 5b: Build tool compatibility matrix

For each detected tool version + module requirement:
- Compare: detected-version ≥ required-version
- Mark: `compatible | mismatch | unknown`
- Build: `tool-version → [compatible-repos]` list
- Build: `repo-module → [compatible-tools]` map

If tool missing but required → Step 5c (Q&A).

---

## Step 5c: Ask for missing tools only (P0 — if truly missing)

Per ask-user-protocol.md: header `Tools`, P0 priority.

Ask ONLY if tool cannot be auto-detected:
- `[P0] {TOOL} required by {N} repos but not found. Provide path or skip?`
- Options: Provide path | Use system PATH (if new location available) | Skip validation

Validate user path: `{path} --version` → capture version + update compatibility matrix.

---

## Step 6: Confirm with compatibility matrix

Per ask-user-protocol.md.

Present two tables:
1. **Tool Availability**: `tool → version | path | status | compatible-repos`
2. **Repo Readiness**: `repo → tech | best-tool | status`

Warn if:
- Tool missing (required but not found)
- Version mismatch (detected < required)
- No compatible tool available for repo

Ask: "Proceed with detected tools?" 
- Apply user corrections before writing.
- If user provides alternate paths → re-run compatibility matrix.

---

## Step 7: Write registry

`memory/projects/{project}/repo-registry.yml`:

```yaml
scanned: {ISO-date}

tools:
  {tool-name}:                    # e.g., java-8, java-17, maven, python, node
    path: {full-path}
    version: {version}
    status: verified | unverified | missing
    compatible_repos:             # Repos that use this tool
      - {repo-name}
      - ...

repos:
  {repo-name}:
    path: {root-relative path}
    default_build_cmd: {cmd}
    modules:
      - name: {module}
        tech: {lang+version}
        framework: {name+version}
        build_tool: {tool+version}
        build_cmd: {cmd}
        tool_status: compatible-{tool} | mismatch | unknown
        required_tools:             # Versions this module needs
          java: "8+"
          maven: "3.9+"
```

Create `memory/projects/` dir if absent.

**Reusable across projects:** Next project scans reads this registry → recognizes tool patterns.

---

## Step 8: Summary

```
Registry written: {project} ({N} repos, {M} modules)
Tools: {tool-list with status}
  - {tool-name} v{version}: {N} repos compatible
  - ... (any mismatches flagged)
Next: /init-feature — use registry for repo selection.
```

---

## Token Efficiency Notes

- **Step 0:** Reuse existing registries → skip redundant tool searches on multi-project runs
- **Step 5:** Auto-detect all tool versions once → build comprehensive map → minimal Q&A
- **Step 5c:** Ask for tools ONLY if truly missing after auto-detection → no unnecessary prompts
- **Step 6:** Single confirmation table → no back-and-forth → one user decision
- **Registry reuse:** Next project scan reads this registry → learns workspace tool layout → faster scan
