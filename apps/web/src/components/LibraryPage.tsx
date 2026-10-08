import { useCallback, useEffect, useState } from 'react'
import { Image, RefreshCw } from 'lucide-react'
import { api, message, type Capture, type CaptureList } from '../lib/api'
import LibraryCard from './LibraryCard'
import { onTopic } from '../lib/state-updates'

export default function LibraryPage({ timezone }: { timezone: string }) {
  const [items, setItems] = useState<Capture[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async (next?: string) => {
    setBusy(true)
    try {
      const result = await api<CaptureList>(`/library${next ? `?cursor=${encodeURIComponent(next)}` : ''}`)
      setItems(previous => next ? [...previous, ...result.items] : result.items)
      setCursor(result.next_cursor); setError('')
    } catch (failure) { setError(message(failure)) }
    finally { setBusy(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => onTopic('library', () => { if (items.length <= 30) void refresh() }), [refresh, items.length])
  const unfinished = items.some(item => item.state === 'recording' || item.state === 'saving')
  useEffect(() => {
    if (!unfinished) return
    const timer = window.setInterval(() => { void refresh() }, 3000)
    return () => window.clearInterval(timer)
  }, [unfinished, refresh])

  return <>
    <div className="library-toolbar"><p>Live recordings and snapshots saved on this PC.</p><button className="secondary" disabled={busy} onClick={() => { void refresh() }}><RefreshCw size={17} />Refresh Library</button></div>
    {error && <p className="feedback" role="alert">{error}</p>}
    {items.length > 0 ? <div className="library-grid">{items.map(item => <LibraryCard key={item.id} item={item} timezone={timezone} onChanged={() => refresh()} />)}</div> : <section className="panel empty-state"><div className="empty-icon"><Image size={32} /></div><h2>{busy ? 'Opening your library…' : 'No captures saved yet'}</h2><p>Open Live view and use Record or Snapshot while fresh video is playing.</p><a className="text-link" href="#live">Open Live view</a></section>}
    {cursor && <button className="secondary load-more" disabled={busy} onClick={() => { void refresh(cursor) }}>Load more captures</button>}
  </>
}
