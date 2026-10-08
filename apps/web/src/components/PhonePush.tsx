import { useCallback, useEffect, useState } from 'react'
import { api, message, type PushStatus } from '../lib/api'

function publicKey(value: string): Uint8Array<ArrayBuffer> {
  const raw = atob(value.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat((4 - value.length % 4) % 4))
  return Uint8Array.from(raw, character => character.charCodeAt(0))
}

export function PhonePush() {
  const [status, setStatus] = useState<PushStatus | null>(null)
  const [name, setName] = useState('My phone')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const supported = window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
  const originMatches = status?.public_origin === location.origin
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await api<PushStatus>('/push', { signal })
    if (!signal?.aborted) setStatus(result)
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    const load = () => { void refresh(controller.signal).catch(error => { if (!controller.signal.aborted) setFeedback(message(error)) }) }
    load(); const timer = window.setInterval(load, 10000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [refresh])
  async function action(operation: () => Promise<unknown>, success: string) {
    setBusy(true); setFeedback('')
    try { await operation(); await refresh(); setFeedback(success) }
    catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function pair() {
    if (!status?.public_key || !supported || !originMatches) return
    // Permission is requested only after the owner presses the pairing button.
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') throw new Error('Notifications were not allowed. Review this site’s browser permission before trying again.')
    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    await navigator.serviceWorker.ready
    const existing = await registration.pushManager.getSubscription()
    const subscription = existing ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: publicKey(status.public_key) })
    try {
      const data = subscription.toJSON()
      await api<PushStatus>('/push/devices', { method: 'POST', body: JSON.stringify({ name, endpoint: data.endpoint, keys: data.keys }) })
    } catch (error) { if (!existing) await subscription.unsubscribe(); throw error }
  }
  return <section className="panel settings-section phone-push"><h2>Phone notifications</h2>
    <p className="helper">Web Push sends encrypted alert text through your browser’s delivery service. Recordings and local AI stay on the PC. Use Chrome or Firefox for this first version.</p>
    <p>{status?.message ?? 'Checking phone setup…'}</p>
    {!status?.configured && <button className="secondary" disabled={busy || !status?.dependency_ready || !status.public_origin || originMatches} onClick={() => { void action(() => api('/push/configure', { method: 'POST' }), 'Local push keys created. Open the configured HTTPS address on your phone to pair it.') }}>Create local push keys</button>}
    {status?.configured && <form onSubmit={event => { event.preventDefault(); void action(pair, 'Browser paired. Send a test and check it with the screen locked.') }}>
      <label>Browser name<input required maxLength={60} value={name} onChange={event => setName(event.target.value)} /></label>
      <button className="primary" disabled={busy || !supported || !originMatches}>Pair this browser</button>
      {!originMatches && <p className="helper">Pair from the configured HTTPS address: {status.public_origin}</p>}
      {!supported && <p className="helper">This browser needs a secure connection and Web Push support.</p>}
    </form>}
    {status?.devices.map(device => <div className="diagnostic-row" key={device.id}><div><strong>{device.name}</strong><small>{device.enabled ? 'Paired' : 'Revoked'}</small></div><div className="detail-actions"><button className="secondary" disabled={busy || !device.enabled} onClick={() => { void action(() => api(`/push/devices/${device.id}/test`, { method: 'POST' }), 'Test queued. Provider acceptance appears below; check your phone separately.') }}>Send push test</button><button className="secondary" disabled={busy || !device.enabled} onClick={() => { void action(() => api(`/push/devices/${device.id}`, { method: 'DELETE' }), 'Browser revoked. Porchlight will no longer send it alerts.') }}>Revoke browser</button></div></div>)}
    {!!status?.deliveries.length && <details><summary>Delivery history</summary>{status.deliveries.map(delivery => <p className="helper" key={delivery.id}>{new Date(delivery.created_at).toLocaleString()} · {delivery.status.replaceAll('_', ' ')}{delivery.safe_error ? ` · ${delivery.safe_error.replaceAll('_', ' ').toLowerCase()}` : ''}</p>)}<p className="helper">Transport accepted means the service accepted the message. Phone display, tap-to-open and private playback need separate testing.</p></details>}
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </section>
}
