import type { ReactNode } from 'react'
import { AlertTriangle, CircleAlert, Info } from 'lucide-react'
import type { Severity, Stage } from '../api'

const STAGE_LABEL: Record<Stage, string> = {
  processing: 'Processing',
  needs_review: 'Needs review',
  approved: 'Approved',
  changes_requested: 'Changes requested',
  failed: 'Failed',
}

export function StageStatus({ stage }: { stage: Stage }) {
  return (
    <span className={`status ${stage}`}>
      <i />
      {STAGE_LABEL[stage]}
    </span>
  )
}

const SEV_ICON = { critical: CircleAlert, warning: AlertTriangle, info: Info } as const
const SEV_LABEL = { critical: 'Critical', warning: 'Warning', info: 'Note' } as const

export function SeverityLabel({ severity }: { severity: Severity }) {
  const Icon = SEV_ICON[severity]
  return (
    <span className={`sev ${severity}`}>
      <Icon size={13} strokeWidth={2.2} />
      {SEV_LABEL[severity]}
    </span>
  )
}

export function Banner({
  tone = 'warn',
  children,
}: {
  tone?: 'warn' | 'error' | 'info'
  children: ReactNode
}) {
  const Icon = tone === 'error' ? CircleAlert : tone === 'warn' ? AlertTriangle : Info
  return (
    <div className={`banner ${tone === 'info' ? '' : tone}`}>
      <Icon size={15} />
      <div>{children}</div>
    </div>
  )
}

export function Prop({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="prop">
      <dt>{label}</dt>
      <dd>{children ?? <span className="subtle">—</span>}</dd>
    </div>
  )
}

export function Progress({ completed, total }: { completed: number; total: number }) {
  const pct = total ? Math.round((completed / total) * 100) : 0
  return (
    <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${pct}%` }} />
    </div>
  )
}
