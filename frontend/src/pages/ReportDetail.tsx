import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDate, formatDistance, isActive, type ProjectDetail } from '../api'
import { SiteMap } from '../components/SiteMap'
import { ProgressBar, StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../usePolling'

const LAYER_NAMES: Record<string, string> = {
  protected_areas: 'Protected areas',
  wetlands_water: 'Water bodies / wetlands',
  forest: 'Forest',
  coastline: 'Coastline',
}
const SEVERITY_TEXT = { critical: 'Critical', warning: 'Check', info: 'Note' } as const
// ESA WorldCover colours, matching the map plates.
const LULC_COLOURS: Record<number, string> = {
  10: '#006400', 20: '#ffbb22', 30: '#ffff4c', 40: '#f096ff', 50: '#fa0000', 60: '#b4b4b4',
  70: '#f0f0f0', 80: '#0064c8', 90: '#0096a0', 95: '#00cf75', 100: '#fae6a0',
}
const STEP_ICON = { done: '✓', failed: '!', running: '', pending: '', skipped: '–' } as const

const stillWorking = (p: ProjectDetail) => isActive(p.status.state)

export function ReportDetail() {
  const { id = '' } = useParams()
  const load = useCallback(() => api.project(id), [id])
  const { data: p, error, refresh } = usePolling(load, stillWorking, 4000)
  const [retrying, setRetrying] = useState(false)

  async function retry() {
    setRetrying(true)
    try {
      await api.rerun(id)
      await refresh()
    } finally {
      setRetrying(false)
    }
  }

  if (error && !p) return <div className="page"><div className="alert error">{error}</div></div>
  if (!p) return <div className="page muted">Loading…</div>

  const m = p.metrics
  const where = m ? [m.site.locality, m.site.district, m.site.state].filter(Boolean).join(', ') : ''
  const ndvi = m?.indices.ndvi
  const loss = m?.change.find((c) => c.index === 'ndvi')
  const nearestWater = m?.proximity.find((x) => x.layer === 'wetlands_water')

  return (
    <div className="page">
      <Link to="/" className="small">← All reports</Link>
      <div className="page-head" style={{ marginTop: 8 }}>
        <div>
          <h1>{p.site_name}</h1>
          <p>
            {p.client}
            {where && ` · ${where}`} · submitted {formatDate(p.submitted)}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <StatusBadge state={p.status.state} />
          {p.report_url && (
            <a className="btn primary" href={p.report_url} target="_blank" rel="noreferrer">
              Download PDF report
            </a>
          )}
        </div>
      </div>

      <div className="grid-2">
        <div className="stack">
          {p.status.state !== 'ready' && (
            <section className="card">
              <h2>{p.status.label}</h2>
              <ProgressBar completed={p.status.completed} total={p.status.total} />
              <p className="muted small">
                Step {Math.min(p.status.completed + 1, p.status.total)} of {p.status.total}. This page
                updates by itself.
              </p>
              {!p.status.engine_online && (
                <div className="alert warn small">
                  The processing engine is offline. Your request is saved and will start once it is running.
                </div>
              )}
              {p.status.error && (
                <div className="alert error" style={{ marginBottom: 12 }}>
                  {p.status.error}
                </div>
              )}
              <ol className="steps">
                {p.status.steps.map((s) => (
                  <li key={s.key} className={s.status}>
                    <span className="step-icon">{STEP_ICON[s.status]}</span>
                    {s.label}
                  </li>
                ))}
              </ol>
              {p.status.state === 'failed' && (
                <button className="btn" style={{ marginTop: 16 }} onClick={() => void retry()} disabled={retrying}>
                  {retrying ? 'Restarting…' : 'Try again'}
                </button>
              )}
            </section>
          )}

          {p.summary.length > 0 && (
            <section className="card">
              <h2>Summary</h2>
              <p style={{ margin: 0 }}>{p.summary.join(' ')}</p>
            </section>
          )}

          {m && (
            <section className="card">
              <h2>Findings to review</h2>
              {m.flags.length === 0 && <p className="muted">No screening rule was triggered.</p>}
              {m.flags.map((f) => (
                <div key={f.rule_id} className="flag">
                  <span className={`badge ${f.severity}`}>{SEVERITY_TEXT[f.severity]}</span>
                  <div>
                    <div>{f.message}</div>
                    {f.regulation && <div className="muted small">{f.regulation}</div>}
                  </div>
                </div>
              ))}
            </section>
          )}

          {p.plates.length > 0 && (
            <section className="card">
              <h2>Maps</h2>
              <div className="plates">
                {p.plates.map((pl) => (
                  <a key={pl.url} className="plate" href={pl.url} target="_blank" rel="noreferrer">
                    <img src={pl.url} alt={pl.title} loading="lazy" />
                    <div>{pl.title}</div>
                  </a>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="stack">
          <section className="card">
            <h2>Site</h2>
            {p.geometry && <SiteMap geometry={p.geometry} />}
            {m && (
              <div className="kpis" style={{ marginTop: 12 }}>
                <div className="kpi">
                  <div className="value">{m.site.area_ha.toFixed(1)} ha</div>
                  <div className="label">Site area</div>
                </div>
                {ndvi?.median != null && (
                  <div className="kpi">
                    <div className="value">{ndvi.median.toFixed(2)}</div>
                    <div className="label">Vegetation index (NDVI)</div>
                  </div>
                )}
                {loss && (
                  <div className="kpi">
                    <div className="value">{loss.loss_ha.toFixed(1)} ha</div>
                    <div className="label">Vegetation lost</div>
                  </div>
                )}
                {nearestWater?.distance_m != null && (
                  <div className="kpi">
                    <div className="value">{formatDistance(nearestWater.distance_m)}</div>
                    <div className="label">Nearest water body</div>
                  </div>
                )}
              </div>
            )}
          </section>

          {m && m.lulc.length > 0 && (
            <section className="card">
              <h2>Land cover</h2>
              <div className="bars">
                {m.lulc.map((c) => (
                  <div key={c.code} className="bar-row">
                    <span>{c.label}</span>
                    <div className="bar-track">
                      <div style={{ width: `${c.percent}%`, background: LULC_COLOURS[c.code] ?? '#98a2b3' }} />
                    </div>
                    <span className="muted">{c.percent.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {m && (
            <section className="card">
              <h2>Nearby sensitive areas</h2>
              {m.proximity.map((x) => (
                <div key={x.layer} className="bar-row" style={{ gridTemplateColumns: '1fr auto' }}>
                  <span>{LAYER_NAMES[x.layer] ?? x.layer}</span>
                  <span className={x.distance_m == null ? 'muted' : ''}>
                    {x.distance_m == null
                      ? `none within ${formatDistance(x.search_radius_m)}`
                      : x.overlap_ha > 0
                        ? `overlaps site (${x.overlap_ha.toFixed(2)} ha)`
                        : formatDistance(x.distance_m)}
                  </span>
                </div>
              ))}
            </section>
          )}

          <section className="card small muted">
            Compared periods: {p.periods.baseline.start} → {p.periods.baseline.end} and{' '}
            {p.periods.current.start} → {p.periods.current.end}. This is an automated desktop
            screening; findings must be reviewed by a qualified professional before submission.
          </section>
        </aside>
      </div>
    </div>
  )
}
