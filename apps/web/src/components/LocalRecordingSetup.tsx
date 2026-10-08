import { useEffect, useRef, useState } from 'react'
import { api, message, type LocalRecordingStatus } from '../lib/api'

export function LocalRecordingSetup({ onChanged }: { onChanged: () => Promise<void> }) {
  const [status, setStatus] = useState<LocalRecordingStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const saved = useRef(onChanged)
  useEffect(() => { saved.current = onChanged }, [onChanged])
  useEffect(() => {
    const controller = new AbortController()
    let lastCount: number | null = null
    let inFlight = false
    const load = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const value = await api<LocalRecordingStatus>('/integrations/blink/local-recordings', { signal: controller.signal })
        if (controller.signal.aborted) return
        setStatus(value)
        if (lastCount !== null && value.sync.archived !== lastCount) await saved.current()
        lastCount = value.sync.archived
      } catch (error) { if (!controller.signal.aborted) setFeedback(message(error)) }
      finally { inFlight = false }
    }
    void load(); const timer = window.setInterval(() => { void load() }, 10000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [])
  async function control(enabled: boolean) {
    setBusy(true); setFeedback('')
    try {
      setStatus(await api<LocalRecordingStatus>('/integrations/blink/local-sync', { method: 'POST', body: JSON.stringify({ enabled }) }))
      await onChanged()
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section"><h2>Sync Module local storage</h2>
    <p className="helper">Experimental retrieval copies listed module clips into this PC’s archive through Blink’s service. Internet is required. Removable storage recording is configured in the official Blink app.</p>
    {status?.modules.map(module => <div className="diagnostic-row" key={module.id}><div><strong>{module.name}</strong><small>{module.message}</small></div><span className="badge">{module.storage_ready ? 'Candidate' : 'Unavailable'}</span></div>)}
    {status && !status.modules.length && <p>No eligible module has been observed. Sync Module Core cannot record to USB or microSD.</p>}
    {status && <p role="status">{status.sync.message} {status.sync.archived} saved · {status.sync.pending} waiting · {status.sync.failed} unavailable</p>}
    <div className="camera-control-actions"><button className="secondary" disabled={busy || !status?.eligible} onClick={() => { void control(true) }}>{status?.sync.enabled ? 'Retry local recording work' : 'Sync local recordings'}</button>{status?.sync.enabled && <button className="secondary" disabled={busy} onClick={() => { void control(false) }}>Pause local sync</button>}</div>
    <p className="helper">Local storage retrieval and no-plan compatibility need testing on your exact module. This does not turn cloud clip backups into direct local recording.</p>
    {feedback && <p role="alert">{feedback}</p>}
  </section>
}
