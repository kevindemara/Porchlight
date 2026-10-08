import { useRef, useState } from 'react'
import { Download, Image, Star, Trash2, Video } from 'lucide-react'
import { api, message, type Capture } from '../lib/api'

export default function LibraryCard({ item, timezone, onChanged }: {
  item: Capture; timezone: string; onChanged: () => Promise<void>
}) {
  const video = useRef<HTMLVideoElement>(null)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ready = item.state === 'ready'
  const finished = ready || item.state === 'failed'
  const url = `/api/v1/library/${item.id}/media`
  async function favourite() {
    setBusy(true); setError('')
    try { await api(`/library/${item.id}/favourite`, { method: 'PATCH', body: JSON.stringify({ favourite: !item.favourite }) }); await onChanged() }
    catch (failure) { setError(message(failure)) }
    finally { setBusy(false) }
  }
  async function remove() {
    setBusy(true); setError('')
    try {
      video.current?.pause(); video.current?.removeAttribute('src'); video.current?.load()
      await api(`/library/${item.id}`, { method: 'DELETE' }); await onChanged()
    } catch (failure) { setError(message(failure)); if (video.current) video.current.src = url }
    finally { setBusy(false) }
  }
  return <article className="panel library-card">
    {ready ? item.kind === 'recording'
      ? <video ref={video} controls muted preload="metadata" poster={`/api/v1/library/${item.id}/thumbnail`} src={url} aria-label={`Recording from ${item.camera_name}`} />
      : <a href={url} target="_blank" rel="noreferrer" aria-label={`Open snapshot from ${item.camera_name}`}><img src={url} alt={`Snapshot from ${item.camera_name}`} loading="lazy" /></a>
      : <div className="library-placeholder">{item.kind === 'recording' ? <Video size={28} /> : <Image size={28} />}<span>{item.state === 'recording' ? 'Recording…' : item.state === 'saving' ? 'Saving…' : 'Capture failed'}</span></div>}
    <div className="library-card-body"><span className="eyebrow">Local live {item.kind === 'recording' ? 'recording' : 'snapshot'}</span><h2>{item.camera_name}</h2><p>Saved {new Date(item.saved_at).toLocaleString(undefined, { timeZone: timezone })}</p>
      {item.duration_seconds !== null && <p>{item.duration_seconds.toFixed(1)} seconds · Video only</p>}
      {item.safe_error && <p role="status">{item.safe_error}</p>}
      <div className="detail-actions">{ready && <a className="secondary button-link" href={url} download={`porchlight-${item.kind}-${item.id}.${item.kind === 'recording' ? 'mp4' : 'jpg'}`}><Download size={17} />Download {item.kind}</a>}
        <button className={item.favourite ? 'secondary selected' : 'secondary'} aria-pressed={item.favourite ?? false} disabled={busy} onClick={favourite}><Star size={17} />Favourite capture</button>
      </div>
      {finished && (confirm ? <div className="notice"><strong>Delete this local capture?</strong><p>Its saved file will be removed from the Library. Exports remain.</p><div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>Keep capture</button><button className="danger" disabled={busy} onClick={remove}>Delete capture</button></div></div> : <button className="text-link" disabled={busy} onClick={() => setConfirm(true)}><Trash2 size={16} />Delete local capture</button>)}
      {error && <p className="feedback" role="alert">{error}</p>}
    </div>
  </article>
}
