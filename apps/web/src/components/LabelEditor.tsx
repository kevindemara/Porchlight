import { useRef, useEffect, useState } from 'react'
import { ApiError, api, message, type AnalysisView, type Event, type OwnerEntity } from '../lib/api'

const categories = ['person', 'vehicle', 'animal', 'package', 'other', 'unknown'] as const
const colors = ['black', 'white', 'gray', 'silver', 'blue', 'red', 'green', 'yellow', 'orange', 'brown', 'beige', 'other'] as const
const directions = ['left_to_right', 'right_to_left', 'toward_camera', 'away_from_camera', 'stationary', 'unknown'] as const
const actions = ['visible', 'moving', 'passing', 'approaching', 'departing', 'stopping', 'parked', 'placing_object', 'picking_up_object', 'opening_door', 'closing_door', 'entering_doorway', 'exiting_doorway', 'unknown'] as const
const subtypes: Partial<Record<OwnerEntity['category'], NonNullable<OwnerEntity['subtype']>[]>> = { vehicle: ['car', 'truck', 'van', 'bus', 'motorcycle', 'bicycle'], animal: ['dog', 'cat', 'bird'], package: ['box', 'envelope'] }
type Row = { key: string; value: OwnerEntity }
const blank = (): Row => ({ key: crypto.randomUUID(), value: { category: 'unknown', subtype: null, color: null, actions: ['visible'], direction: 'unknown' } })
const label = (text: string) => text.replaceAll('_', ' ')

export default function LabelEditor({ event, analysis, onSaved }: { event: Event; analysis: AnalysisView | null; onSaved: (event: Event) => void }) {
  const [draft, setDraft] = useState<{ rows: Row[]; revision: number; basedOn: number | null } | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [conflict, setConflict] = useState(false)
  const controller = useRef(new AbortController())
  useEffect(() => { const active = new AbortController(); controller.current = active; return () => active.abort() }, [])
  function begin(current = event) {
    const entities = current.corrected_entities ?? (analysis?.entities ?? []).map(entity => ({
      category: entity.category, color: entity.color, direction: entity.direction,
      subtype: subtypes[entity.category]?.find(value => value === entity.subtype) ?? null,
      actions: actions.filter(action => entity.actions.includes(action)).slice(0, 6),
    }))
    setDraft({ revision: current.correction_revision ?? 0, basedOn: current.corrected_entities !== null && current.corrected_entities !== undefined ? current.correction_based_on ?? null : analysis?.revision ?? null, rows: entities.map(entity => ({ key: crypto.randomUUID(), value: { ...entity, actions: entity.actions?.length ? entity.actions : ['visible'] } })) })
    setFeedback(''); setConflict(false)
  }
  function edit(key: string, update: Partial<OwnerEntity>) {
    setDraft(previous => previous && ({ ...previous, rows: previous.rows.map(row => row.key === key ? { ...row, value: { ...row.value, ...update } } : row) }))
  }
  async function save(reset = false) {
    if (!draft) return
    setBusy(true); setFeedback(''); setConflict(false)
    try {
      const saved = await api<Event>(`/events/${event.id}/labels`, { method: 'PUT', body: JSON.stringify({ revision: draft.revision, based_on: reset ? null : draft.basedOn, entities: reset ? null : draft.rows.map(row => row.value) }), signal: controller.current.signal })
      if (controller.current.signal.aborted) return
      onSaved(saved); setDraft(null); setFeedback(reset ? 'Original AI labels restored.' : 'Your labels saved. No new alert was sent.')
    } catch (err) { if (!controller.current.signal.aborted) { setFeedback(message(err)); setConflict(err instanceof ApiError && err.status === 409) } }
    finally { if (!controller.current.signal.aborted) setBusy(false) }
  }
  async function reload() {
    setBusy(true)
    try {
      const latest = await api<Event>(`/events/${event.id}`, { signal: controller.current.signal })
      if (!controller.current.signal.aborted) { onSaved(latest); begin(latest) }
    } catch (err) { if (!controller.current.signal.aborted) setFeedback(message(err)) }
    finally { if (!controller.current.signal.aborted) setBusy(false) }
  }
  return <section className="label-review" aria-label="Object label corrections">
    {event.corrected_entities !== null && event.corrected_entities !== undefined && <div className="notice"><strong>Your object labels · revision {event.correction_revision}</strong><p>{event.corrected_entities.length ? event.corrected_entities.map(entity => [entity.color, entity.subtype ?? entity.category, (entity.actions ?? []).map(label).join(', '), label(entity.direction ?? 'unknown')].filter(Boolean).join(' · ')).join('; ') : 'No objects labelled.'}</p><p className="helper">{event.correction_based_on ? `Reviewed against AI revision ${event.correction_based_on}. ` : 'Owner-supplied labels. '}Archive filters and digests use your labels. AI evidence and existing alerts keep their original result.</p></div>}
    {!draft ? <button className="secondary" onClick={() => begin()}>Description is wrong · correct object labels</button> : <fieldset disabled={busy} className="label-editor"><legend>Your object labels</legend>
      <p className="helper">Label the whole recording. Removing every object saves an explicit empty set. Clearing the correction restores AI labels. Use Unknown when unsure; these are your observations.</p>
      {draft.rows.map((row, index) => <fieldset className="label-row" key={row.key}><legend>Object {index + 1}</legend><div className="filter-grid">
        <label>Category<select value={row.value.category} onChange={e => edit(row.key, { category: e.target.value as OwnerEntity['category'], subtype: null })}>{categories.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Type<select value={row.value.subtype ?? ''} onChange={e => edit(row.key, { subtype: (e.target.value || null) as OwnerEntity['subtype'] })}><option value="">Unspecified</option>{(subtypes[row.value.category] ?? []).map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Colour<select value={row.value.color ?? ''} onChange={e => edit(row.key, { color: (e.target.value || null) as OwnerEntity['color'] })}><option value="">Unknown / not visible</option>{colors.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Direction<select value={row.value.direction} onChange={e => edit(row.key, { direction: e.target.value as OwnerEntity['direction'] })}>{directions.map(value => <option value={value} key={value}>{label(value)}</option>)}</select></label>
      </div><fieldset className="label-actions"><legend>Actions · choose up to six</legend>{actions.map(action => <label className="check-label" key={action}><input type="checkbox" checked={row.value.actions?.includes(action)} disabled={!row.value.actions?.includes(action) && (row.value.actions?.length ?? 0) >= 6} onChange={e => edit(row.key, { actions: e.target.checked ? [...(row.value.actions ?? []), action] : (row.value.actions ?? []).filter(value => value !== action) })} />{label(action)}</label>)}</fieldset><button className="text-link" onClick={() => setDraft(previous => previous && ({ ...previous, rows: previous.rows.filter(item => item.key !== row.key) }))}>Remove object {index + 1}</button></fieldset>)}
      <div className="detail-actions"><button className="secondary" disabled={draft.rows.length >= 20} onClick={() => setDraft(previous => previous && ({ ...previous, rows: [...previous.rows, blank()] }))}>Add object</button><button className="primary" disabled={draft.rows.some(row => !row.value.actions?.length)} onClick={() => { void save() }}>Save object labels</button><button className="secondary" onClick={() => { void save(true) }}>Use original AI labels</button><button className="secondary" onClick={() => { setDraft(null); setFeedback(''); setConflict(false) }}>Cancel label changes</button></div>
    </fieldset>}
    {feedback && <p className="feedback" role="status">{feedback}</p>}{conflict && <button className="secondary" disabled={busy} onClick={() => { void reload() }}>Reload labels and discard this draft</button>}
  </section>
}
