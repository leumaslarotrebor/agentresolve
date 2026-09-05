import { useEffect, useRef, useState } from 'react'
import './App.css'
import { Header } from './components/Header'
import { RequestPanel } from './components/RequestPanel'
import { StatusPanel } from './components/StatusPanel'
import { ExecutionTimeline } from './components/ExecutionTimeline'
import { ApprovalCard } from './components/ApprovalCard'
import { ResolutionCard } from './components/ResolutionCard'
import { AuditLog } from './components/AuditLog'
import { ErrorBanner } from './components/ErrorBanner'
import { DEMO_SCENARIOS } from './components/demoScenarios'
import { api } from './services/api'
import type { AgentRunResult } from './types/api'
import { ApiError } from './types/api'

const STEP_REVEAL_MS = 260

function App() {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)

  const [requestText, setRequestText] = useState('')
  const [customerId, setCustomerId] = useState('')
  const [orderId, setOrderId] = useState('')

  const [loading, setLoading] = useState(false)
  const [approvalLoading, setApprovalLoading] = useState(false)
  const [result, setResult] = useState<AgentRunResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [visibleStepCount, setVisibleStepCount] = useState(0)
  const revealedCountRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then(() => !cancelled && setBackendOnline(true))
      .catch(() => !cancelled && setBackendOnline(false))
    return () => {
      cancelled = true
    }
  }, [])

  // Animate the execution timeline revealing step-by-step, using the real
  // steps/timestamps returned by the backend. The backend executes each
  // run synchronously, so this is a client-side reveal rather than a true
  // server push — see README for why, and the polling-based GET
  // /api/agent/{run_id} path used after approval decisions.
  useEffect(() => {
    if (!result) {
      setVisibleStepCount(0)
      revealedCountRef.current = 0
      return
    }
    const total = result.steps.length
    let current = revealedCountRef.current
    if (current >= total) {
      setVisibleStepCount(total)
      return
    }
    setVisibleStepCount(current)
    const id = window.setInterval(() => {
      current += 1
      setVisibleStepCount(current)
      if (current >= total) {
        window.clearInterval(id)
        revealedCountRef.current = total
      }
    }, STEP_REVEAL_MS)
    return () => window.clearInterval(id)
  }, [result])

  async function handleSubmit() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.runAgent({
        customer_request: requestText.trim(),
        customer_id: customerId.trim() || undefined,
        order_id: orderId.trim() || undefined,
      })
      setResult(res)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setLoading(false)
    }
  }

  function handleSelectDemo(id: string) {
    const scenario = DEMO_SCENARIOS.find((s) => s.id === id)
    if (!scenario) return
    setRequestText(scenario.customerRequest)
    setCustomerId(scenario.customerId)
    setOrderId(scenario.orderId)
    setResult(null)
    setError(null)
  }

  async function handleApprovalDecision(approved: boolean) {
    if (!result?.pending_approval) return
    setApprovalLoading(true)
    setError(null)
    try {
      const res = approved
        ? await api.approve(result.pending_approval.approval_id, { decided_by: 'dashboard_reviewer' })
        : await api.reject(result.pending_approval.approval_id, { decided_by: 'dashboard_reviewer' })
      setResult(res)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setApprovalLoading(false)
    }
  }

  const status = result?.status ?? 'idle'
  const showApproval = result?.status === 'awaiting_approval' && result.pending_approval
  const showResolution = result && (result.resolution_message || result.action_taken || result.error)

  return (
    <div className="app-shell">
      <Header backendOnline={backendOnline} />

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <main className="layout">
        <div className="layout__left">
          <RequestPanel
            requestText={requestText}
            customerId={customerId}
            orderId={orderId}
            loading={loading}
            onRequestTextChange={setRequestText}
            onCustomerIdChange={setCustomerId}
            onOrderIdChange={setOrderId}
            onSubmit={handleSubmit}
            onSelectDemo={handleSelectDemo}
          />
        </div>

        <div className="layout__right">
          <StatusPanel status={status} analysis={result?.analysis ?? null} />
          <ExecutionTimeline steps={result?.steps ?? []} visibleCount={visibleStepCount} />
        </div>

        <div className="layout__full">
          {showApproval && result.pending_approval && (
            <ApprovalCard
              approval={result.pending_approval}
              loading={approvalLoading}
              onApprove={() => handleApprovalDecision(true)}
              onReject={() => handleApprovalDecision(false)}
            />
          )}

          {showResolution && <ResolutionCard result={result} />}

          {result && <AuditLog events={result.audit_trail} />}
        </div>
      </main>
    </div>
  )
}

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.detail
    return `${err.detail}`
  }
  if (err instanceof Error) return err.message
  return 'Something unexpected went wrong. Please try again.'
}

export default App
