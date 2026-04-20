---
name: draw
description: Always use when user asks to create, edit, review, generate, draw, or design a diagram, flowchart, architecture diagram, ER diagram, sequence diagram, class diagram, network diagram, mockup, wireframe, or UI sketch, or mentions draw.io, drawio, drawoi, .drawio files, or diagram export to PNG/SVG/PDF.
argument-hint: [ <feature-name> | <external-location> ] "<what to draw>"
---

# Draw.io Diagram Skill

Respond concisely throughout. Drop articles, filler, hedging. Fragments OK. → for causality. Tables over prose.
Code/paths exact.

Generate draw.io diagrams as native `.drawio` files with PNG export by default. Optionally export to SVG or PDF with
embedded XML (so the exported file remains editable in draw.io).

**Platform:** Windows only.

## Invocation

```
/draw <feature-name> "what to draw"       → writes to docs/features/{slug}/diagrams/
/draw <external-location> "what to draw"  → writes to the specified path
/draw "what to draw"                      → writes to docs/features/{slug}/diagrams/ if active feature exists, else ask
```

- `<feature-name>` — feature slug; resolves to `docs/features/{slug}/diagrams/`
- `<external-location>` — any explicit path (relative or absolute)
- If neither is provided and no active feature is detected, ask the user where to save before proceeding

## Resolving the output directory

1. If `<feature-name>` matches a slug in `docs/features/`, use `docs/features/{slug}/diagrams/`
2. If `<external-location>` is an explicit path, use it as-is
3. If neither: check `docs/features/` for a single active feature (one folder with a `planning/` subfolder). If exactly
   one found, use its `diagrams/` folder
4. If still ambiguous: load `AskUserQuestion` tool (`ToolSearch → query: "select:AskUserQuestion"`) and ask the user to
   confirm the output location before proceeding

Create the output directory if it does not exist.

## How to create a diagram

1. **Resolve output directory** (see above)
2. **Clarify if needed** — if the diagram description is ambiguous or missing key details, ask one focused question
   using `AskUserQuestion` before generating (see Clarification section)
3. **Generate draw.io XML** in mxGraphModel format
4. **Write the XML** to `<output-dir>/<name>.drawio`
5. **Export to PNG** (default): locate the draw.io CLI, run export with `--embed-diagram`. Keep the `.drawio` source
   file — never delete it. If CLI not found or export fails, keep the `.drawio` file and inform the user.
6. **If user requested SVG or PDF**: export to that format instead of PNG, same rules apply
7. **Open the result**: `start <file>`. If it fails, print the absolute file path

## Choosing the output format

Default output is `.drawio` + PNG. Both files kept. Override by mentioning a format:

- `/draw "flowchart for login"` → `login-flow.drawio` + `login-flow.drawio.png` (both kept)
- `/draw svg "ER diagram"` → `er-diagram.drawio` + `er-diagram.drawio.svg` (both kept)
- `/draw pdf "architecture overview"` → `architecture-overview.drawio` + `architecture-overview.drawio.pdf` (both kept)
- `/draw drawio "sequence diagram"` → `sequence-diagram.drawio` only (no export)

| Format            | Extension     | Embed XML |
|-------------------|---------------|-----------|
| `png` *(default)* | `.drawio.png` | Yes       |
| `svg`             | `.drawio.svg` | Yes       |
| `pdf`             | `.drawio.pdf` | Yes       |
| `drawio`          | `.drawio`     | Native    |

PNG, SVG, and PDF embed the full diagram XML — opening them in draw.io recovers the editable diagram.

## Clarification (when needed)

If the diagram request is ambiguous, load `AskUserQuestion` and ask **one question at a time**:

```python
AskUserQuestion({
    "questions": [{
        "header": "Diagram Scope",
        "question": "Q1: [specific question about what's unclear and why it affects the diagram]?",
        "multiSelect": false,
        "options": [
            {"label": "Option A (Recommended)", "description": "Trade-offs"},
            {"label": "Option B", "description": "Trade-offs"}
        ]
    }]
})
```

After each answer: acknowledge (`✅ Q{n}: [answer]`), then proceed or ask the next question if still needed. Do not ask
more than 3 questions total.

## draw.io CLI (Windows)

Run `where drawio` first. If not on PATH, fall back to:

```
"C:\Program Files\draw.io\draw.io.exe"
```

### Export command

