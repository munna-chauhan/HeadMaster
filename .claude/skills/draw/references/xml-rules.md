# XML Diagram Rules (draw.io mxGraphModel)

## Structure

```xml
<mxGraphModel adaptiveColors="auto">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
  </root>
</mxGraphModel>
```

## Grid Layout

* Column x = `col_index × 180 + 40`
* Row y = `row_index × 120 + 40`
* Sizes: rectangles `140×60` | diamonds `140×80` | cylinders `100×70` | circles `60×60`
* Minimum **40px spacing** between nodes, **80px** between layers
* Label > 20 chars → width `180`
* Group related components in same row/column
* Single flow direction (LR or TB, never mixed)

## Containers

Use for: systems, domains, bounded contexts.
* Minimum 40px internal padding
* Same phase → same column | same layer → same row
* Decision nodes centered between branches | end nodes horizontally aligned

## Node Styling (MANDATORY — every node)

`fillColor` + `strokeColor` + `fontColor=#000000` + `whiteSpace=wrap` + `align=center` + `verticalAlign=middle` + `html=1`

Hierarchy: core systems `strokeWidth=2` | standard `strokeWidth=1` | optional/external → dashed

## Edges (MANDATORY)

`endArrow=block` + `rounded=1` + `edgeStyle=orthogonalEdgeStyle` + `<mxGeometry relative="1" as="geometry" />`

Semantic: sync → solid `#333333` | async → dashed `#b85450` | event → dotted `#d79b00`

No overlapping edges. No crossing lines. No mixed flow directions.

## General

* Always `html=1` | Never XML comments | Escape: `&amp;` `&lt;` `&gt;` `&quot;`
* No waypoints unless absolutely necessary

Full reference: https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md

## Enterprise Colors

| Component | fillColor | strokeColor |
|-----------|-----------|-------------|
| service | `#dae8fc` | `#6c8ebf` |
| database | `#fff2cc` | `#d6b656` |
| queue | `#f8cecc` | `#b85450` |
| gateway | `#d5e8d4` | `#82b366` |
| external | `#e1d5e7` | `#9673a6` |
| cache | `#ffe6cc` | `#d79b00` |
| storage | `#f5f5f5` | `#666666` |
| lambda | `#fad7ac` | `#b46504` |
| cdn/actor | `#f5f5f5` | `#333333` |
