import { useEffect, useState, type FormEvent } from 'react'
import { Camera, RefreshCw } from 'lucide-react'
import { api, message, type BlinkStatus } from '../lib/api'

export default function BlinkSetup({ onConnected }: { onConnected: () => Promise<void> }) {
  const [status, setStatus] = useState<BlinkStatus | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    api<BlinkStatus>('/integrations/blink/status').then(value => { if (active) setStatus(value) }).catch(err => { if (active) setError(message(err)) })
    return () => { active = false }
  }, [])
  async function signIn(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    const credentials = { email, password }
    setPassword('')
    try {
      const next = await api<BlinkStatus>('/integrations/blink/auth/start', { method: 'POST', body: JSON.stringify(credentials) })
      setStatus(next); if (next.state === 'connected') { setEmail(''); await onConnected() }
    } catch (err) { setError(message(err)) }
    finally { setBusy(false) }
  }
  async function verify(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    const verification = { challenge_id: status?.challenge_id, code }
    setCode('')
    try {
      const next = await api<BlinkStatus>('/integrations/blink/auth/verify', { method: 'POST', body: JSON.stringify(verification) })
      setStatus(next); if (next.state === 'connected') { setEmail(''); await onConnected() }
    } catch (err) {
      setError(message(err))
      try { setStatus(await api<BlinkStatus>('/integrations/blink/status')) } catch { /* Keep the original verification error. */ }
    }
    finally { setBusy(false) }
  }
  async function refresh() {
    setBusy(true); setError('')
    try {
      await api('/integrations/blink/inventory/refresh', { method: 'POST' })
      setStatus(await api<BlinkStatus>('/integrations/blink/status')); await onConnected()
    } catch (err) { setError(message(err)) }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section blink-setup">
    <div className="section-heading"><Camera size={22} /><div><h2>Blink cameras</h2><p>Sign in here to discover your cameras. Credentials stay in the local setup flow.</p></div></div>
    {status && <div className="notice"><strong>{status.state === 'connected' ? `${status.camera_count} camera${status.camera_count === 1 ? '' : 's'} discovered` : status.state.replaceAll('_', ' ')}</strong><p>{status.message}</p></div>}
    {status?.state === 'connected' ? <><button className="secondary" disabled={busy} onClick={refresh}><RefreshCw size={16} />{busy ? 'Refreshing…' : 'Refresh camera inventory'}</button><p className="helper">Inventory refreshes are coalesced to at least two minutes. Use Save camera recordings below to start cloud clip collection.</p></> : status?.state === 'challenge_required' ? <form onSubmit={verify}>
      <label htmlFor="blink-code">Blink verification code</label><input id="blink-code" type="password" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} required minLength={4} maxLength={12} />
      <button className="primary" disabled={busy} type="submit">{busy ? 'Verifying…' : 'Verify code'}</button>
    </form> : <form onSubmit={signIn}>
      <label htmlFor="blink-email">Blink email</label><input id="blink-email" type="email" autoComplete="off" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} />
      <label htmlFor="blink-password">Blink password</label><input id="blink-password" type="password" autoComplete="off" value={password} onChange={e => setPassword(e.target.value)} required maxLength={256} />
      <button className="primary" disabled={busy || !status} type="submit">{busy ? 'Signing in…' : 'Connect Blink'}</button>
    </form>}
    {error && <p role="alert" className="error-message">{error}</p>}
    <p className="helper">Session material is encrypted for your Windows user. Your password and verification code are not saved. Recording access without a plan is unverified until new clips are retrieved and tested.</p>
  </section>
}
