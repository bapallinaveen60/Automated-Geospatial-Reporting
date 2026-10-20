import { CheckCircle2, Upload } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type AoiPreview, type Period } from '../api'
import { SiteMap } from '../components/SiteMap'
import { Banner } from '../components/ui'

const ACCEPT = '.kml,.geojson,.json,.gpkg,.zip'

export function NewScreening() {
  const navigate = useNavigate()
  const fileInput = useRef<HTMLInputElement>(null)

  const [siteName, setSiteName] = useState('')
  const [client, setClient] = useState('')
  const [requestedBy, setRequestedBy] = useState('')
  const [baseline, setBaseline] = useState<Period>({ start: '', end: '' })
  const [current, setCurrent] = useState<Period>({ start: '', end: '' })

  const [fileName, setFileName] = useState<string | null>(null)
  const [preview, setPreview] = useState<AoiPreview | null>(null)
  const [checking, setChecking] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
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
    setFileError(null)
    setChecking(true)
    try {
      setPreview(await api.previewAoi(file))
    } catch (e) {
      setFileError(e instanceof Error ? e.message : String(e))
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
        site_name: siteName.trim(),
        client: client.trim(),
        geometry: preview.geometry,
        baseline_period: baseline,
        current_period: current,
        requested_by: requestedBy.trim() || undefined,
      })
      navigate(`/projects/${id}`)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err))
      setSubmitting(false)
    }
  }

  const ready = Boolean(preview && siteName.trim() && client.trim())

  return (
    <div className="content" style={{ maxWidth: 960 }}>
      <div className="crumbs">
        <Link to="/">Projects</Link>
        <span>/</span>
        <span>New screening</span>
      </div>
      <div className="page-header">
        <div>
          <h1>New screening</h1>
          <div className="meta">
            Results are usually ready in two to three minutes and are held as a draft until reviewed.
          </div>
        </div>
      </div>

      <form onSubmit={onSubmit}>
        <section className="form-section">
          <div className="intro">
            <h2>Project</h2>
            <p>Shown on the report cover and in the project list.</p>
          </div>
          <div>
            <div className="field">
              <label htmlFor="site">Site name</label>
              <input id="site" className="input" value={siteName} onChange={(e) => setSiteName(e.target.value)} placeholder="Survey No. 214, Ameenpur" required />
            </div>
            <div className="field">
              <label htmlFor="client">Client</label>
              <input id="client" className="input" value={client} onChange={(e) => setClient(e.target.value)} placeholder="Client organisation" required />
            </div>
            <div className="field">
              <label htmlFor="by">Requested by</label>
              <input id="by" className="input" value={requestedBy} onChange={(e) => setRequestedBy(e.target.value)} placeholder="Optional" />
            </div>
          </div>
        </section>

        <section className="form-section">
          <div className="intro">
            <h2>Site boundary</h2>
            <p>KML from Google Earth, GeoJSON, GeoPackage or a zipped Shapefile. Multiple parcels are merged.</p>
          </div>
          <div>
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
              <div className="icon">
                <Upload size={17} />
              </div>
              <div>
                <div style={{ color: 'var(--text)', fontWeight: 500 }}>
                  {fileName ? 'Replace boundary file' : 'Upload boundary file'}
                </div>
                <div className="small subtle">Drop a file here or click to browse</div>
              </div>
              <input ref={fileInput} type="file" accept={ACCEPT} hidden onChange={(e) => void handleFile(e.target.files?.[0])} />
            </div>

            {checking && <p className="small muted" style={{ marginTop: 10 }}>Validating {fileName}…</p>}
            {fileError && (
              <div style={{ marginTop: 10 }}>
                <Banner tone="error">{fileError}</Banner>
              </div>
            )}
            {preview && (
              <>
                <div className="file-ok">
                  <CheckCircle2 size={15} />
                  <span>
                    {fileName} · <span className="num">{preview.area_ha.toFixed(2)} ha</span> ·{' '}
                    <span className="num">{(preview.perimeter_m / 1000).toFixed(2)} km</span> perimeter
                  </span>
                </div>
                {preview.warnings.map((w) => (
                  <div key={w} style={{ marginTop: 8 }}>
                    <Banner>{w}</Banner>
                  </div>
                ))}
                <div style={{ marginTop: 12 }}>
                  <SiteMap geometry={preview.geometry} />
                </div>
              </>
            )}
          </div>
        </section>

        <section className="form-section">
          <div className="intro">
            <h2>Comparison periods</h2>
            <p>Imagery from both periods is compared to detect vegetation and water change. Dry-season windows reduce cloud cover.</p>
          </div>
          <div>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="b0">Baseline from</label>
                <input id="b0" type="date" className="input" value={baseline.start} onChange={(e) => setBaseline({ ...baseline, start: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="b1">Baseline to</label>
                <input id="b1" type="date" className="input" value={baseline.end} onChange={(e) => setBaseline({ ...baseline, end: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="c0">Current from</label>
                <input id="c0" type="date" className="input" value={current.start} onChange={(e) => setCurrent({ ...current, start: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="c1">Current to</label>
                <input id="c1" type="date" className="input" value={current.end} onChange={(e) => setCurrent({ ...current, end: e.target.value })} />
              </div>
            </div>
          </div>
        </section>

        {submitError && <Banner tone="error">{submitError}</Banner>}
        <div className="form-footer">
          <Link to="/" className="btn">
            Cancel
          </Link>
          <button type="submit" className="btn primary" disabled={!ready || submitting}>
            {submitting ? 'Submitting…' : 'Start screening'}
          </button>
        </div>
      </form>
    </div>
  )
}
