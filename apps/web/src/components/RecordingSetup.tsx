import { useEffect, useRef, useState } from 'react'
import { Download, Pause, RefreshCw } from 'lucide-react'
import { api, message, type RecordingSync } from '../lib/api'
import { onTopic } from '../lib/state-updates'

export default function RecordingSetup({ onChanged }: { onChanged: () => Promise<void> }) {
  const [status, setStatus] = useState<RecordingSync | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)
  const requestVersion = useRef(0)
  const mutation = useRef(false)
  const lastCount = useRef<number | null>(null)
  const initialRange = useRef(false)
  useEffect(() => {
    let active = true
    let pending = false
    const controller = new AbortController()
    async function read() {
      if (pending || mutation.current) return
      pending = true
      const version = ++requestVersion.current
      try {
        const value = await api<RecordingSync>('/integrations/blink/recordings', { signal: controller.signal })
        if (!active || version !== requestVersion.current) return
        setStatus(value)
        if (!initialRange.current) { initialRange.current = true; if (value.history?.days != null) setDays(value.history.days) }
        if (lastCount.current !== null && lastCount.current !== value.archived) await onChanged()
        lastCount.current = value.archived
      } catch (err) { if (active && version === requestVersion.current) setError(message(err)) }
      finally { pending = false }
    }
    void read()
    const unsubscribe = onTopic('settings', () => { void read() })
    const timer = window.setInterval(() => { void read() }, 5000)
    return () => { active = false; requestVersion.current++; controller.abort(); window.clearInterval(timer); unsubscribe() }
  }, [onChanged])
  async function update(path: string, body: object) {
    if (mutation.current) return
    mutation.current = true
    const version = ++requestVersion.current
    setBusy(true); setError('')
    try {
      const value = await api<RecordingSync>(path, { method: 'POST', body: JSON.stringify(body) })
      if (version !== requestVersion.current) return
      setStatus(value)
      await onChanged()
    } catch (err) { if (version === requestVersion.current) setError(message(err)) }
    finally { mutation.current = false; if (version === requestVersion.current) setBusy(false) }
  }
  return <section className="panel settings-section">
    <div className="section-heading"><Download size={22} /><div><h2>Save camera recordings</h2><p>Copy available Blink cloud recordings into this PC’s archive.</p></div></div>
    <p className="helper">Start with the last seven days. New clip checks run about every {status?.poll_interval_seconds ?? 60} seconds, with small timing variation. Temporary errors retry automatically with backoff and a longer cooldown after repeated failures. Sign-in or configuration problems may need your attention. Original recordings stay in Blink.</p>
    {status && <div className="notice" role="status"><strong>{status.state.replaceAll('_', ' ')}</strong><p>{status.message}</p>
      <p>{status.discovered} discovered · {status.archived} saved · {status.pending} waiting · {status.failed} unavailable</p>
      {status.incomplete && <p>Discovery is in progress; this is not a complete history yet.</p>}
      {status.last_error_code && <p className="helper">Reason: {status.last_error_code.replaceAll('_', ' ').toLowerCase()}</p>}
    </div>}
    <div className="detail-actions"><button className="primary" disabled={busy || !status} onClick={() => { void update('/integrations/blink/sync', { enabled: true }) }}><RefreshCw size={16} />{busy ? 'Updating…' : status?.enabled ? 'Retry recording work' : 'Sync recordings'}</button>
      {status?.enabled && <button className="secondary" disabled={busy} onClick={() => { void update('/integrations/blink/sync', { enabled: false }) }}><Pause size={16} />Pause sync</button>}
    </div>
    {status?.last_checked_at && <p className="helper">Last complete check: {new Date(status.last_checked_at).toLocaleString()}. {status.next_sync_at && <>Next eligible check: {new Date(status.next_sync_at).toLocaleTimeString()}.</>}</p>}
    <details className="settings-section"><summary>Retrieve older cloud recordings</summary>
      <p className="helper">Search available Blink history alongside ordinary sync. These imports stay silent and can be analyzed manually. Blink may have already expired older clips.</p>
      <label>History range<select value={days} disabled={busy} onChange={event => setDays(Number(event.target.value))}>
        <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={365}>Last year</option><option value={0}>All available history</option>
      </select></label>
      {status?.history && status.history.state !== 'not_started' && <p role="status">History: {status.history.state.replaceAll('_', ' ')} · {status.history.archived} saved · {status.history.pending} waiting · {status.history.failed} unavailable</p>}
      <div className="detail-actions"><button className="secondary" disabled={busy || !status} onClick={() => { void update('/integrations/blink/history', { action: 'start', days }) }}>Retrieve selected history</button>
        {status?.history && status.history.state !== 'not_started' && status.history.state !== 'complete' && <button className="secondary" disabled={busy} onClick={() => { void update('/integrations/blink/history', { action: status.history?.state === 'paused' ? 'resume' : 'pause' }) }}>{status.history.state === 'paused' ? 'Resume history' : 'Stop history retrieval'}</button>}
      </div>
      <p className="helper">Stopping history pauses its next page or download. A download already in progress may finish; saved clips are kept. Ordinary sync has its own pause control.</p>
    </details>
    {error && <p className="error-message" role="alert">{error}</p>}
    <p className="helper">Cloud syncing is separate from the experimental Sync Module local-storage controls below. Subscription-free recording access has not been verified.</p>
  </section>
}
