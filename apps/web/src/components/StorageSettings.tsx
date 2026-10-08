import { useState } from 'react'
import { api, message, type RetentionPreview, type RetentionResult, type Settings } from '../lib/api'

export default function StorageSettings({ settings, onChange, onApplied }: {
  settings: Settings; onChange: (value: Settings) => void; onApplied: () => Promise<void>
}) {
  const [preview, setPreview] = useState<RetentionPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  function change(key: 'retention_days' | 'archive_budget_gib' | 'reserve_gib', value: number) {
    setPreview(null); onChange({ ...settings, [key]: value })
  }
  async function review() {
    setBusy(true); setFeedback(''); setPreview(null)
    try { setPreview(await api<RetentionPreview>('/retention/preview', { method: 'POST', body: JSON.stringify({ days: settings.retention_days }) })) }
    catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function apply(enable: boolean) {
    if (!preview) return
    setBusy(true); setFeedback('')
    try {
      const result = await api<RetentionResult>('/retention/apply', { method: 'POST', body: JSON.stringify({ token: preview.token, enable_automatic: enable }) })
      setPreview(null); await onApplied()
      setFeedback(`${result.events_deleted} recordings and ${result.captures_deleted} captures removed locally. Automatic cleanup ${result.automatic_enabled ? 'enabled' : 'off'}.`)
    } catch (error) { setPreview(null); setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function disable() {
    setBusy(true); setFeedback('')
    try {
      const current = await api<Settings>('/settings')
      await api('/settings', { method: 'PUT', body: JSON.stringify({ ...current, retention_enabled: false }) })
      setPreview(null); await onApplied(); setFeedback('Automatic cleanup is off.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  return <div className="storage-controls">
    <div className="filter-grid">
      <label>Keep ordinary recordings for (days)<input type="number" min={1} max={3650} value={settings.retention_days} disabled={busy || settings.retention_enabled} onChange={e => change('retention_days', Number(e.target.value))} /></label>
      <label>Archive budget (GiB)<input type="number" min={5} max={10000} value={settings.archive_budget_gib} onChange={e => change('archive_budget_gib', Number(e.target.value))} /></label>
      <label>Free-space reserve (GiB)<input type="number" min={1} max={1000} value={settings.reserve_gib} onChange={e => change('reserve_gib', Number(e.target.value))} /></label>
    </div>
    <p className="helper">Budget and reserve changes take effect after Save settings. Favourites are protected. Saving pauses when space is insufficient; recent recordings are not deleted to meet the budget.</p>
    {settings.retention_enabled ? <div className="notice"><strong>Automatic cleanup is enabled</strong><p>Ordinary Activity recordings and Library captures expire after {settings.retention_days} days. Pause cleanup before changing this policy.</p><button className="secondary" disabled={busy} onClick={disable}>Pause automatic cleanup</button></div> : <p>Automatic cleanup is off.</p>}
    <button className="secondary" disabled={busy} onClick={review}>{busy ? 'Working…' : 'Preview local cleanup'}</button>
    {preview && <div className="notice" role="status"><strong>Review before deleting</strong><p>{preview.event_count} recordings and {preview.capture_count} captures older than {preview.days} days. Approximately {(preview.reclaimable_bytes / 1024 ** 2).toFixed(1)} MiB can be released.</p><p>{preview.protected_count} favourites and {preview.busy_count} active items are protected. Only local copies, notes and analyses are removed. Blink copies and your exports remain.</p><div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => setPreview(null)}>Cancel cleanup</button><button className="danger" disabled={busy} onClick={() => { void apply(false) }}>Delete these local copies once</button><button className="danger" disabled={busy} onClick={() => { void apply(true) }}>Delete and enable automatic cleanup</button></div><p className="helper">This preview expires in five minutes and must still match the archive when confirmed. Open videos may release disk space after playback closes.</p></div>}
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </div>
}
