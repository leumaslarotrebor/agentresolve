// Mirrors backend/app/models/agent.py — kept hand-in-sync with the FastAPI
// Pydantic models since this is a small fixed API surface.

export type StepStatus = 'success' | 'failed' | 'pending_approval' | 'skipped'

export interface ExecutionStep {
  step_id: string
  label: string
  tool: string | null
  status: StepStatus
  timestamp: string
  summary: string
  error: string | null
}

export type RunStatus = 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'rejected'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface ApprovalRequest {
  approval_id: string
  run_id: string
  action: string
  tool_name: string
  tool_args: Record<string, unknown>
  reason: string
  status: ApprovalStatus
  created_at: string
  resolved_at: string | null
}

export interface AgentAnalysis {
  intent: string
  priority: string
  resolution: string
  confidence: number
}

export interface AuditEvent {
  run_id: string
  timestamp: string
  event: string
  [key: string]: unknown
}

export interface AgentRunResult {
  run_id: string
  status: RunStatus
  analysis: AgentAnalysis | null
  steps: ExecutionStep[]
  resolution_message: string | null
  action_taken: Record<string, unknown> | null
  pending_approval: ApprovalRequest | null
  audit_trail: AuditEvent[]
  error: string | null
}

export interface AgentRunRequestPayload {
  customer_request: string
  customer_id?: string
  order_id?: string
  idempotency_key?: string
}

export interface ApprovalDecisionPayload {
  decided_by?: string
  note?: string
}

export interface HealthResponse {
  status: string
  llm_provider: string
  llm_configured: boolean
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}
