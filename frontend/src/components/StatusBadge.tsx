import type { State } from '../api'

const TEXT: Record<State, string> = {
  queued: 'Waiting',
  running: 'In progress',
  ready: 'Ready',
  failed: 'Failed',
}

export function StatusBadge({ state }: { state: State }) {
  return (
    <span className={`badge ${state}`}>
      <span className="dot" />
      {TEXT[state]}
    </span>
  )
}

export function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const pct = total ? Math.round((completed / total) * 100) : 0
  return (
    <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${pct}%` }} />
    </div>
  )
}
