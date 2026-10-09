import { useEffect, useState } from 'react'
import { Bookmark, Trash2 } from 'lucide-react'
import { api, message, type EventFilters, type SavedView } from '../lib/api'

export default function SavedViews({ filters, onApply }: {
  filters: EventFilters; onApply: (filters: EventFilters, id: string) => void
}) {
  const [views, setViews] = useState<SavedView[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void api<SavedView[]>('/saved-views', { signal: controller.signal }).then(setViews).catch(error => { if (!controller.signal.aborted) setFeedback(message(error)) })
    return () => controller.abort()
  }, [])
  async function save() {
    setBusy(true); setFeedback('')
    try {
      const view = await api<SavedView>('/saved-views', { method: 'POST', body: JSON.stringify({ name, filters }) })
      setViews(previous => [...previous, view]); setName(''); setFeedback('View saved. Open it to get a link you can bookmark.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function remove(view: SavedView) {
    setBusy(true); setFeedback('')
    try { await api(`/saved-views/${view.id}`, { method: 'DELETE' }); setViews(previous => previous.filter(item => item.id !== view.id)); setFeedback('Saved view removed. Recordings are preserved.') }
    catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  return <div className="panel archive-tool-panel"><p className="helper">Save the current search and filters. Date intervals stay fixed; favourite/category filters update as recordings arrive.</p>
    {views.map(view => <div className="diagnostic-row" key={view.id}><button className="text-link" disabled={busy} onClick={() => onApply(view.filters, view.id)}><Bookmark size={16} />{view.name}</button><button className="icon-button" aria-label={`Remove saved view ${view.name}`} disabled={busy} onClick={() => { void remove(view) }}><Trash2 size={16} /></button></div>)}
    <form className="filter-bar" onSubmit={event => { event.preventDefault(); void save() }}><input aria-label="Saved view name" maxLength={60} value={name} onChange={event => setName(event.target.value)} placeholder="Name this view" /><button className="secondary" disabled={busy || !name.trim()}>Save current view</button></form>
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </div>
}
