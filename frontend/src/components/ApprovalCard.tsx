import type { ApprovalRequest } from '../types/api'

interface ApprovalCardProps {
  approval: ApprovalRequest
  loading: boolean
  onApprove: () => void
  onReject: () => void
}

export function ApprovalCard({ approval, loading, onApprove, onReject }: ApprovalCardProps) {
  return (
    <section className="panel panel--approval">
      <div className="approval-header">
        <span className="badge badge--warning">Human Approval Required</span>
      </div>

      <div className="approval-field">
        <span className="approval-field__label">Action</span>
        <span className="approval-field__value">{describeAction(approval)}</span>
      </div>

      <div className="approval-field">
        <span className="approval-field__label">Reason</span>
        <span className="approval-field__value">{approval.reason}</span>
      </div>

      <div className="approval-actions">
        <button className="btn btn--success" onClick={onApprove} disabled={loading}>
          {loading ? 'Submitting…' : 'Approve'}
        </button>
        <button className="btn btn--outline-danger" onClick={onReject} disabled={loading}>
          Reject
        </button>
      </div>
    </section>
  )
}

function describeAction(approval: ApprovalRequest): string {
  if (approval.tool_name === 'create_refund') {
    const amount = approval.tool_args?.amount
    const orderId = approval.tool_args?.order_id
    if (typeof amount === 'number') {
      return `Issue a €${amount.toFixed(2)} refund${orderId ? ` for order ${orderId}` : ''}`
    }
  }
  return approval.action
}