```
drawio -x -f <format> -e -b 10 -o <output> <input.drawio>
```

Key flags:

- `-x` export mode
- `-f` format: `png`, `svg`, `pdf`
- `-e` embed diagram XML in output
- `-o` output file path
- `-b` border width (default: 0)
- `-t` transparent background (PNG only)
- `-s` scale
- `--width` / `--height` fit dimensions (preserves aspect ratio)
- `-a` all pages (PDF only)
- `-p` page index, 1-based

If export exits non-zero or hangs, kill the process, keep the `.drawio` file, and inform the user.

## File naming

- Descriptive, lowercase, hyphenated: `login-flow`, `database-schema`
- Both files always kept: `name.drawio` (source) + `name.drawio.png/svg/pdf` (export)
- Never delete the `.drawio` source — needed for future edits

## XML format

A `.drawio` file is native mxGraphModel XML. Always generate XML directly — never Mermaid or CSV (those require
server-side conversion).

### Basic structure

```xml

<mxGraphModel adaptiveColors="auto">
    <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
    </root>
</mxGraphModel>
```

- `adaptiveColors="auto"` — optional; enables dark mode color adaptation
- `id="0"` — root layer; `id="1"` — default parent layer
- All diagram elements use `parent="1"` unless using multiple layers

## XML reference

For the complete draw.io XML reference (styles, edge routing, containers, layers, metadata, dark mode), fetch at
runtime:
https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md

## Troubleshooting

| Problem              | Solution                                                           |
|----------------------|--------------------------------------------------------------------|
| CLI not found        | Keep `.drawio`, tell user to install draw.io desktop app           |
| Export empty/corrupt | Validate XML well-formedness before writing                        |
| Diagram blank        | Ensure `id="0"` and `id="1"` root cells are present                |
| Edges not rendering  | Every edge needs `<mxGeometry relative="1" as="geometry" />` child |
| Export hangs         | Kill process, keep `.drawio`, inform user                          |
| File won't open      | Print absolute file path                                           |

## CRITICAL: XML well-formedness

- **NEVER include XML comments (`<!-- -->`)** — forbidden, causes parse errors
- Escape special characters: `&amp;`, `&lt;`, `&gt;`, `&quot;`
- Always use unique `id` values for each `mxCell`

## CRITICAL: Converting from Mermaid or any source format

When the user provides a Mermaid diagram, HTML, markdown, or any other source to convert:

**Extract only the logical structure:**

- Nodes (id, label, shape)
- Edges (source, target, label)
- Groupings / subgraphs → draw.io containers

**Strip everything else — do NOT carry over:**

- HTML tags (`<br>`, `<b>`, `<div>`, `<span>`, `<p>`, `<style>`, etc.)
- CSS classes or inline styles from the source
- JavaScript, script blocks, or event handlers
- Mermaid directives (`%%`, `classDef`, `click`, `style`, `linkStyle`)
- Markdown formatting (`**bold**`, `_italic_`, backticks)
- Any content that is not a node label, edge label, or structural grouping

**Label rules — plain text only:**

- `value` attribute must contain plain text only — no HTML tags whatsoever
- If a Mermaid label contains HTML (e.g. `"<b>Title</b><br/>Sub"`), flatten it: extract visible text, discard tags →
  `"Title: Sub"`
- If a label uses `\n` or `<br>` for line breaks, replace with a space or colon separator
- Never set `html="1"` on a cell unless you are intentionally using draw.io HTML labels and the content is clean,
  escaped draw.io HTML — not source HTML

## CRITICAL: Node and edge geometry

Poor spacing is the most common visual defect. Apply these minimums on every diagram:

**Nodes (vertex cells):**

- Minimum width: `120`, minimum height: `60`
- For nodes with longer labels (>20 chars): width = `max(120, label_length * 8)`
- Add `whiteSpace=wrap` to the style so text wraps inside the box instead of overflowing
- Default style for a readable box: `rounded=1;whiteSpace=wrap;arcSize=10;`

**Edge labels:**

- Never place an edge label directly on the line — use `x` and `y` offsets in `mxGeometry` to push it clear
- Edge label geometry: `<mxGeometry x="0" y="-10" relative="1" as="geometry"/>` (negative y lifts label above the line)
- Keep edge labels short (≤ 4 words). If the label is longer, shorten it

**Spacing between nodes:**

