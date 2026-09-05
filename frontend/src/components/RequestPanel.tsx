import type { FormEvent } from 'react'
import { DEMO_SCENARIOS } from './demoScenarios'

interface RequestPanelProps {
  requestText: string
  customerId: string
  orderId: string
  loading: boolean
  onRequestTextChange: (value: string) => void
  onCustomerIdChange: (value: string) => void
  onOrderIdChange: (value: string) => void
  onSubmit: () => void
  onSelectDemo: (id: string) => void
}

export function RequestPanel({
  requestText,
  customerId,
  orderId,
  loading,
  onRequestTextChange,
  onCustomerIdChange,
  onOrderIdChange,
  onSubmit,
  onSelectDemo,
}: RequestPanelProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!loading && requestText.trim().length >= 3) onSubmit()
  }

  return (
    <section className="panel">
      <h2 className="panel__title">Customer Request</h2>

      <div className="demo-row">
        {DEMO_SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            className="chip"
            onClick={() => onSelectDemo(s.id)}
            disabled={loading}
          >
            {s.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="request-form">
        <textarea
          className="request-textarea"
          placeholder="e.g. My laptop arrived damaged and I need a replacement before Friday."
          value={requestText}
          onChange={(e) => onRequestTextChange(e.target.value)}
          disabled={loading}
          rows={5}
          maxLength={2000}
        />

        <div className="request-form__row">
          <label className="field">
            <span className="field__label">Customer ID (optional)</span>
            <input
              type="text"
              value={customerId}
              onChange={(e) => onCustomerIdChange(e.target.value)}
              placeholder="CUST-1001"
              disabled={loading}
            />
          </label>
          <label className="field">
            <span className="field__label">Order ID (optional)</span>
            <input
              type="text"
              value={orderId}
              onChange={(e) => onOrderIdChange(e.target.value)}
              placeholder="ORD-5001"
              disabled={loading}
            />
          </label>
        </div>

        <button
          type="submit"
          className="btn btn--primary btn--block"
          disabled={loading || requestText.trim().length < 3}
        >
          {loading ? 'Resolving…' : 'Resolve Request'}
        </button>
      </form>
    </section>
  )
}
