import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { initializeInstall } from './lib/install'
import { refreshPushWorker } from './lib/push-worker'
import './styles.css'

initializeInstall()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)

if (import.meta.env.PROD && window.isSecureContext && 'serviceWorker' in navigator) {
  const update = () => { void refreshPushWorker().catch(() => { /* Online use remains available. */ }) }
  update()
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') update() })
}