- Horizontal gap between sibling nodes: minimum `40px`
- Vertical gap between rows: minimum `60px`
- Do not place nodes at the same x/y coordinates — every node must have a unique position

**Container / subgraph padding:**

- Inner padding: at least `20px` on all sides so child nodes do not touch the container border
- Container width/height must fully enclose all children plus padding

---

## Diagram-Type Layout Templates

Apply the matching template before generating XML. These fix the most common layout problems per type.

### Architecture / System Context

- Layout: top-down or left-right grid. Services in row, databases below, external actors on edges.
- Node size: `width=160, height=60` minimum.
- Edge routing: `edgeStyle=orthogonalEdgeStyle` — right-angle routing, no diagonal arrows.
- Arrow direction: always explicit (`exitX`, `exitY`, `entryX`, `entryY`) — never auto-route.
- Group related services in container with `20px` inner padding.
- Min horizontal gap: `60px`. Vertical gap: `80px`.
- Edge labels: direction only ("calls", "publishes") — max 2 words.

```xml

<mxCell id="svc1" value="Service Name"
        style="rounded=1;whiteSpace=wrap;arcSize=10;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
    <mxGeometry x="80" y="80" width="160" height="60" as="geometry"/>
</mxCell>
<mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1"
        source="svc1" target="svc2" parent="1">
<mxGeometry relative="1" as="geometry"/>
</mxCell>
```

### Sequence Diagram

- Layout: participants left-to-right as columns. Messages as horizontal arrows.
- Participant box: `width=120, height=40`.
- Lifeline: dashed vertical line below each participant, `height=400` minimum.
- Message arrows: horizontal only — never diagonal. `edgeStyle=elbowEdgeStyle;elbow=vertical`.
- Message label: `y=-12` offset above arrow line.
- Vertical spacing between messages: min `50px`.
- Return arrows: `dashed=1`.

```xml

<mxCell id="p1" value="Client" style="shape=mxgraph.sequence.participant;whiteSpace=wrap;" vertex="1" parent="1">
    <mxGeometry x="60" y="20" width="120" height="40" as="geometry"/>
</mxCell>
<mxCell id="m1" value="request()" style="edgeStyle=elbowEdgeStyle;elbow=vertical;exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
        edge="1" source="p1" target="p2" parent="1">
<mxGeometry x="0" y="-12" relative="1" as="geometry"/>
</mxCell>
```

### Data Flow / Pipeline

- Layout: left-to-right. Each stage a box, arrows between stages.
- Node size: `width=140, height=60`. Consistent shape per type (process=rect, store=cylinder, decision=diamond).
- Edge routing: `edgeStyle=orthogonalEdgeStyle`. Arrows horizontal where possible.
- Decision diamonds: `shape=rhombus;width=80;height=80`. Yes/No labels on outgoing edges.
- Min horizontal gap: `60px`. Branch paths offset vertically `100px` min — no path overlaps.

```xml

<mxCell id="s1" value="Ingest" style="rounded=1;whiteSpace=wrap;fillColor=#d5e8d4;strokeColor=#82b366;" vertex="1"
        parent="1">
    <mxGeometry x="40" y="100" width="140" height="60" as="geometry"/>
</mxCell>
<mxCell id="d1" value="Valid?" style="rhombus;whiteSpace=wrap;" vertex="1" parent="1">
<mxGeometry x="240" y="90" width="80" height="80" as="geometry"/>
</mxCell>
```

### ER Diagram

- Layout: entities as rectangles with attribute rows. Relationships as lines between entities.
- Entity header: `fillColor=#dae8fc`. Attribute rows below in same container.
- Relationship line: plain line for associations, crow’s foot for cardinality.
- Min gap: `80px` horizontal, `60px` vertical. Never overlap entity boxes.
- FK attributes: `[FK]` suffix in label.

### General Rules (all types)

1. No overlapping nodes — every node unique x/y
2. No diagonal arrows — `edgeStyle=orthogonalEdgeStyle` or `elbowEdgeStyle`
3. Explicit entry/exit points — always set `exitX/Y` + `entryX/Y` on edges
4. Text fits in box — label >20 chars → increase width or `whiteSpace=wrap`
5. Consistent node sizes — same type = same size throughout
6. Edge labels above line — `y=-10` to `-15` offset, never on the line
7. Containers fully enclose children — width/height = max child extent + 40px padding
