// Typed client for the GeoVision API (src/geovision/api/main.py).

export type State = 'queued' | 'running' | 'ready' | 'failed'
export type Severity = 'critical' | 'warning' | 'info'

export interface Period {
  start: string
  end: string
}

export interface ProjectSummary {
  id: string
  site_name: string
  client: string
  submitted: string
  status: { state: State; label: string; completed: number; total: number; engine_online: boolean }
  flags: { critical: number; warning: number }
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
  submitted: string
  periods: { baseline: Period; current: Period }
  geometry: GeoJSON.Geometry
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
  rerun: (id: string) =>
    request<{ id: string }>(`/api/projects/${encodeURIComponent(id)}/rerun`, { method: 'POST' }),
}

export const isActive = (s: State) => s === 'queued' || s === 'running'

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDistance(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`
}
