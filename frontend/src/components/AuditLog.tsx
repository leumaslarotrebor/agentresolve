import type { AuditEvent } from '../types/api'

interface AuditLogProps {
  events: AuditEvent[]
}

export function AuditLog({ events }: AuditLogProps) {
  const toolEvents = events.filter((e) => e.event === 'tool_call')

  return (
    <section className="panel">
      <h2 className="panel__title">Audit Log</h2>
      {toolEvents.length === 0 ? (
        <p className="empty-hint">Tool calls will be logged here as the agent runs.</p>
      ) : (
        <pre className="audit-log">
          {toolEvents.map((e, i) => (
            <div key={i} className="audit-log__line">
              <span className="audit-log__time">{formatTime(e.timestamp)}</span>{' '}
              <span className="audit-log__tool">{String(e.tool)}()</span>{' '}
              <span
                className={
                  (e.result as { success?: boolean })?.success
                    ? 'audit-log__ok'
                    : 'audit-log__fail'
                }
              >
                {(e.result as { success?: boolean })?.success ? 'ok' : 'failed'}
              </span>
            </div>
          ))}
        </pre>
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
