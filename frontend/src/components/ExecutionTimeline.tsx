import type { ExecutionStep } from '../types/api'

interface ExecutionTimelineProps {
  steps: ExecutionStep[]
  visibleCount: number
}

function StepIcon({ status }: { status: ExecutionStep['status'] }) {
  if (status === 'success') return <span className="step-icon step-icon--success">✓</span>
  if (status === 'failed') return <span className="step-icon step-icon--danger">✕</span>
  if (status === 'pending_approval') return <span className="step-icon step-icon--warning">⏸</span>
  return <span className="step-icon step-icon--muted">–</span>
}

export function ExecutionTimeline({ steps, visibleCount }: ExecutionTimelineProps) {
  const visible = steps.slice(0, visibleCount)

  return (
    <section className="panel">
      <h2 className="panel__title">Agent Execution</h2>
      {visible.length === 0 ? (
        <p className="empty-hint">Execution steps will appear here as the agent works.</p>
      ) : (
        <ol className="timeline">
          {visible.map((step) => (
            <li key={step.step_id} className="timeline__item">
              <StepIcon status={step.status} />
              <div className="timeline__body">
                <div className="timeline__row">
                  <span className="timeline__label">{step.label}</span>
                  <span className="timeline__time">{formatTime(step.timestamp)}</span>
                </div>
                <div className="timeline__summary">
                  {step.error ? <span className="timeline__error">{step.error}</span> : step.summary}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour12: false })
  } catch {
    return iso
  }
}
