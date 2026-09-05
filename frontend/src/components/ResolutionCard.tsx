import type { AgentRunResult } from '../types/api'

interface ResolutionCardProps {
  result: AgentRunResult
}

export function ResolutionCard({ result }: ResolutionCardProps) {
  return (
    <section className="panel">
      <h2 className="panel__title">Resolution</h2>

      {result.action_taken && (
        <div className="resolution-action">{describeAction(result.action_taken)}</div>
      )}

      {result.resolution_message && (
        <div className="resolution-message">
          <span className="resolution-message__label">Customer notification</span>
          <p>{result.resolution_message}</p>
        </div>
      )}

      {result.error && (
        <div className="resolution-error">
          <span className="resolution-message__label">Error</span>
          <p>{result.error}</p>
        </div>
      )}
    </section>
  )
}

function describeAction(action: Record<string, unknown>): string {
  const type = action.type
  if (type === 'replacement') {
    return `Replacement ${action.replacement_id} created successfully. Estimated delivery: ${action.estimated_delivery}.`
  }
  if (type === 'refund') {
    const amount = action.amount as number
    return `Refund ${action.refund_id} issued for €${amount.toFixed(2)}.`
  }
  if (type === 'ticket') {
    return `Support ticket ${action.ticket_id} opened (${action.priority} priority).`
  }
  return 'Request reviewed.'
}
