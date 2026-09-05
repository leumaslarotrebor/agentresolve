import type { AgentAnalysis, RunStatus } from '../types/api'

interface StatusPanelProps {
  status: RunStatus | 'idle'
  analysis: AgentAnalysis | null
}

const STATUS_LABEL: Record<string, string> = {
  idle: 'Waiting for a request',
  running: 'Running',
  awaiting_approval: 'Awaiting Approval',
  completed: 'Completed',
  failed: 'Failed',
  rejected: 'Rejected',
}

const STATUS_CLASS: Record<string, string> = {
  idle: 'badge badge--muted',
  running: 'badge badge--pending',
  awaiting_approval: 'badge badge--warning',
  completed: 'badge badge--success',
  failed: 'badge badge--danger',
  rejected: 'badge badge--danger',
}

export function StatusPanel({ status, analysis }: StatusPanelProps) {
  return (
    <section className="panel">
      <h2 className="panel__title">Agent Status</h2>

      <div className="status-grid">
        <div className="status-grid__row">
          <span className="status-grid__label">Status</span>
          <span className={STATUS_CLASS[status]}>{STATUS_LABEL[status]}</span>
        </div>

        {analysis ? (
          <>
            <div className="status-grid__row">
              <span className="status-grid__label">Intent</span>
              <span className="status-grid__value">{formatIntent(analysis.intent)}</span>
            </div>
            <div className="status-grid__row">
              <span className="status-grid__label">Priority</span>
              <span className="status-grid__value">{capitalize(analysis.priority)}</span>
            </div>
            <div className="status-grid__row">
              <span className="status-grid__label">Resolution</span>
              <span className="status-grid__value">{analysis.resolution}</span>
            </div>
            <div className="status-grid__row">
              <span className="status-grid__label">Confidence</span>
              <span className="status-grid__value">{Math.round(analysis.confidence * 100)}%</span>
            </div>
          </>
        ) : (
          <p className="empty-hint">Analysis appears once the agent has classified the request.</p>
        )}
      </div>
    </section>
  )
}

function formatIntent(intent: string): string {
  return intent
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
