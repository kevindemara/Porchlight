import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, message, type CameraList, type InboxView, type RuleView } from '../lib/api'
import { PhonePush } from './PhonePush'
import RuleScope from './RuleScope'
import { onTopic } from '../lib/state-updates'

type Definition = { schema_version: string; name: string; enabled: boolean; camera_ids: string[]; categories: string[]; colors: string[]; directions: string[]; unknown_policy: string; channels: string[]; cooldown_seconds: number; freshness_seconds: number; include_historical: false; privacy_mode: string; include_thumbnail?: boolean; schedule: { timezone: string; active_iso_weekdays: number[]; quiet_hours: { enabled: boolean; start: string; end: string } } }
const initial = (timezone: string): Definition => ({ schema_version: '1.0', name: '', enabled: false, camera_ids: [], categories: [], colors: [], directions: [], unknown_policy: 'notify_generic', channels: ['in_app'], cooldown_seconds: 60, freshness_seconds: 900, include_historical: false, privacy_mode: 'generic', schedule: { timezone, active_iso_weekdays: [1, 2, 3, 4, 5, 6, 7], quiet_hours: { enabled: false, start: '22:00', end: '07:00' } } })

export default function NotificationsPage({ timezone, cameras, onRecording, mode = 'inbox' }: { timezone: string; cameras: CameraList['items']; onRecording?: (id: string) => void; mode?: 'inbox' | 'settings' }) {
  const [inbox, setInbox] = useState<InboxView | null>(null)
  const [rules, setRules] = useState<RuleView[]>([])
  const [draft, setDraft] = useState<Definition>(() => initial(timezone))
  const [editing, setEditing] = useState<{ id: string; revision: number } | null>(null)
  const [deleting, setDeleting] = useState<RuleView | null>(null)
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [cursor, setCursor] = useState<string | null>(null)
  const [paging, setPaging] = useState(false)
  const requestVersion = useRef(0)
  const load = useCallback(async (signal?: AbortSignal) => {
    const version = ++requestVersion.current
    const path = cursor ? `/notifications?cursor=${encodeURIComponent(cursor)}` : '/notifications'
    const [notifications, saved] = await Promise.all([mode === 'inbox' ? api<InboxView>(path, { signal }) : Promise.resolve(null), mode === 'settings' ? api<RuleView[]>('/notification-rules', { signal }) : Promise.resolve([])])
    if (!signal?.aborted && version === requestVersion.current) { setInbox(notifications); setRules(saved); setPaging(false) }
  }, [cursor, mode])
  useEffect(() => {
    const controller = new AbortController()
    let pending = false
    const refresh = async () => {
      if (pending) return
      pending = true
      try { await load(controller.signal) }
      catch (err) {
        if (!controller.signal.aborted) {
          setFeedback(message(err)); setPaging(false)
          if (cursor && err instanceof ApiError && err.status === 422) setCursor(null)
        }
      } finally { pending = false }
    }
    refresh(); const timer = window.setInterval(refresh, 10000)
    const unsubscribe = onTopic('notifications', () => { void refresh() })
    return () => { controller.abort(); requestVersion.current++; window.clearInterval(timer); unsubscribe() }
  }, [load, cursor])
  async function action(operation: () => Promise<unknown>, success = '', reload = true) {
    setBusy(true); setFeedback('')
    try { await operation(); if (reload) await load(); setFeedback(success) } catch (err) {
      setFeedback(message(err))
      if (err instanceof ApiError && (err.code === 'RULE_CONFLICT' || err.code === 'RULE_NOT_FOUND')) {
        try { await load() } catch { /* Keep the draft and original conflict message on a refresh failure. */ }
      }
    } finally { setBusy(false) }
  }
  const savedDraft = editing ? rules.find(rule => rule.id === editing.id) : undefined
  const changedDraft = !!editing && (!savedDraft || savedDraft.revision !== editing.revision)
  const latestDeletion = deleting ? rules.find(rule => rule.id === deleting.id) : undefined
  const changedDeletion = !!deleting && (!latestDeletion || latestDeletion.revision !== deleting.revision)
  function beginEdit(rule: RuleView) {
    setEditing({ id: rule.id, revision: rule.revision }); setDraft(rule.definition as unknown as Definition); setFeedback('')
  }
  async function reloadDraft() {
    if (!editing) return
    const fresh = await api<RuleView[]>('/notification-rules')
    setRules(fresh)
    const rule = fresh.find(rule => rule.id === editing.id)
    if (!rule) { setEditing(null); setDraft(initial(timezone)); return }
    beginEdit(rule)
  }
  return <div className="notifications-layout">
    {mode === 'settings' && <PhonePush />}
    {mode === 'inbox' && <section className="panel settings-section"><div className="section-heading"><h2>Inbox</h2><a className="secondary button-link" href="#settings?section=notifications">Notification settings</a></div><p className="helper">Local alerts stay here. Background phone delivery needs separate setup and testing.</p><div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => { void action(() => api('/notifications/test', { method: 'POST' }), 'Local inbox test created.') }}>Test local inbox</button><button className="secondary" disabled={busy} onClick={() => { void action(() => api('/notifications/snooze', { method: 'POST', body: JSON.stringify({ minutes: inbox?.snoozed_until ? 0 : 60 }) })) }}>{inbox?.snoozed_until ? 'Resume notifications' : 'Snooze for one hour'}</button></div>
      {inbox?.snoozed_until && <p className="helper">Snoozed until {new Date(inbox.snoozed_until).toLocaleString(undefined, { timeZone: timezone })}. Camera recording continues.</p>}
      {inbox?.items.length ? <div className="inbox-list">{inbox.items.map(item => <article key={item.id} className={item.read ? 'inbox-item read' : 'inbox-item'}><strong>{item.title}</strong><p>{item.body}</p><small>{new Date(item.created_at).toLocaleString(undefined, { timeZone: timezone })}</small><div className="detail-actions">{item.event_id && <button className="secondary" onClick={() => { void action(() => api(`/notifications/${item.id}/read`, { method: 'POST' })); onRecording?.(item.event_id!) }}>Open recording</button>}{!item.read && <button className="secondary" disabled={busy} onClick={() => { void action(() => api(`/notifications/${item.id}/read`, { method: 'POST' })) }}>Mark read</button>}</div></article>)}</div> : <p>Your inbox is empty. Create and enable a rule for new camera recordings.</p>}
      <div className="detail-actions">{cursor && <button className="secondary" disabled={busy || paging} onClick={() => { setPaging(true); setCursor(null) }}>Latest notifications</button>}{inbox?.next_cursor && <button className="secondary" disabled={busy || paging} onClick={() => { setPaging(true); setCursor(inbox.next_cursor) }}>Older notifications</button>}</div>{paging && <p className="helper" role="status">Loading notificationsâ€¦</p>}
    </section>}
    {mode === 'settings' && <section className="panel settings-section"><h2>Notification rules</h2><p className="helper">Rules apply to fresh camera recordings. Historical imports and manual reanalysis stay silent. Keep up to 50 rules.</p>{rules.map(rule => <div className="diagnostic-row" key={rule.id}><div><strong>{String(rule.definition.name)}</strong><small>{rule.definition.enabled ? 'Enabled' : 'Paused'}</small></div><div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => { beginEdit(rule) }}>Edit rule</button><button className="secondary" disabled={busy} onClick={() => { void action(() => api(`/notification-rules/${rule.id}`, { method: 'PUT', body: JSON.stringify({ expected_revision: rule.revision, definition: { ...rule.definition, enabled: !rule.definition.enabled } }) })) }}>{rule.definition.enabled ? 'Pause' : 'Enable'}</button><button className="secondary" disabled={busy} onClick={() => setDeleting(rule)}>Delete rule</button></div></div>)}
      {deleting && <div className="feedback" role="group" aria-label="Confirm rule deletion"><p>Delete {String(deleting.definition.name)}? Recordings and existing inbox messages stay saved.</p>{changedDeletion && <p role="status">This rule changed or was removed. Review its latest version before deleting.</p>}<div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => setDeleting(null)}>Keep rule</button>{changedDeletion ? <button className="secondary" disabled={busy} onClick={() => { if (latestDeletion) setDeleting(latestDeletion); else setDeleting(null) }}>{latestDeletion ? 'Review latest rule for deletion' : 'Close unavailable rule'}</button> : <button className="secondary" disabled={busy} onClick={() => { void action(async () => { await api(`/notification-rules/${deleting.id}?expected_revision=${deleting.revision}`, { method: 'DELETE' }); if (editing?.id === deleting.id) { setEditing(null); setDraft(initial(timezone)) }; setDeleting(null) }, 'Rule deleted.') }}>Confirm delete rule</button>}</div></div>}
      <form onSubmit={e => { e.preventDefault(); void action(async () => { await api(editing ? `/notification-rules/${editing.id}` : '/notification-rules', { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ definition: draft, ...(editing ? { expected_revision: editing.revision } : {}) }) }); setEditing(null); setDraft(initial(timezone)) }, 'Rule saved.') }}>
        <h3>{editing ? 'Edit rule' : 'New rule'}</h3>{changedDraft && <div className="feedback" role="group" aria-label="Rule draft conflict"><p>The saved rule changed or was removed. Your draft is kept here. Reloading discards this draft.</p><button type="button" className="secondary" disabled={busy} onClick={() => { void action(reloadDraft, 'Saved rule reloaded.', false) }}>{savedDraft ? 'Reload saved rule' : 'Discard unavailable rule draft'}</button></div>}<label>Rule name<input required value={draft.name} maxLength={80} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
        <RuleScope value={draft} cameras={cameras} disabled={busy} onChange={update => setDraft(previous => ({ ...previous, ...update }))} />
        <div className="filter-grid">
          <label>Cooldown (seconds)<input type="number" min={0} max={86400} value={draft.cooldown_seconds} onChange={e => setDraft({ ...draft, cooldown_seconds: Number(e.target.value) })} /></label><label>Maximum clip age (seconds)<input type="number" min={60} max={86400} value={draft.freshness_seconds} onChange={e => setDraft({ ...draft, freshness_seconds: Number(e.target.value) })} /></label>
        </div>
        <label className="checkbox-label"><input type="checkbox" checked={draft.enabled} onChange={e => setDraft({ ...draft, enabled: e.target.checked })} />Enable this rule</label><label className="checkbox-label"><input type="checkbox" checked={draft.channels.includes('web_push')} onChange={e => setDraft({ ...draft, channels: e.target.checked ? ['in_app', 'web_push'] : ['in_app'] })} />Also send to paired browsers</label><label className="checkbox-label"><input type="checkbox" checked={draft.privacy_mode === 'descriptive'} onChange={e => setDraft({ ...draft, privacy_mode: e.target.checked ? 'descriptive' : 'generic' })} />Include validated AI description in alerts</label>
        <label className="checkbox-label"><input type="checkbox" checked={draft.include_thumbnail ?? false} onChange={e => setDraft({ ...draft, include_thumbnail: e.target.checked })} />Include a recording thumbnail in phone alerts</label><p className="helper">Previews may appear on your lock screen. Your phone must be signed in and able to reach this PC; otherwise alerts show text only. Named matches update the same alert quietly.</p>
        <label>Uncertain observations<select value={draft.unknown_policy} onChange={e => setDraft({ ...draft, unknown_policy: e.target.value })}><option value="notify_generic">Keep a generic alert</option><option value="suppress">Suppress uncertain matches</option></select></label><p className="helper">Suppressing uncertain matches can miss activity. Every recording stays in Activity.</p>
        <fieldset className="weekday-picker"><legend>Active days</legend>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => <label key={day}><input type="checkbox" checked={draft.schedule.active_iso_weekdays.includes(index + 1)} onChange={e => setDraft({ ...draft, schedule: { ...draft.schedule, active_iso_weekdays: e.target.checked ? [...draft.schedule.active_iso_weekdays, index + 1] : draft.schedule.active_iso_weekdays.filter(value => value !== index + 1) } })} />{day}</label>)}</fieldset>
        <label>Schedule timezone<input required maxLength={64} value={draft.schedule.timezone} onChange={e => setDraft({ ...draft, schedule: { ...draft.schedule, timezone: e.target.value } })} /></label><p className="helper">Use an IANA timezone such as America/Toronto. The schedule follows its daylight-saving changes.</p>
        <label className="checkbox-label"><input type="checkbox" checked={draft.schedule.quiet_hours.enabled} onChange={e => setDraft({ ...draft, schedule: { ...draft.schedule, quiet_hours: { ...draft.schedule.quiet_hours, enabled: e.target.checked } } })} />Quiet hours ({draft.schedule.timezone})</label><div className="filter-grid">{(['start', 'end'] as const).map(key => <label key={key}>{key === 'start' ? 'Quiet from' : 'Quiet until'}<input type="time" value={draft.schedule.quiet_hours[key]} onChange={e => setDraft({ ...draft, schedule: { ...draft.schedule, quiet_hours: { ...draft.schedule.quiet_hours, [key]: e.target.value } } })} /></label>)}</div><p className="helper">Matching start and end times mean quiet all day.</p>
        <div className="detail-actions"><button className="primary" disabled={busy || changedDraft}>Save rule</button>{editing && <button className="secondary" type="button" disabled={busy} onClick={() => { setEditing(null); setDraft(initial(timezone)) }}>Cancel edit</button>}</div>
      </form>
    </section>}{feedback && <p role="status" className="feedback">{feedback}</p>}
  </div>
}
