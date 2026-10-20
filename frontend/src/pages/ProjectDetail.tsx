import { CheckCircle2, Circle, Download, FileCheck2, Loader2, RotateCcw, XCircle } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatDistance, formatRelative, type ProjectDetail as Detail } from '../api'
import { ReviewPanel } from '../components/ReviewPanel'
import { SiteMap } from '../components/SiteMap'
import { Banner, Progress, Prop, SeverityLabel, StageStatus } from '../components/ui'
import { usePolling } from '../usePolling'

type Tab = 'overview' | 'maps' | 'review' | 'sources'

const LAYER_NAMES: Record<string, string> = {
  protected_areas: 'Protected areas',
  wetlands_water: 'Water bodies and wetlands',
  forest: 'Forest',
  coastline: 'Coastline',
}
const STEP_NAMES: Record<string, string> = {
  aoi_validated: 'Site boundary',
  site_location: 'Administrative location',
  s2_composite_baseline: 'Sentinel-2 imagery, baseline',
  s2_composite_current: 'Sentinel-2 imagery, current',
  lulc_worldcover: 'Land cover',
  proximity: 'Sensitive receptors',
}
const EVENT_TEXT: Record<string, string> = {
  approved: 'Approved and issued',
  changes_requested: 'Requested changes',
}
const LULC_COLOURS: Record<number, string> = {
  10: '#006400', 20: '#ffbb22', 30: '#ffff4c', 40: '#f096ff', 50: '#fa0000', 60: '#b4b4b4',
  70: '#f0f0f0', 80: '#0064c8', 90: '#0096a0', 95: '#00cf75', 100: '#fae6a0',
}

const processing = (p: Detail) => p.stage === 'processing'

function StepIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckCircle2 size={15} />
  if (status === 'running') return <Loader2 size={15} />
  if (status === 'failed') return <XCircle size={15} />
  return <Circle size={15} />
}

