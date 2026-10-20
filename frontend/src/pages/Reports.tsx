import { Link } from 'react-router-dom'
import { api, formatDate, isActive, type ProjectSummary } from '../api'
import { ProgressBar, StatusBadge } from '../components/StatusBadge'
import { usePolling } from '../usePolling'

const anyActive = (list: ProjectSummary[]) => list.some((p) => isActive(p.status.state))

export function Reports() {
  const { data, error } = usePolling(api.projects, anyActive)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Site screening reports</h1>
          <p>Every site you have submitted, with its progress and findings.</p>
        </div>
        <Link to="/new" className="btn primary">
          + New report
        </Link>
      </div>

      {error && <div className="alert error">Could not load reports: {error}</div>}
      {data && data.some((p) => !p.status.engine_online) && (
        <div className="alert warn" style={{ marginBottom: 16 }}>
          The processing engine is offline, so new requests will wait until it is started.
        </div>
      )}

      {data && data.length === 0 && (
        <div className="card empty">
          <h2>No reports yet</h2>
          <p>Upload a site boundary to get an automated environmental screening report.</p>
          <Link to="/new" className="btn primary">
            Create your first report
          </Link>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="card report-list">
          {data.map((p) => (
            <Link key={p.id} to={`/reports/${p.id}`} className="report-row">
              <div>
                <div className="title">{p.site_name}</div>
                <div className="muted small">
                  {p.client} · submitted {formatDate(p.submitted)}
                </div>
              </div>
              <div>
                <div className="small" style={{ marginBottom: 6 }}>
                  {p.status.label}
                </div>
                {isActive(p.status.state) && (
                  <ProgressBar completed={p.status.completed} total={p.status.total} />
                )}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {p.flags.critical > 0 && <span className="badge critical">{p.flags.critical} critical</span>}
                {p.flags.warning > 0 && <span className="badge warning">{p.flags.warning} to check</span>}
                {p.status.state === 'ready' && p.flags.critical + p.flags.warning === 0 && (
                  <span className="badge ready">No issues found</span>
                )}
              </div>
              <StatusBadge state={p.status.state} />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
