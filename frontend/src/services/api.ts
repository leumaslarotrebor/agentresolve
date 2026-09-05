import type {
  AgentRunRequestPayload,
  AgentRunResult,
  ApprovalDecisionPayload,
  HealthResponse,
} from '../types/api'
import { ApiError } from '../types/api'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the AgentResolve backend. Is it running?')
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
      else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ')
      }
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(response.status, detail)
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(response.status, 'The server returned a malformed response.')
  }
}

export const api = {
  health(): Promise<HealthResponse> {
    return request<HealthResponse>('/api/health')
  },

  runAgent(payload: AgentRunRequestPayload): Promise<AgentRunResult> {
    return request<AgentRunResult>('/api/agent/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getRun(runId: string): Promise<AgentRunResult> {
    return request<AgentRunResult>(`/api/agent/${encodeURIComponent(runId)}`)
  },

  approve(approvalId: string, payload: ApprovalDecisionPayload = {}): Promise<AgentRunResult> {
    return request<AgentRunResult>(`/api/approval/${encodeURIComponent(approvalId)}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  reject(approvalId: string, payload: ApprovalDecisionPayload = {}): Promise<AgentRunResult> {
    return request<AgentRunResult>(`/api/approval/${encodeURIComponent(approvalId)}/reject`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
