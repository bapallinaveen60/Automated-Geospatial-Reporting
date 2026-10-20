import { useState, type FormEvent } from 'react'
import { api, formatDate, type Disposition, type ProjectDetail, type ReviewSubmission } from '../api'
import { Banner, SeverityLabel } from './ui'

const DISPOSITIONS: { key: Disposition; label: string }[] = [
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'site_visit', label: 'Site visit required' },
  { key: 'dismissed', label: 'Not applicable' },
]
const DISPOSITION_LABEL = Object.fromEntries(DISPOSITIONS.map((d) => [d.key, d.label])) as Record<Disposition, string>

// Remember the reviewer between sessions on this device.
const REVIEWER_KEY = 'geovision.reviewer'
function savedReviewer(): ReviewSubmission['reviewer'] {
  try {
    const raw = localStorage.getItem(REVIEWER_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    /* storage unavailable */
  }
  return { name: '', qualification: '', registration_no: '', organisation: '' }
}

export function ReviewPanel({ project, onDone }: { project: ProjectDetail; onDone: () => void }) {
  const flags = (project.metrics?.flags ?? []).filter((f) => f.severity !== 'info')
  const [reviews, setReviews] = useState<ReviewSubmission['flag_reviews']>({})
  const [reviewer, setReviewer] = useState(savedReviewer)
  const [comments, setComments] = useState('')
  const [busy, setBusy] = useState<null | 'approved' | 'changes_requested'>(null)
  const [error, setError] = useState<string | null>(null)

  if (project.review) {
    const r = project.review
    return (
      <div className={`approved-box${r.decision === 'approved' ? '' : ' changes'}`}>
        <h2>{r.decision === 'approved' ? 'Approved for issue' : 'Changes requested'}</h2>
        <p className="small muted" style={{ marginTop: 4 }}>
          {r.reviewer.name} · {r.reviewer.qualification} · Reg. {r.reviewer.registration_no} ·{' '}
          {formatDate(r.decided_at)}
        </p>
        {r.comments && <p style={{ marginTop: 10 }}>{r.comments}</p>}
        {Object.keys(r.flag_reviews).length > 0 && (
          <ul className="small" style={{ margin: '10px 0 0', paddingLeft: 18 }}>
            {flags.map((f) => {
              const fr = r.flag_reviews[f.rule_id]
              return fr ? (
                <li key={f.rule_id}>
                  <strong>{DISPOSITION_LABEL[fr.disposition]}</strong> — {f.message}
                  {fr.note && <span className="muted"> ({fr.note})</span>}
                </li>
              ) : null
            })}
          </ul>
        )}
      </div>
    )
  }

  const missing = flags.filter((f) => !reviews[f.rule_id]).length
  const needsReason = flags.some((f) => reviews[f.rule_id]?.disposition === 'dismissed' && !reviews[f.rule_id].note.trim())
  const identityOk = reviewer.name.trim() && reviewer.qualification.trim() && reviewer.registration_no.trim()

  function setDisposition(ruleId: string, disposition: Disposition) {
    setReviews((r) => ({ ...r, [ruleId]: { disposition, note: r[ruleId]?.note ?? '' } }))
  }
  function setNote(ruleId: string, note: string) {
    setReviews((r) => ({ ...r, [ruleId]: { disposition: r[ruleId]?.disposition ?? 'confirmed', note } }))
  }

  async function submit(decision: 'approved' | 'changes_requested', e?: FormEvent) {
    e?.preventDefault()
    setBusy(decision)
    setError(null)
    try {
      try {
        localStorage.setItem(REVIEWER_KEY, JSON.stringify(reviewer))
      } catch {
        /* ignore */
      }
      await api.review(project.id, {
        decision,
        reviewer: { ...reviewer, organisation: reviewer.organisation?.trim() || null },
        comments,
        flag_reviews: reviews,
      })
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <form onSubmit={(e) => void submit('approved', e)}>
      <div className="section">
        <h2>Findings</h2>
        <p className="small subtle" style={{ marginBottom: 10 }}>
          Record a disposition for each finding. It is printed beside the finding in the issued report.
        </p>
        <div className="panel">
          {flags.length === 0 && <div className="panel-body subtle">No findings to review.</div>}
          {flags.map((f) => {
            const r = reviews[f.rule_id]
            return (
              <div key={f.rule_id} className="review-flag">
                <SeverityLabel severity={f.severity} />
                <div style={{ marginTop: 4 }}>{f.message}</div>
                {f.regulation && <div className="small subtle">{f.regulation}</div>}
                <div className="choice" role="radiogroup" aria-label="Disposition">
                  {DISPOSITIONS.map((d) => (
                    <button
                      key={d.key}
                      type="button"
                      role="radio"
                      aria-checked={r?.disposition === d.key}
                      className={r?.disposition === d.key ? 'on' : ''}
                      onClick={() => setDisposition(f.rule_id, d.key)}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
                <input
                  className="input"
                  placeholder={r?.disposition === 'dismissed' ? 'Justification (required)' : 'Note (optional)'}
                  value={r?.note ?? ''}
                  onChange={(e) => setNote(f.rule_id, e.target.value)}
                />
              </div>
            )
          })}
        </div>
      </div>

      <div className="section">
        <h2>Sign-off</h2>
        <div className="panel panel-body">
          <div className="grid-2">
            <div className="field">
              <label htmlFor="rv-name">Reviewer name</label>
              <input id="rv-name" className="input" value={reviewer.name} onChange={(e) => setReviewer({ ...reviewer, name: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="rv-org">Organisation</label>
              <input id="rv-org" className="input" value={reviewer.organisation ?? ''} onChange={(e) => setReviewer({ ...reviewer, organisation: e.target.value })} placeholder="Optional" />
            </div>
            <div className="field">
              <label htmlFor="rv-q">Qualification</label>
              <input id="rv-q" className="input" value={reviewer.qualification} onChange={(e) => setReviewer({ ...reviewer, qualification: e.target.value })} placeholder="e.g. QCI-NABET accredited EIA Coordinator" />
            </div>
            <div className="field">
              <label htmlFor="rv-reg">Registration number</label>
              <input id="rv-reg" className="input" value={reviewer.registration_no} onChange={(e) => setReviewer({ ...reviewer, registration_no: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="rv-c">Comments</label>
            <textarea id="rv-c" className="input" value={comments} onChange={(e) => setComments(e.target.value)} placeholder="Printed in the issued report" />
          </div>
        </div>
      </div>

      {error && <Banner tone="error">{error}</Banner>}
      <div className="form-footer" style={{ justifyContent: 'space-between' }}>
        <span className="small subtle">
          {missing > 0
            ? `${missing} finding${missing > 1 ? 's' : ''} without a disposition`
            : needsReason
              ? 'Add a justification for findings marked not applicable'
              : !identityOk
                ? 'Enter your name, qualification and registration number'
                : 'Approving issues the final report without the draft watermark.'}
        </span>
        <div className="actions">
          <button type="button" className="btn danger" disabled={!identityOk || busy !== null} onClick={() => void submit('changes_requested')}>
            {busy === 'changes_requested' ? 'Saving…' : 'Request changes'}
          </button>
          <button type="submit" className="btn primary" disabled={!identityOk || missing > 0 || needsReason || busy !== null}>
            {busy === 'approved' ? 'Issuing report…' : 'Approve and issue'}
          </button>
        </div>
      </div>
    </form>
  )
}
