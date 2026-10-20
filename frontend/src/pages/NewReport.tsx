import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type AoiPreview, type Period } from '../api'
import { SiteMap } from '../components/SiteMap'

const ACCEPT = '.geojson,.json,.kml,.gpkg,.zip'

export function NewReport() {
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)

  const [client, setClient] = useState('')
  const [siteName, setSiteName] = useState('')
  const [requestedBy, setRequestedBy] = useState('')
  const [baseline, setBaseline] = useState<Period>({ start: '', end: '' })
  const [current, setCurrent] = useState<Period>({ start: '', end: '' })

  const [fileName, setFileName] = useState<string | null>(null)
  const [preview, setPreview] = useState<AoiPreview | null>(null)
  const [checking, setChecking] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    api
      .defaults()
      .then((d) => {
        setBaseline(d.periods.baseline)
        setCurrent(d.periods.current)
      })
      .catch(() => undefined)
  }, [])

  async function handleFile(file: File | undefined) {
    if (!file) return
    setFileName(file.name)
    setPreview(null)
    setUploadError(null)
    setChecking(true)
    try {
      setPreview(await api.previewAoi(file))
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e))
    } finally {
      setChecking(false)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    void handleFile(e.dataTransfer.files[0])
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!preview) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const { id } = await api.createProject({
        client: client.trim(),
        site_name: siteName.trim(),
        geometry: preview.geometry,
        baseline_period: baseline,
        current_period: current,
        requested_by: requestedBy.trim() || undefined,
      })
      navigate(`/reports/${id}`)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  const canSubmit = Boolean(preview && client.trim() && siteName.trim() && !submitting)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>New screening report</h1>
          <p>Tell us about the site and upload its boundary. The report is ready in about two minutes.</p>
        </div>
      </div>

      <form className="grid-2" onSubmit={onSubmit}>
        <div className="stack">
          <section className="card">
            <h2>1. Site details</h2>
            <div className="field">
              <label htmlFor="site">Site name</label>
              <input
                id="site"
                type="text"
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
                placeholder="e.g. Plot 42, Ameenpur"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="client">Client</label>
              <input
                id="client"
                type="text"
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="e.g. Sunrise Developers Pvt Ltd"
                required
              />
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="by">Your name (optional)</label>
              <input id="by" type="text" value={requestedBy} onChange={(e) => setRequestedBy(e.target.value)} />
            </div>
          </section>

          <section className="card">
            <h2>2. Site boundary</h2>
            <div
              className={`dropzone${dragOver ? ' over' : ''}`}
              role="button"
              tabIndex={0}
              onClick={() => fileInput.current?.click()}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInput.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
            >
              <div>
                <strong>Click to choose a file</strong> or drag it here
              </div>
              <div className="muted small">KML (Google Earth), GeoJSON, GeoPackage or zipped Shapefile</div>
              {fileName && <div className="small" style={{ marginTop: 8 }}>{fileName}</div>}
              <input
                ref={fileInput}
                type="file"
                accept={ACCEPT}
                hidden
                onChange={(e) => void handleFile(e.target.files?.[0])}
              />
            </div>
            {checking && <p className="muted">Checking the boundary…</p>}
            {uploadError && (
              <div className="alert error" style={{ marginTop: 12 }}>
                {uploadError}
              </div>
            )}
          </section>

          <section className="card">
            <details>
              <summary>3. Comparison dates (optional)</summary>
              <p className="muted small" style={{ marginTop: 0 }}>
                Satellite images from these two periods are compared to detect vegetation and water
                change. The defaults use the dry season (October–March), which has the fewest clouds.
              </p>
              <div className="row">
                <div className="field">
                  <label htmlFor="b0">Earlier period from</label>
                  <input id="b0" type="date" value={baseline.start} onChange={(e) => setBaseline({ ...baseline, start: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="b1">to</label>
                  <input id="b1" type="date" value={baseline.end} onChange={(e) => setBaseline({ ...baseline, end: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="c0">Recent period from</label>
                  <input id="c0" type="date" value={current.start} onChange={(e) => setCurrent({ ...current, start: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="c1">to</label>
                  <input id="c1" type="date" value={current.end} onChange={(e) => setCurrent({ ...current, end: e.target.value })} />
                </div>
              </div>
            </details>
          </section>
        </div>

        <aside className="stack">
          <section className="card">
            <h2>Preview</h2>
            {preview ? (
              <>
                <SiteMap geometry={preview.geometry} />
                <div className="kpis" style={{ marginTop: 12 }}>
                  <div className="kpi">
                    <div className="value">{preview.area_ha.toFixed(2)} ha</div>
                    <div className="label">{(preview.area_ha * 2.47105).toFixed(1)} acres</div>
                  </div>
                  <div className="kpi">
                    <div className="value">{(preview.perimeter_m / 1000).toFixed(2)} km</div>
                    <div className="label">Boundary length</div>
                  </div>
                </div>
                {preview.warnings.map((w) => (
                  <div key={w} className="alert warn small" style={{ marginTop: 10 }}>
                    {w}
                  </div>
                ))}
              </>
            ) : (
              <p className="muted">Upload a boundary to see the site on a map.</p>
            )}
          </section>

          {submitError && <div className="alert error">{submitError}</div>}
          <button type="submit" className="btn primary" disabled={!canSubmit} style={{ justifyContent: 'center' }}>
            {submitting ? 'Submitting…' : 'Create report'}
          </button>
          {!canSubmit && !submitting && (
            <p className="muted small" style={{ margin: 0, textAlign: 'center' }}>
              Fill in the site name and client, and upload a boundary.
            </p>
          )}
        </aside>
      </form>
    </div>
  )
}