export function ProjectDetail() {
  const { id = '' } = useParams()
  const load = useCallback(() => api.project(id), [id])
  const { data: p, error, refresh } = usePolling(load, processing, 4000)
  const [tab, setTab] = useState<Tab>('overview')
  const [zoom, setZoom] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (p?.stage === 'needs_review' && tab === 'overview' && window.location.hash === '#review') setTab('review')
  }, [p?.stage, tab])

  if (error && !p) return <div className="content"><Banner tone="error">{error}</Banner></div>
  if (!p) return <div className="content subtle">Loading…</div>

  const m = p.metrics
  const location = m ? [m.site.locality, m.site.district, m.site.state].filter(Boolean).join(', ') : null
  const ndvi = m?.indices.ndvi
  const change = m?.change.find((c) => c.index === 'ndvi')
  const water = m?.proximity.find((x) => x.layer === 'wetlands_water')
  const flags = m?.flags.filter((f) => f.severity !== 'info') ?? []

  async function retry() {
    setRetrying(true)
    try {
      await api.rerun(id)
      await refresh()
    } finally {
      setRetrying(false)
    }
  }

  const tabs: { key: Tab; label: string; n?: number }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'maps', label: 'Maps', n: p.plates.length },
    { key: 'review', label: 'Review', n: p.stage === 'needs_review' ? flags.length : undefined },
    { key: 'sources', label: 'Data sources' },
  ]

  return (
    <div className="content">
      <div className="crumbs">
        <Link to="/">Projects</Link>
        <span>/</span>
        <span>{p.site_name}</span>
      </div>

      <div className="page-header">
        <div>
          <h1>{p.site_name}</h1>
          <div className="meta">
            <StageStatus stage={p.stage} />
            <span>{p.client}</span>
            {location && <span>{location}</span>}
            <span title={formatDate(p.submitted)}>Submitted {formatRelative(p.submitted)}</span>
          </div>
        </div>
        <div className="actions">
          {p.report_url && !p.final_report_url && (
            <a className="btn" href={p.report_url} target="_blank" rel="noreferrer">
              <Download size={15} />
              Draft PDF
            </a>
          )}
          {p.final_report_url && (
            <a className="btn primary" href={p.final_report_url} target="_blank" rel="noreferrer">
              <FileCheck2 size={15} />
              Issued report
            </a>
          )}
          {p.stage === 'needs_review' && (
            <button className="btn primary" onClick={() => setTab('review')}>
              Review
            </button>
          )}
        </div>
      </div>

      {(p.stage === 'processing' || p.stage === 'failed') && (
        <div className="panel" style={{ marginBottom: 24 }}>
          <div className="panel-head">
            <h2>{p.status.label}</h2>
            <span className="small subtle num">
              {p.status.completed} of {p.status.total} steps
            </span>
          </div>
          <div className="panel-body">
            {p.stage === 'processing' && <Progress completed={p.status.completed} total={p.status.total} />}
            {!p.status.engine_online && (
              <div style={{ marginTop: 12 }}>
                <Banner>The processing service is not running. This screening will start when it is available.</Banner>
              </div>
            )}
            {p.status.error && (
              <div style={{ marginTop: 12 }}>
                <Banner tone="error">{p.status.error}</Banner>
              </div>
            )}
            <ol className="steps" style={{ marginTop: 12 }}>
              {p.status.steps.map((s) => (
                <li key={s.key} className={s.status}>
                  <StepIcon status={s.status} />
                  {s.label}
                </li>
              ))}
            </ol>
            {p.stage === 'failed' && (
              <button className="btn" style={{ marginTop: 12 }} onClick={() => void retry()} disabled={retrying}>
                <RotateCcw size={14} />
                {retrying ? 'Restarting…' : 'Run again'}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? 'on' : ''} onClick={() => setTab(t.key)}>
            {t.label}
            {t.n ? <span className="n num">{t.n}</span> : null}
          </button>
        ))}
      </div>

      <div className="layout">
        <div>
          {tab === 'overview' && (
            <>
              {!m && <p className="subtle">Results appear here when processing finishes.</p>}
              {m && (
                <>
                  <div className="stats section">
                    <div className="stat">
                      <div className="label">Site area</div>
                      <div className="value num">{m.site.area_ha.toFixed(1)} ha</div>
                      <div className="hint num">{(m.site.area_ha * 2.47105).toFixed(1)} acres</div>
                    </div>
                    <div className="stat">
                      <div className="label">Vegetation index</div>
                      <div className="value num">{ndvi?.median != null ? ndvi.median.toFixed(2) : '—'}</div>
                      <div className="hint">Median NDVI, current</div>
                    </div>
                    <div className="stat">
                      <div className="label">Vegetation loss</div>
                      <div className="value num">{change ? `${change.loss_ha.toFixed(1)} ha` : '—'}</div>
                      <div className="hint">Between periods</div>
                    </div>
                    <div className="stat">
                      <div className="label">Nearest water body</div>
                      <div className="value num">{water?.distance_m != null ? formatDistance(water.distance_m) : '—'}</div>
                      <div className="hint">From boundary</div>
                    </div>
                  </div>

                  <div className="section">
                    <h2>Summary</h2>
                    <p className="prose">{p.summary.join(' ')}</p>
                  </div>

                  <div className="section">
                    <h2>Findings</h2>
                    <div className="panel findings">
                      {flags.length === 0 && <div className="panel-body subtle">No screening rule was triggered.</div>}
                      {flags.map((f) => {
                        const r = p.review?.flag_reviews[f.rule_id]
                        return (
                          <div key={f.rule_id} className="row">
                            <SeverityLabel severity={f.severity} />
                            <div>
                              <div>{f.message}</div>
                              {f.regulation && <div className="small subtle">{f.regulation}</div>}
                            </div>
                            <span className="small muted">
                              {r ? { confirmed: 'Confirmed', dismissed: 'Not applicable', site_visit: 'Site visit' }[r.disposition] : ''}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>

                  <div className="section">
                    <h2>Land cover</h2>
                    {m.lulc.map((c) => (
                      <div key={c.code} className="bar">
                        <span>
                          <span className="swatch" style={{ background: LULC_COLOURS[c.code] ?? '#999' }} />
                          {c.label}
                        </span>
                        <div className="track">
                          <div style={{ width: `${c.percent}%`, background: 'var(--text-3)' }} />
                        </div>
                        <span className="num muted" style={{ textAlign: 'right' }}>
                          {c.percent.toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="section">
                    <h2>Sensitive receptors</h2>
                    <div className="table-wrap">
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Receptor</th>
                            <th>Nearest feature</th>
                            <th className="right">Distance</th>
                            <th className="right">Searched within</th>
                          </tr>
                        </thead>
                        <tbody>
                          {m.proximity.map((x) => (
                            <tr key={x.layer} style={{ cursor: 'default' }}>
                              <td>{LAYER_NAMES[x.layer] ?? x.layer}</td>
                              <td className="muted">{x.nearest_name ?? (x.distance_m == null ? 'None found' : 'Unnamed')}</td>
                              <td className="right num">
                                {x.distance_m == null ? '—' : x.overlap_ha > 0 ? `Overlaps (${x.overlap_ha.toFixed(2)} ha)` : formatDistance(x.distance_m)}
                              </td>
                              <td className="right num muted">{formatDistance(x.search_radius_m)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {p.warnings.length > 0 && (
                    <div className="section">
                      <h2>Processing notes</h2>
                      {p.warnings.map((w) => (
                        <Banner key={w}>{w}</Banner>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'maps' && (
            <>
              {p.plates.length === 0 && <p className="subtle">Maps appear here when processing finishes.</p>}
              <div className="plates">
                {p.plates.map((pl) => (
                  <button key={pl.url} className="plate" onClick={() => setZoom(pl.url)}>
                    <img src={pl.url} alt={pl.title} loading="lazy" />
                    <div className="caption">{pl.title}</div>
                  </button>
                ))}
              </div>
            </>
          )}

          {tab === 'review' &&
            (p.stage === 'processing' || p.stage === 'failed' ? (
              <p className="subtle">The report can be reviewed once processing has finished.</p>
            ) : (
              <>
                <ReviewPanel project={p} onDone={() => void refresh()} />
                {p.audit.length > 0 && (
                  <div className="section" style={{ marginTop: 28 }}>
                    <h2>History</h2>
                    <ul className="timeline">
                      {p.audit.map((e) => (
                        <li key={e.at}>
                          <span className="pin" />
                          <div>
                            <strong>{e.reviewer}</strong> {(EVENT_TEXT[e.event] ?? e.event).toLowerCase()}
                            <div className="small subtle">{formatDate(e.at)}</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ))}

          {tab === 'sources' && (
            <>
              <p className="prose small" style={{ marginBottom: 16 }}>
                Every figure in the report can be traced to the inputs below. The same list is printed in the
                report appendix.
              </p>
              {p.sources.length === 0 && <p className="subtle">Available when processing finishes.</p>}
              {p.sources.length > 0 && (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Step</th>
                        <th className="right">Inputs</th>
                        <th>Licence</th>
                        <th>Code version</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.sources.map((s) => (
                        <tr key={s.step} style={{ cursor: 'default' }} title={s.items.join('\n')}>
                          <td>{STEP_NAMES[s.step] ?? s.step}</td>
                          <td className="right num">{s.inputs}</td>
                          <td className="muted small">{s.licences.join('; ') || '—'}</td>
                          <td className="mono subtle">{s.code_version.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        <aside className="side">
          <div>
            <h3>Site</h3>
            {p.geometry && <SiteMap geometry={p.geometry} />}
          </div>
          <div>
            <h3>Details</h3>
            <dl className="props">
              <Prop label="Project ID">
                <span className="mono">{p.id}</span>
              </Prop>
              <Prop label="Client">{p.client}</Prop>
              <Prop label="Requested by">{p.requested_by}</Prop>
              <Prop label="Location">{location}</Prop>
              <Prop label="Baseline">
                <span className="num">
                  {formatDate(p.periods.baseline.start, false)} – {formatDate(p.periods.baseline.end, false)}
                </span>
              </Prop>
              <Prop label="Current">
                <span className="num">
                  {formatDate(p.periods.current.start, false)} – {formatDate(p.periods.current.end, false)}
                </span>
              </Prop>
              <Prop label="Reviewer">
                {p.review ? `${p.review.reviewer.name}, ${formatDate(p.review.decided_at, false)}` : null}
              </Prop>
            </dl>
          </div>
          <p className="small subtle">
            Automated desktop screening. Findings must be reviewed by a qualified professional before the report is
            issued.
          </p>
        </aside>
      </div>

      {zoom && (
        <div className="lightbox" onClick={() => setZoom(null)} role="dialog" aria-label="Map plate">
          <img src={zoom} alt="" />
        </div>
      )}
    </div>
  )
}
