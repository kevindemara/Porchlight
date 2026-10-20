import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Health, Settings } from '../lib/api'
import BlinkSetup from './BlinkSetup'
import RecordingSetup from './RecordingSetup'
import { LocalRecordingSetup } from './LocalRecordingSetup'
import { PhonePush } from './PhonePush'
import AiSetup from './AiSetup'
import PhoneSetup from './PhoneSetup'
import BlinkHardwareSetup, { moduleChoices } from './BlinkHardwareSetup'

const steps = ['Privacy', 'Storage', 'Blink', 'Recording source', 'Local AI', 'Phone', 'Review'] as const

export default function SetupGuide({ settings, health, onSaved, onClose, renderSettings }: {
  settings: Settings; health: Health | null; onSaved: () => Promise<void>; onClose: () => void; renderSettings: (focused: 'ai' | 'storage') => ReactNode
}) {
  const [step, setStep] = useState(0)
  const page = useRef<HTMLDivElement>(null)
  useEffect(() => { page.current?.focus({ preventScroll: true }); page.current?.scrollIntoView({ block: 'start' }) }, [step])
  const [skipped, setSkipped] = useState(new Set<number>())
  const next = (skip: boolean) => {
    setSkipped(previous => { const result = new Set(previous); if (skip) result.add(step); else result.delete(step); return result })
    setStep(value => Math.min(value + 1, steps.length - 1))
  }
  const rows = [
    { label: 'Local owner', state: 'ready', message: 'Your signed-in local owner protects recordings and settings.' },
    { label: 'Local archive', state: health?.archive.state ?? 'unverified', message: health?.archive.message ?? 'Waiting for the archive check.' },
    { label: 'Blink connection', state: health?.blink.state ?? 'unverified', message: health?.blink.message ?? 'Waiting for Blink status.' },
    { label: 'Hardware guidance', state: settings.blink_module_setup === 'unknown' ? 'unselected' : 'owner choice', message: `${moduleChoices.find(choice => choice.value === settings.blink_module_setup)?.label ?? 'Not sure yet'}. This saved choice guides setup; it does not verify hardware or recording access.` },
    { label: 'Recording access', state: health?.checks?.find(check => check.key === 'downloads')?.state ?? 'unverified', message: 'Saved paid-cloud clips do not establish subscription-free access. Verify fresh recordings from the selected source.' },
    { label: 'Local AI', state: health?.ai.state ?? 'unverified', message: health?.ai.message ?? 'Select and test a local vision model.' },
    { label: 'Phone delivery', state: health?.notifications.state ?? 'unverified', message: 'Pair the actual phone and confirm a test arrives. Skipping never marks delivery verified.' },
  ]
  return <div className="setup-guide">
    <section className="panel settings-section guide-header"><div className="section-heading"><div><h2>Set up Porchlight</h2><p>Configure each connection separately. You can pause and return to this guide.</p></div><button className="secondary" onClick={onClose}>Close guide</button></div>
      <nav className="guide-steps" aria-label="Setup steps">{steps.map((name, index) => <button className={step === index ? 'secondary selected' : 'secondary'} key={name} aria-current={step === index ? 'step' : undefined} onClick={() => setStep(index)}>{name}</button>)}</nav>
    </section>
    <div key={step} ref={page} tabIndex={-1} role="group" aria-label={`${steps[step]} setup`}>
      {step === 0 && <section className="panel settings-section"><h2>Privacy and your local owner</h2><p>Your local owner account is already created. This sign-in is separate from Blink.</p><p>Recordings and AI analysis stay on this PC. Blink access still depends on its services and your hardware, storage and account. Standard browser push uses browser-vendor infrastructure.</p><p>Connect accounts only in these local forms. Ollama must remain on loopback with cloud features disabled. The app checks this before private analysis.</p><p>Automatic AI, cleanup, camera controls and live capture require explicit actions; this guide does not enable them as you move between steps.</p></section>}
      {step === 1 && <><section className="panel settings-section"><h2>Choose local storage</h2><p>Your configured data folder:</p><code className="guide-path">{health?.data_root ?? 'Checking the local folder…'}</code><p className="helper">Use a local disk outside this source checkout, OneDrive and network drives. To use another folder, close the app and set PORCHLIGHT_DATA_ROOT before starting it. A new folder creates a separate installation; use the backup/restore instructions to migrate existing recordings.</p><p>{health ? `${(health.free_space_bytes / 1024 ** 3).toFixed(1)} GiB available` : 'Available space has not been checked.'}</p><p>Review the archive budget and free-space reserve below. Cleanup stays off until explicitly reviewed and applied.</p></section>{renderSettings('storage')}</>}
      {step === 2 && <BlinkSetup onConnected={onSaved} />}
      {step === 3 && <><BlinkHardwareSetup settings={settings} onSaved={onSaved} /><section className="panel settings-section"><h2>Recording source and entitlement</h2><p>Cloud recordings and Sync Module storage are separate sources. Choose the source your hardware and account actually provide; importing a file does not verify either source.</p><p>Subscription-free access stays unverified until eligible storage supplies new clips under a verified no-plan configuration. This guide never changes a subscription.</p><p>Entitlement currently saved: <strong>{settings.blink_entitlement}</strong>. Review the account setting outside this guide if it needs correction.</p></section><RecordingSetup onChanged={onSaved} /><LocalRecordingSetup onChanged={onSaved} /></>}
      {step === 4 && <><AiSetup onSaved={onSaved} onSkipped={() => next(true)} />{renderSettings('ai')}</>}
      {step === 5 && <><PhoneSetup /><section className="panel settings-section"><PhonePush /></section></>}
      {step === 6 && <section className="panel settings-section"><h2>Readiness review</h2><p>These states reflect observed checks. Visiting or skipping a step does not make its connection ready.</p>{rows.map(row => <div className="diagnostic-row" key={row.label}><div><strong>{row.label}</strong><small>{row.message}</small></div><span className={`badge ${row.state === 'ready' ? 'ready' : ''}`}>{row.state.replaceAll('_', ' ')}</span></div>)}{!!skipped.size && <p className="helper">Skipped this visit: {[...skipped].sort().map(index => steps[index]).join(', ')}. Those connections retain their observed state.</p>}<p className="helper">Automatic AI: {settings.ai_enabled ? 'enabled' : 'paused'} · automatic cleanup: {settings.retention_enabled ? 'enabled' : 'paused'}. Follow Readiness in Settings for independent workers and last-success times.</p></section>}
    </div>
    <div className="guide-actions"><button className="secondary" onClick={() => setStep(value => value - 1)} disabled={step === 0}>Back</button>{step < steps.length - 1 ? <><button className="text-link" onClick={() => next(true)}>Skip for now</button><button className="primary" onClick={() => next(false)}>Continue</button></> : <button className="primary" onClick={onClose}>Return to Settings</button>}</div>
  </div>
}
