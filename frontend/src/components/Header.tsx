interface HeaderProps {
  backendOnline: boolean | null
}

export function Header({ backendOnline }: HeaderProps) {
  const label = backendOnline === null ? 'Checking…' : backendOnline ? 'Agent Ready' : 'Backend Unreachable'
  const dotClass = backendOnline === null ? 'dot dot--pending' : backendOnline ? 'dot dot--ok' : 'dot dot--down'

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <span className="app-header__mark">AR</span>
        <div>
          <div className="app-header__title">AgentResolve</div>
          <div className="app-header__subtitle">Autonomous customer support resolution</div>
        </div>
      </div>
      <div className="app-header__status">
        <span className={dotClass} />
        {label}
      </div>
    </header>
  )
}
