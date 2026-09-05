interface ErrorBannerProps {
  message: string
  onDismiss: () => void
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      <button className="error-banner__dismiss" onClick={onDismiss} aria-label="Dismiss error">
        ×
      </button>
    </div>
  )
}
