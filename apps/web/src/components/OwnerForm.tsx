import { useState, type FormEvent } from 'react'
import { HardDrive, LockKeyhole, ShieldCheck, Eye, EyeOff } from 'lucide-react'
import BrandMark from './BrandMark'
import { api, message, type Session } from '../lib/api'

export default function OwnerForm({ creating, onSession }: {
  creating: boolean; onSession: (session: Session) => void
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (creating && password !== confirmation) { setError('Your passwords do not match.'); return }
    setBusy(true); setError('')
    try {
      const credentials = { login_name: username, password }
      const session = creating
        ? await api<Session>('/setup/claim', {
            method: 'POST', body: JSON.stringify({ ...credentials,
              bootstrap_token: (await api<{ token: string }>('/setup/bootstrap', {
                headers: { 'X-Porchlight-Bootstrap': 'local-setup' },
              })).token,
            }),
          })
        : await api<Session>('/auth/login', { method: 'POST', body: JSON.stringify(credentials) })
      setPassword(''); setConfirmation(''); onSession(session)
    } catch (err) { setError(message(err)) }
    finally { setBusy(false) }
  }

  return <main className="owner-layout">
    <div className="owner-intro">
      <div className="brand"><BrandMark />Porchlight</div>
      <div className="owner-copy">
        <span className="eyebrow">YOUR HOME. YOUR ARCHIVE.</span>
        <h1>{creating ? 'Make yourself at home.' : 'Welcome home.'}</h1>
        <p>One place for your camera recordings, with a little help from local AI.</p>
        <div className="privacy-facts">
          <div><HardDrive /><span><strong>Stored on your PC</strong>Your archive stays on your own disk.</span></div>
          <div><ShieldCheck /><span><strong>AI runs locally</strong>Connect your existing Ollama models.</span></div>
          <div><LockKeyhole /><span><strong>A private workspace</strong>Sign in before viewing your recordings.</span></div>
        </div>
        <p className="boundary-note">Blink camera access still uses Blink’s services. Recording availability depends on your camera, storage, and account.</p>
      </div>
      <span className="local-label">Local development · Private access</span>
    </div>
    <section className="owner-panel" aria-labelledby="owner-title">
      <div className="form-card">
        <span className="eyebrow">{creating ? 'FIRST, YOUR WORKSPACE' : 'YOUR PRIVATE WORKSPACE'}</span>
        <h2 id="owner-title">{creating ? 'Create your local owner' : 'Sign in to Porchlight'}</h2>
        <p>{creating ? 'Choose a username and password for this installation. You’ll connect Blink separately.' : 'Use your local Porchlight username and password.'}</p>
        <form onSubmit={submit}>
          <label htmlFor="owner-username">Username</label>
          <input id="owner-username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required maxLength={64} pattern="[a-zA-Z0-9_.\-]+" placeholder="Your username" />
          <label htmlFor="owner-password">Password</label>
          <div className="password-field">
            <input id="owner-password" type={visible ? 'text' : 'password'} autoComplete={creating ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} required minLength={creating ? 12 : 1} maxLength={128} aria-describedby={creating ? 'password-hint' : undefined} />
            <button type="button" className="icon-button" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(v => !v)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button>
          </div>
          {creating && <><small id="password-hint">At least 12 characters. A memorable passphrase works well.</small>
            <label htmlFor="owner-confirm">Confirm password</label>
            <input id="owner-confirm" type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} required minLength={12} maxLength={128} />
          </>}
          {error && <p role="alert" className="error-message">{error}</p>}
          <button className="primary full-width" type="submit" disabled={busy}>{busy ? 'Please wait…' : creating ? 'Create workspace' : 'Sign in'}</button>
        </form>
        <p className="form-footnote"><LockKeyhole size={14} />This is your Porchlight login, separate from Blink.</p>
      </div>
    </section>
  </main>
}
