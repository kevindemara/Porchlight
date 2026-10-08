import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import { api, message, type EventFilters, type SearchPreview } from '../lib/api'

export default function SearchTools({ onApply }: { onApply: (filters: EventFilters) => void }) {
  const [query, setQuery] = useState('')
  const [preview, setPreview] = useState<SearchPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  async function interpret() {
    setBusy(true); setFeedback(''); setPreview(null)
    try { setPreview(await api<SearchPreview>('/search/interpret', { method: 'POST', body: JSON.stringify({ query }) })) }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  return <section className="panel search-tools"><h2>Describe what you’re looking for</h2><p className="helper">Local AI proposes filters. Your recordings are searched only after you apply them.</p>
    <form className="filter-bar" onSubmit={e => { e.preventDefault(); void interpret() }}><input aria-label="Describe your search" value={query} maxLength={200} onChange={e => { setQuery(e.target.value); setPreview(null) }} placeholder="For example, vehicles yesterday evening" /><button className="secondary" disabled={busy || !query.trim()}><Sparkles size={16} />{busy ? 'Interpreting…' : 'Preview filters'}</button></form>
    {preview && <div className="notice"><strong>Proposed filters</strong><p>{preview.message}</p><p>Categories: {preview.filters.categories?.join(', ') || 'all'} · Colour: {preview.filters.color ?? 'all'} · Time of day: {preview.filters.daypart ?? 'all'}</p><p>{preview.filters.start ? new Date(preview.filters.start).toLocaleString(undefined, { timeZone: preview.timezone }) : 'Any start time'} → {preview.filters.end ? new Date(preview.filters.end).toLocaleString(undefined, { timeZone: preview.timezone }) : 'Any end time'} · {preview.timezone}</p><p>Camera selection: {preview.filters.camera_ids?.length ? `${preview.filters.camera_ids.length} camera(s)` : 'all'} · Text: {preview.filters.query || 'any'} · {preview.filters.favourites ? 'favourites only' : 'all recordings'}</p><button className="primary" disabled={preview.needs_clarification} onClick={() => onApply(preview.filters)}>Apply proposed filters</button></div>}
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </section>
}
