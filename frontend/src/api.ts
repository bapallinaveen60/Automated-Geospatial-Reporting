// Typed client for the GeoVision API (src/geovision/api/main.py).

export type State = 'queued' | 'running' | 'ready' | 'failed'
export type Stage = 'processing' | 'needs_review' | 'approved' | 'changes_requested' | 'failed'
export type Severity = 'critical' | 'warning' | 'info'
export type Disposition = 'confirmed' | 'dismissed' | 'site_visit'

export interface Period {
  start: string
  end: string
}

export interface ProjectSummary {
  id: string
  site_name: string
  client: string
  submitted: string
  stage: Stage
  location: string | null
  area_ha: number | null
  status: { state: State; label: string; completed: number; total: number; engine_online: boolean }
  flags: { critical: number; warning: number }
}

export interface Reviewer {
  name: string
  qualification: string
  registration_no: string
  organisation?: string | null
}

export interface ReviewSubmission {
  decision: 'approved' | 'changes_requested'
  reviewer: Reviewer
  comments: string
  flag_reviews: Record<string, { disposition: Disposition; note: string }>
}

export interface ReviewRecord extends ReviewSubmission {
  decided_at: string
  draft_sha256: string
  final_sha256: string | null
}

export interface AuditEvent {
  at: string
  event: string
  reviewer?: string
  registration_no?: string
  comments?: string
}

export interface SourceStep {
  step: string
  inputs: number
  licences: string[]
  code_version: string
  items: string[]
}

export interface Step {
  key: string
  label: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
}

export interface Flag {
  rule_id: string
  severity: Severity
  message: string
  regulation: string | null
}

export interface Metrics {
  site: {
    area_ha: number
    perimeter_m: number
    centroid_lon: number
    centroid_lat: number
    state: string | null
    district: string | null
    locality: string | null
  }
  lulc: { code: number; label: string; area_ha: number; percent: number }[]
  indices: Record<string, { median: number | null; valid_fraction: number }>
  change: { index: string; threshold: number; loss_ha: number; gain_ha: number }[]
  proximity: {
    layer: string
    nearest_name: string | null
    distance_m: number | null
    overlap_ha: number
    search_radius_m: number
  }[]
  flags: Flag[]
}

export interface ProjectDetail {
  id: string
  site_name: string
  client: string
  requested_by: string | null
  submitted: string
  periods: { baseline: Period; current: Period }
  geometry: GeoJSON.Geometry
  stage: Stage
  review: ReviewRecord | null
  audit: AuditEvent[]
  sources: SourceStep[]
  final_report_url: string | null
  status: {
    state: State
    label: string
    steps: Step[]
    completed: number
    total: number
    error: string | null
    engine_online: boolean
  }
  summary: string[]
  metrics: Metrics | null
  warnings: string[]
  plates: { title: string; url: string }[]
  report_url: string | null
}

export interface AoiPreview {
  geometry: GeoJSON.Geometry
  area_ha: number
  perimeter_m: number
  centroid: [number, number]
  bbox: [number, number, number, number]
  warnings: string[]
}

export interface Defaults {
  periods: { baseline: Period; current: Period }
  max_area_ha: number
  module_title: string
}

export interface NewProject {
  client: string
  site_name: string
  geometry: GeoJSON.Geometry
  baseline_period: Period
  current_period: Period
  requested_by?: string
  notes?: string
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg
    } catch {
      /* not JSON */
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export const api = {
  defaults: () => request<Defaults>('/api/defaults'),
  projects: () => request<ProjectSummary[]>('/api/projects'),
  project: (id: string) => request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`),
  previewAoi: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<AoiPreview>('/api/aoi/preview', { method: 'POST', body: form })
  },
  createProject: (body: NewProject) =>
    request<{ id: string }>('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  review: (id: string, body: ReviewSubmission) =>
    request<ReviewRecord>(`/api/projects/${encodeURIComponent(id)}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  rerun: (id: string) =>
    request<{ id: string }>(`/api/projects/${encodeURIComponent(id)}/rerun`, { method: 'POST' }),
}

export const isActive = (s: State) => s === 'queued' || s === 'running'

export function formatDate(iso: string, withTime = true): string {
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  })
}

export function formatRelative(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  return days < 7 ? `${days} d ago` : formatDate(iso, false)
}

export function formatDistance(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`
}
