import { useEffect, useRef, useState } from 'react'
import { Check, Cpu, HardDrive, RefreshCw, ShieldCheck } from 'lucide-react'
import { api, message, type AiResources, type AnalysisStatus, type CameraList, type Health, type Models, type ModelTest, type Settings } from '../lib/api'
import BlinkSetup from './BlinkSetup'
import RecordingSetup from './RecordingSetup'
import { LocalRecordingSetup } from './LocalRecordingSetup'
import StorageSettings from './StorageSettings'
import SetupGuide from './SetupGuide'
import NotificationsPage from './NotificationsPage'
import InstallApp from './InstallApp'

const sections = [{ id: 'cameras', label: 'Cameras & recording' }, { id: 'ai', label: 'AI' }, { id: 'storage', label: 'Storage' }, { id: 'notifications', label: 'Notifications' }, { id: 'appearance', label: 'Appearance' }, { id: 'diagnostics', label: 'Diagnostics' }] as const
type Section = typeof sections[number]['id']
function currentSection(): Section {
  const id = new URLSearchParams(location.hash.split('?')[1] ?? '').get('section')
  return sections.some(section => section.id === id) ? id as Section : 'cameras'
}

export default function SettingsView({ settings, health, onSaved, focused, cameras = [] }: {
  settings: Settings; health: Health | null; onSaved: () => Promise<void>; focused?: 'ai' | 'storage'; cameras?: CameraList['items']
}) {
  const [guideOpen, setGuideOpen] = useState(() => !focused && new URLSearchParams(location.hash.split('?')[1] ?? '').get('setup') === '1')
  const guideButton = useRef<HTMLButtonElement>(null)
  const [section, setSection] = useState<Section>(currentSection)
  useEffect(() => {
    const changed = () => setSection(currentSection())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const [draft, setDraft] = useState(settings)
  const [models, setModels] = useState<Models | null>(null)
  const [selected, setSelected] = useState(settings.ai_model ?? '')
  const [result, setResult] = useState<ModelTest | null>(null)
  const [busy, setBusy] = useState('')
  const [feedback, setFeedback] = useState('')
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null)
  const [resources, setResources] = useState<AiResources | null>(null)
  useEffect(() => {
    if (guideOpen || (focused ?? section) !== 'ai') return
    const controller = new AbortController()
    let pending = false
    const load = async () => {
      if (pending) return
      pending = true
      const results = await Promise.allSettled([api<AnalysisStatus>('/analysis/status', { signal: controller.signal }), api<AiResources>('/ollama/resources', { signal: controller.signal })])
      if (!controller.signal.aborted) {
        setAnalysis(results[0].status === 'fulfilled' ? results[0].value : null)
        setResources(results[1].status === 'fulfilled' ? results[1].value : null)
      }
      pending = false
    }
    load()
    const timer = window.setInterval(load, 10000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [guideOpen, focused, section])
  async function loadModels() {
    setBusy('models'); setFeedback('')
    try {
      const inventory = await api<Models>('/ollama/models')
      setModels(inventory)
      if (!selected) setSelected(inventory.models.find(m => m.local && m.vision)?.name ?? '')
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy('') }
  }
  async function testModel() {
    setBusy('test'); setFeedback(''); setResult(null)
    try {
      const tested = await api<ModelTest>('/ollama/test', { method: 'POST', body: JSON.stringify({ model: selected }) })
      setResult(tested); await onSaved()
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy('') }
  }
  async function save() {
    setBusy('save'); setFeedback('')
    try {
      const saved = await api<Settings>('/settings', { method: 'PUT', body: JSON.stringify({ ...draft, ai_model: selected || draft.ai_model }) })
      setDraft(saved); await onSaved(); setFeedback('Settings saved.')
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy('') }
  }
  async function resetLiveTrust() {
    setBusy('trust'); setFeedback('')
    try { await api('/live/certificates/revoke', { method: 'POST' }); setFeedback('Live relay certificate trust cleared. A new session may require review.') }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy('') }
  }
  if (guideOpen) return <SetupGuide settings={settings} health={health} onSaved={onSaved} renderSettings={focus => <SettingsView cameras={cameras} focused={focus} settings={settings} health={health} onSaved={onSaved} />} onClose={() => { setDraft(settings); setSelected(settings.ai_model ?? ''); setGuideOpen(false); if (location.hash.includes('setup=')) location.hash = 'settings'; window.requestAnimationFrame(() => guideButton.current?.focus()) }} />
  const active = focused ?? section
  return <div className="settings-page">
    {!focused && <div className="settings-toolbar">
      <nav className="settings-sections" aria-label="Settings sections">{sections.map(item => <button key={item.id} className={section === item.id ? 'secondary selected' : 'secondary'} aria-pressed={section === item.id} aria-controls={`settings-${item.id}`} onClick={() => { location.hash = `settings?section=${item.id}` }}>{item.label}</button>)}</nav>
      <button ref={guideButton} className="secondary settings-guide-action" onClick={() => setGuideOpen(true)}>{cameras.length ? 'Review setup' : 'Open setup guide'}</button>
    </div>}
    {!focused && <div id="settings-cameras" hidden={active !== 'cameras'} className="settings-content">
      <BlinkSetup onConnected={onSaved} /><RecordingSetup onChanged={onSaved} /><LocalRecordingSetup onChanged={onSaved} />
      <section className="panel settings-section"><h2>Recording entitlement</h2>
      <label htmlFor="blink-plan">Blink recording entitlement</label><select id="blink-plan" value={draft.blink_entitlement} onChange={e => setDraft({ ...draft, blink_entitlement: e.target.value as Settings['blink_entitlement'] })}>
        <option value="unknown">Not confirmed</option><option value="paid">Paid plan</option><option value="trial">Free trial</option><option value="none">Neither plan nor trial</option>
      </select><p className="helper">Your confirmation is recorded separately from successful clip retrieval. A paid/trial clip does not prove no-plan support.</p>

        <a className="secondary button-link" href="#live?manage=1">Manage cameras</a>
      </section>
    </div>}
    <div id="settings-ai" hidden={active !== 'ai'} className="settings-content">
<section className="panel settings-section">
      <div className="section-heading"><Cpu size={22} /><div><h2>Local AI</h2><p>Use a vision model already installed in Ollama.</p></div></div>
      <button className="secondary" onClick={loadModels} disabled={!!busy}><RefreshCw size={16} />{busy === 'models' ? 'Checking…' : 'Check local models'}</button>
      {models && <><label htmlFor="ai-model">Vision model</label><select id="ai-model" value={selected} onChange={e => { setSelected(e.target.value); setResult(null) }}>
        <option value="">Choose a model</option>{models.models.map(model => <option key={model.name} value={model.name} disabled={!model.vision || !model.local}>{model.name}{!model.vision ? ' · text only' : !model.local ? ' · remote model' : ''}</option>)}
      </select><p className="helper">Ollama {models.version}. Model sizes are file sizes, not total GPU memory requirements.</p>
        <button className="primary" disabled={!selected || !!busy} onClick={testModel}>{busy === 'test' ? 'Testing image handling…' : 'Test with a synthetic image'}</button>
      </>}
      {busy === 'test' && <p role="status" className="helper">The first load can take up to two minutes. This test uses a generated color image.</p>}
      {result && <div className={result.passed ? 'notice success' : 'notice'} role="status"><strong>{result.passed ? 'Image test passed' : 'Image test did not pass'}</strong><p>{result.message} Test time: {result.elapsed_seconds.toFixed(1)} seconds.</p></div>}
      <div className="notice" role="status"><strong>{analysis?.cloud_disabled ? 'Local-only server confirmed' : 'Local-only setup required'}</strong><p>{analysis?.message ?? 'Checking the local AI service…'}</p>
        {analysis && !analysis.cloud_disabled && <p>Disable Ollama cloud features, then restart Ollama. This changes its shared server configuration.</p>}
      </div>
      <label className="checkbox-label"><input type="checkbox" checked={draft.ai_enabled} disabled={!!busy || (!draft.ai_enabled && (!analysis?.cloud_disabled || !(result?.passed || (analysis.ready && selected === analysis.model))))} onChange={e => setDraft({ ...draft, ai_enabled: e.target.checked })} />Analyze new recordings automatically</label>
      <label>AI workload<select value={draft.ai_workload ?? 'balanced'} disabled={!!busy} onChange={event => setDraft({ ...draft, ai_workload: event.target.value as Settings['ai_workload'] })}><option value="balanced">Balanced · up to 6 frames</option><option value="light">Light · up to 3 frames</option></select></label>
      <p className="helper">Light uses smaller images and context to reduce work; it can miss brief activity between samples. Save settings to apply it to new analysis requests. Queued requests keep their chosen preset. Neither preset guarantees accuracy or GPU fit.</p>
      <p className="helper">Save settings to apply. Existing recordings stay unanalyzed until you select Analyze recording. Playback and recording sync continue when AI is paused.</p>
      <p className="helper">{resources?.available ? `${resources.loaded_models} model(s) loaded in Ollama · ${(resources.loaded_vram_bytes / 1024 ** 3).toFixed(1)} GiB reported GPU allocation${resources.inference_busy ? ' · Porchlight inference is busy' : ''}.` : 'Shared Ollama resource status is unavailable.'} This does not measure other GPU applications.</p>
      {resources?.contention_possible && <p role="status" className="helper">Other models are loaded in the shared Ollama service and may compete for memory. Porchlight leaves them loaded; analysis can take longer.</p>}
      {analysis && <p className="helper">{analysis.queued} queued · {analysis.running} analyzing · {analysis.completed} completed · {analysis.failed} need attention</p>}
    </section>
      {!focused && <a className="text-link" href="#faces">Review faces and saved people</a>}
    </div>
    <div id="settings-storage" hidden={active !== 'storage'} className="settings-content">
<section className="panel settings-section">
      <div className="section-heading"><HardDrive size={22} /><div><h2>Local archive</h2><p>Your recordings stay on this PC.</p></div></div>
      <div className="storage-info"><span>Data folder</span><code>{health?.data_root ?? 'Loading…'}</code><span>Available space</span><strong>{health ? `${(health.free_space_bytes / 1024 ** 3).toFixed(1)} GiB` : 'Loading…'}</strong></div>
      <StorageSettings settings={draft} onChange={setDraft} onApplied={async () => { setDraft(await api<Settings>('/settings')); await onSaved() }} />
      <p className="helper">MP4 imports: up to 256 MiB and 5 minutes. JPEG imports: up to 32 MiB. Both allow 4096 pixels per edge. Imports do not prove Blink recording access.</p>
      <details className="archive-help"><summary>Backup and restore</summary><p className="helper">Stop Porchlight, then run backup.ps1 with a new local destination. restore.ps1 verifies a backup and previews a new destination; -Apply creates it. Credentials and sessions are excluded; restored sync, rules, AI and cleanup start paused. See the repository's Archive and backup guide for the exact commands.</p></details>
    </section>
    </div>
    {!focused && <><div id="settings-notifications" hidden={active !== 'notifications'} className="settings-content">
      <a className="text-link" href="#notifications">Open notification inbox</a>
      <InstallApp />
      <NotificationsPage mode="settings" timezone={settings.timezone} cameras={cameras} />
    </div><div id="settings-appearance" hidden={active !== 'appearance'} className="settings-content">
<section className="panel settings-section">
      <div className="section-heading"><ShieldCheck size={22} /><div><h2>Workspace</h2><p>Time and appearance for this installation.</p></div></div>
      <label htmlFor="timezone">Timezone</label><input id="timezone" value={draft.timezone} onChange={e => setDraft({ ...draft, timezone: e.target.value })} />
      <label htmlFor="theme">Appearance</label><select id="theme" value={draft.theme} onChange={e => setDraft({ ...draft, theme: e.target.value as Settings['theme'] })}>
        <option value="system">Use system setting</option><option value="light">Light</option><option value="dark">Dark</option>
      </select>

    </section>
    </div><div id="settings-diagnostics" hidden={active !== 'diagnostics'} className="settings-content">
<section className="panel settings-section diagnostics">
      <h2>Readiness</h2><p>Each connection is checked independently.</p>
      {health?.checks?.length ? health.checks.map(check => <div className="diagnostic-row" key={check.key}><div><strong>{check.label}</strong><small>{check.message}</small>
        {check.last_success_at && <small>Last success: {new Date(check.last_success_at).toLocaleString(undefined, { timeZone: settings.timezone })}</small>}
        {check.heartbeat_at && <small>Worker checked in: {new Date(check.heartbeat_at).toLocaleTimeString()}</small>}
        {(check.queued > 0 || check.running > 0 || check.needs_attention > 0) && <small>{check.queued} queued · {check.running} working · {check.needs_attention} need attention</small>}
        {check.safe_error && <small>{check.safe_error.replaceAll('_', ' ')}</small>}{check.action && <small>{check.action}</small>}
      </div><span className={`badge ${check.state === 'ready' ? 'ready' : ''}`}>{check.state.replaceAll('_', ' ')}</span></div>) : health && [ ['Database', health.database], ['Storage', health.archive], ['Blink', health.blink],
        ['Local AI', health.ai], ['Media tools', health.media_tools], ['Phone notifications', health.notifications], ['Live view', health.live_view],
      ].map(([label, component]) => {
        if (typeof component === 'string') return null
        return <div className="diagnostic-row" key={label as string}><div><strong>{label as string}</strong><small>{component.message}</small></div><span className={`badge ${component.state === 'ready' ? 'ready' : ''}`}>{component.state.replaceAll('_', ' ')}</span></div>
      })}
      <p className="helper">Background supervision: {health ? new Date(health.worker_heartbeat).toLocaleTimeString() : 'Loading…'}. Manage recording sync in Cameras &amp; recording.</p>
      {health?.recording_last_checked_at && <p className="helper">Last complete recording check: {new Date(health.recording_last_checked_at).toLocaleString(undefined, { timeZone: settings.timezone })}</p>}
      <button className="secondary" onClick={async () => {
        try {
          const report = await api<object>('/diagnostics/export')
          const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
          const link = document.createElement('a'); link.href = url; link.download = 'porchlight-diagnostics.json'; link.click()
          window.setTimeout(() => URL.revokeObjectURL(url), 1000)
          setFeedback('Diagnostics downloaded. The report includes counts and versions; private recordings, notes, names, paths and credentials are excluded.')
        } catch (error) { setFeedback(message(error)) }
      }}>Download redacted diagnostics</button>
      <button className="secondary" disabled={!!busy} onClick={resetLiveTrust}>Reset live relay trust</button><p className="helper">Ends live view and clears certificates approved for Porchlight. Saved recordings are preserved.</p>
    </section>
    </div></>}
    {!['notifications', 'diagnostics'].includes(active) && <div className="settings-save"><button className="primary" onClick={save} disabled={!!busy}><Check size={17} />{busy === 'save' ? 'Saving…' : 'Save settings'}</button><p className="helper">Save applies your camera entitlement, AI, storage and appearance changes.</p></div>}
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </div>
}
