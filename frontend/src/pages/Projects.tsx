import { Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, formatRelative, type ProjectSummary, type Stage } from '../api'
import { Banner, StageStatus } from '../components/ui'
import { usePolling } from '../usePolling'

type Filter = 'all' | Stage
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'needs_review', label: 'Needs review' },
  { key: 'processing', label: 'Processing' },
  { key: 'approved', label: 'Approved' },
  { key: 'failed', label: 'Failed' },
]

const anyProcessing = (list: ProjectSummary[]) => list.some((p) => p.stage === 'processing')

function Findings({ p }: { p: ProjectSummary }) {
  if (p.stage === 'processing' || p.stage === 'failed') return <span className="subtle">—</span>
  const { critical, warning } = p.flags
  if (critical + warning === 0) return <span className="subtle">None</span>
  return (
    <span className="num">
      {critical > 0 && <span className="sev critical">{critical} critical</span>}
      {critical > 0 && warning > 0 && <span className="subtle"> · </span>}
      {warning > 0 && <span className="sev warning">{warning} warning{warning > 1 ? 's' : ''}</span>}
    </span>
  )
}

export function Projects() {
  const navigate = useNavigate()
  const { data, error } = usePolling(api.projects, anyProcessing)
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: data?.length ?? 0 }
    for (const p of data ?? []) c[p.stage] = (c[p.stage] ?? 0) + 1
    return c
  }, [data])

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (data ?? []).filter(
      (p) =>
        (filter === 'all' || p.stage === filter) &&
        (!q || [p.site_name, p.client, p.location, p.id].some((v) => v?.toLowerCase().includes(q))),
    )
  }, [data, filter, query])

  return (
    <div className="content">
      <div className="page-header">
        <div>
          <h1>Projects</h1>
          <div className="meta">Environmental site screenings for your clients.</div>
        </div>
        <Link to="/new" className="btn primary">
          <Plus size={15} />
          New screening
        </Link>
      </div>

      {error && <Banner tone="error">Could not load projects. {error}</Banner>}
      {data?.some((p) => !p.status.engine_online) && (
        <Banner>The processing service is not running. Submitted screenings will start once it is available.</Banner>
      )}

      {data && data.length === 0 ? (
        <div className="empty">
          <h2>No projects yet</h2>
          <p>Upload a site boundary to produce a screening report for review.</p>
          <Link to="/new" className="btn primary">
            <Plus size={15} />
            New screening
          </Link>
        </div>
      ) : (
        <>
          <div className="toolbar">
            <div className="segmented" role="tablist">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  className={filter === f.key ? 'on' : ''}
                  onClick={() => setFilter(f.key)}
                  role="tab"
                  aria-selected={filter === f.key}
                >
                  {f.label}
                  <span className="n num">{counts[f.key] ?? 0}</span>
                </button>
              ))}
            </div>
            <label className="search">
              <Search size={14} />
              <input
                placeholder="Search site, client, district"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Site</th>
                  <th>Client</th>
                  <th>Location</th>
                  <th className="right">Area</th>
                  <th>Findings</th>
                  <th>Status</th>
                  <th className="right">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)}>
                    <td className="site">
                      <Link to={`/projects/${p.id}`} className="cell-title" onClick={(e) => e.stopPropagation()}>
                        {p.site_name}
                      </Link>
                      <div className="cell-sub mono">{p.id}</div>
                    </td>
                    <td>{p.client}</td>
                    <td className="muted">{p.location ?? '—'}</td>
                    <td className="right num">{p.area_ha != null ? `${p.area_ha.toFixed(1)} ha` : '—'}</td>
                    <td>
                      <Findings p={p} />
                    </td>
                    <td>
                      <StageStatus stage={p.stage} />
                      {p.stage === 'processing' && (
                        <div className="cell-sub num">
                          Step {Math.min(p.status.completed + 1, p.status.total)} of {p.status.total}
                        </div>
                      )}
                    </td>
                    <td className="right muted num" title={p.submitted}>
                      {formatRelative(p.submitted)}
                    </td>
                  </tr>
                ))}
                {data && rows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="subtle" style={{ textAlign: 'center', padding: 28, cursor: 'default' }}>
                      No projects match this view.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
