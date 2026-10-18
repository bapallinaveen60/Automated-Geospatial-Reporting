// GeoVision — Environmental Site Screening Report template.
// Data comes from report.json written by geovision.reporting.compile.

#let data = json("report.json")
#let m = data.metrics
#let fmt(x, digits: 2) = if x == none { "—" } else { str(calc.round(x, digits: digits)) }
#let km(x) = if x == none { "Not within search radius" } else { fmt(x / 1000, digits: 2) + " km" }
#let sev-color = (critical: rgb("#b42318"), warning: rgb("#b54708"), info: rgb("#475467"))

#set document(
  title: data.module.title + " — " + data.project.site_name,
  author: "GeoVision",
)
#set page(
  paper: "a4",
  margin: (x: 2cm, y: 2.4cm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(8pt, fill: luma(110))
      [#data.module.title #h(1fr) #data.project.id]
    }
  },
  footer: context {
    set text(8pt, fill: luma(110))
    if data.draft [*DRAFT — NOT FOR SUBMISSION*]
    h(1fr)
    counter(page).display("1 of 1", both: true)
  },
  background: if data.draft {
    rotate(-45deg, text(72pt, weight: "bold", fill: rgb(180, 35, 24, 30))[DRAFT])
  },
)
#set text(font: ("Noto Sans", "DejaVu Sans", "Libertinus Serif"), size: 10pt)
#set heading(numbering: "1.")
#set table(stroke: 0.5pt + luma(190), inset: 6pt)
#show table.cell.where(y: 0): set text(weight: "bold")

// ---------- Cover ----------
#align(center + horizon)[
  #text(22pt, weight: "bold")[#data.module.title]
  #v(0.6em)
  #text(14pt)[#data.project.site_name]
  #v(1.5em)
  #table(
    columns: (auto, auto),
    align: left,
    [Project], [#data.project.id],
    [Client], [#data.project.client],
    [Baseline period], [#data.project.baseline_period.start to #data.project.baseline_period.end],
    [Current period], [#data.project.current_period.start to #data.project.current_period.end],
    [Generated], [#data.generated],
  )
]
#pagebreak()

#outline(depth: 2)
#pagebreak()

// ---------- Summary ----------
= Executive summary
The site covers *#fmt(m.site.area_ha) ha*
(centroid #fmt(m.site.centroid_lat, digits: 5)° N, #fmt(m.site.centroid_lon, digits: 5)° E).
#if m.flags.len() == 0 [
  No screening rules were triggered.
] else [
  #m.flags.len() screening item(s) require attention:
]

#if m.flags.len() > 0 {
  table(
    columns: (auto, 1fr, auto),
    [Severity], [Finding], [Reference],
    ..m.flags.map(f => (
      text(fill: sev-color.at(f.severity), weight: "bold", upper(f.severity)),
      f.message,
      if f.regulation == none { "—" } else { f.regulation },
    )).flatten(),
  )
}

= Site description
#table(
  columns: (auto, 1fr),
  [Area], [#fmt(m.site.area_ha) ha (#fmt(m.site.area_ha * 2.47105) acres)],
  [Perimeter], [#fmt(m.site.perimeter_m / 1000) km],
  [Analysis CRS], [#m.site.analysis_crs],
  [State / District],
  [#if m.site.state == none [—] else [#m.site.state] / #if m.site.district == none [—] else [#m.site.district]],
)

= Land use / land cover
#if m.lulc.len() == 0 [No land cover data available.] else {
  table(
    columns: (1fr, auto, auto),
    [Class], [Area (ha)], [Share (%)],
    ..m.lulc.map(c => (c.label, fmt(c.area_ha), fmt(c.percent, digits: 1))).flatten(),
  )
}

= Vegetation and water indices
#table(
  columns: (auto, auto, auto, auto, auto, auto),
  [Index], [Mean], [Median], [P10], [P90], [Valid px],
  ..m.indices.pairs().map(((k, s)) => (
    upper(k), fmt(s.mean), fmt(s.median), fmt(s.p10), fmt(s.p90),
    fmt(s.valid_fraction * 100, digits: 0) + "%",
  )).flatten(),
)

#if m.change.len() > 0 [
  == Change between periods
  #table(
    columns: (auto, auto, auto, auto, auto),
    [Index], [Threshold], [Loss (ha)], [Gain (ha)], [Mean change],
    ..m.change.map(c => (upper(c.index), fmt(c.threshold), fmt(c.loss_ha), fmt(c.gain_ha), fmt(c.net_change_mean, digits: 3))).flatten(),
  )
]

= Proximity to sensitive receptors
#table(
  columns: (auto, 1fr, auto, auto),
  [Layer], [Nearest feature], [Distance], [Overlap (ha)],
  ..m.proximity.map(p => (
    p.layer.replace("_", " "),
    if p.nearest_name == none { "—" } else { p.nearest_name },
    km(p.distance_m),
    fmt(p.overlap_ha),
  )).flatten(),
)

#if data.plates.len() > 0 [
  = Map plates
  #for p in data.plates [
    #figure(image(p.path, width: 100%), caption: p.title)
    #pagebreak(weak: true)
  ]
]

= Data sources and lineage
Every figure in this report is traceable to the inputs and code version below.
#if data.lineage.len() == 0 [Lineage records not attached.] else {
  for rec in data.lineage [
    *#rec.asset_key* — code #raw(rec.code_version), #rec.inputs.len() input(s)
    #list(..rec.inputs.slice(0, calc.min(rec.inputs.len(), 8)).map(i => [
      #i.kind: #raw(i.id)#if i.licence != none [ (#i.licence)]
    ]))
  ]
}

= Limitations
#data.module.disclaimer

= Review and approval
#if data.reviewer == none [
  #table(
    columns: (auto, 1fr),
    [Reviewed by], [],
    [Qualification / Reg. No.], [],
    [Date], [],
    [Signature], [#v(1.5cm)],
  )
] else [
  #table(
    columns: (auto, 1fr),
    [Reviewed by], [#data.reviewer.name],
    [Qualification / Reg. No.], [#data.reviewer.qualification],
    [Date], [#data.reviewer.date],
  )
]
