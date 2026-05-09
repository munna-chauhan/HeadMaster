---
name: draw
description: Generate diagrams as native .drawio files. Use when user asks to create, draw, design, or generate any diagram, flowchart, architecture, ER, sequence, state machine, network, org chart, or mentions draw.io, drawio, .drawio, or diagram export to PNG/SVG/PDF.
argument-hint: "what to draw" [-o output-path] [--format drawio|png|svg|pdf]
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

# Draw

Generate diagrams as native `.drawio` files. Optional export to `.drawio.png`, `.drawio.svg`, `.drawio.pdf` — all embed source XML so exported files remain editable in draw.io.

Three modes, chosen by diagram type:
- **Mermaid** — flowcharts, sequences, state machines, ER, class, C4, git, gantt, mindmaps
- **XML** — complex architecture, swimlanes, styled containers, network/deployment diagrams
- **CSV** — org charts, hierarchical structures, tabular data diagrams

## Usage

```
/draw "system architecture for content publication"
/draw "sequence diagram for auth flow"
/draw "ER diagram for order tables" --format svg
/draw "CI/CD pipeline" --format png -o ./docs/diagrams
/draw "org chart from this data" --format drawio
```

## Steps

### 1. Resolve output

- `-o path` provided → use it
- Feature slug active → `docs/features/{project}/{slug}/diagrams/`
- Otherwise → current working directory
- Create directory if absent
- Filename: descriptive, lowercase-hyphenated (e.g. `auth-flow`, `order-er`, `system-arch`)

### 2. Choose mode

| Use Mermaid | Use XML | Use CSV |
|-------------|---------|---------|
| flowchart, sequence, state machine, ER, class diagram, git branch, gantt, journey, C4 context/container, mindmap, timeline, pie, quadrant, architecture-beta | architecture with boundaries/containers, swimlane processes, network/deployment, divergence maps, diagrams needing precise styling | org charts, hierarchical data, tabular data diagrams |

Rule of thumb: Mermaid for ≤20 nodes or any type in the Mermaid column; XML when you need nested containers, custom shapes, or precise visual control.

### 3. Generate content

**Mermaid** — use the correct type keyword on the first line. Quote labels with special characters. One statement per line.

Supported types: `flowchart`/`graph`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`, `classDiagram`, `gitGraph`, `journey`, `gantt`, `mindmap`, `timeline`, `pie`, `quadrantChart`, `C4Context`, `C4Container`, `C4Component`, `architecture-beta`, `kanban`, `sankey-beta`.

**Visual discipline (MANDATORY):**
- Prefer `flowchart LR` unless vertical flow required
- ≤20 nodes, verb-noun labels (≤5 words), no long text in nodes
- `classDef` for color consistency when applicable

**XML** — mxGraphModel format. Load rules from `.claude/skills/draw/references/xml-rules.md` before generating XML.

**CSV** — follow draw.io CSV import spec with `## config:` header for layout and style options.

---

### 4. Open in draw.io via MCP

Call the matching MCP tool immediately after generating content:

| Mode    | Tool                               |
| ------- | ---------------------------------- |
| Mermaid | `mcp__drawio__open_drawio_mermaid` |
| XML     | `mcp__drawio__open_drawio_xml`     |
| CSV     | `mcp__drawio__open_drawio_csv`     |

### 5. Write source file

Always write source to disk:
- Mermaid → `{output}/{name}.mmd`
- XML → `{output}/{name}.drawio`
- CSV → `{output}/{name}.csv`

### 6. Export (if requested)

If user requested `--format png|svg|pdf`, locate the draw.io CLI:

| Platform | CLI path                                           |
| -------- | -------------------------------------------------- |
| WSL2     | `/mnt/c/Program Files/draw.io/draw.io.exe`         |
| macOS    | `/Applications/draw.io.app/Contents/MacOS/draw.io` |
| Linux    | `drawio`                                           |
| Windows  | `"C:\Program Files\draw.io\draw.io.exe"`           |

Detect WSL2: `grep -qi microsoft /proc/version 2>/dev/null && echo WSL2`

Export command:
```bash
drawio -x -f <format> -e -b 10 -o {name}.drawio.<format> {name}.drawio
```

Flags: `-x` export, `-f` format (`png`/`svg`/`pdf`), `-e` embed XML, `-b 10` border.

After successful export: delete the `.drawio` source (the export already embeds the full XML).

If CLI not found: keep `.drawio`, tell user to install the draw.io desktop app to enable export.

Optional post-processing (better edge routing): `npx @drawio/postprocess {name}.drawio` — skip silently if unavailable.

## Output artifacts

```
{output-dir}/
├── {name}.drawio
├── {name}.mmd
├── {name}.csv
├── {name}.drawio.png
├── {name}.drawio.svg
└── {name}.drawio.pdf
```
