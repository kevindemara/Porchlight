import { useEffect, useRef, useState } from 'react'
import { Download, Sparkles, Star, Trash2, X } from 'lucide-react'
import { analysisLabel, api, message, sourceLabel, type AnalysisJob, type AnalysisView, type Event } from '../lib/api'
import { EvidenceStrip } from './EvidenceStrip'
import LabelEditor from './LabelEditor'
import FaceDetectionPanel from './FaceDetectionPanel'

export function EventDetail({ event, timezone, aiReady, onClose, onSaved }: {
  event: Event; timezone: string; aiReady: boolean; onClose: () => void; onSaved: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null)
  const returnList = useRef(opener.current?.closest<HTMLElement>('.windowed-list') ?? null)
  const returnPosition = useRef(opener.current?.closest<HTMLElement>('.window-row')?.getAttribute('aria-posinset'))
  const image = event.media_type === 'image/jpeg'
  const [note, setNote] = useState(event.note)
  const [favourite, setFavourite] = useState(event.favourite)
  const [correction, setCorrection] = useState(event.corrected_summary ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const video = useRef<HTMLVideoElement>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [current, setCurrent] = useState(event)
  const [analysis, setAnalysis] = useState<AnalysisView | null>(null)
  const savedCallback = useRef(onSaved)
  useEffect(() => { savedCallback.current = onSaved }, [onSaved])
  useEffect(() => {
    const controller = new AbortController()
    let previous = event.analysis_status
    async function update() {
      try {
        const [latest, detail] = await Promise.all([
          api<Event>(`/events/${event.id}`, { signal: controller.signal }),
          api<AnalysisView | null>(`/events/${event.id}/analysis`, { signal: controller.signal }),
        ])
        if (controller.signal.aborted) return
        setCurrent(latest); setAnalysis(detail)
        if (latest.analysis_status !== previous) savedCallback.current()
        previous = latest.analysis_status
      } catch { /* Local playback stays available during a status outage. */ }
    }
    void update()
    const timer = window.setInterval(() => { void update() }, 3000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [event.id, event.analysis_status])
  async function analyze() {
    setBusy(true); setFeedback('')
    try {
      const job = await api<AnalysisJob>(`/events/${event.id}/analyze`, { method: 'POST', body: JSON.stringify({ reanalyze: current.analysis_status === 'analyzed' }) })
      setCurrent(previous => ({ ...previous, analysis_status: job.status === 'done' ? 'analyzed' : 'queued' }))
      setFeedback(job.status === 'done' ? 'This analysis is already available.' : 'Analysis queued. You can keep browsing.'); onSaved()
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => { element.close(); window.requestAnimationFrame(() => { if (opener.current?.isConnected) opener.current.focus({ preventScroll: true }); else returnList.current?.querySelector<HTMLButtonElement>(`.window-row[aria-posinset="${returnPosition.current}"] button`)?.focus({ preventScroll: true }) }) }
  }, [])
  async function save() {
    setBusy(true); setFeedback('')
    try {
      const saved = await api<Event>(`/events/${event.id}/annotation`, { method: 'PATCH', body: JSON.stringify({ note, favourite, corrected_summary: correction || null }) })
      setCurrent(saved)
      setFeedback('Saved.'); onSaved()
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  async function remove() {
    setBusy(true); setFeedback('')
    try {
      video.current?.pause(); video.current?.removeAttribute('src'); video.current?.load()
      await api(`/events/${event.id}`, { method: 'DELETE' }); onSaved(); onClose()
    } catch (err) { setFeedback(message(err)); if (video.current) video.current.src = `/api/v1/media/${event.media_id}` }
    finally { setBusy(false) }
  }
  return <dialog ref={dialog} onCancel={onClose} className="event-dialog" aria-labelledby="event-title">
    <div className="dialog-heading"><div><span className="eyebrow">{sourceLabel(event)}</span><h2 id="event-title">Recording details</h2></div>
      <button className="icon-button" aria-label="Close recording" onClick={onClose}><X /></button></div>
    {image ? <img className="detail-image" src={`/api/v1/media/${event.media_id}`} alt="Imported image" /> : <video ref={video} controls preload="metadata" src={`/api/v1/media/${event.media_id}`} />}
    <div className="detail-body">
      <p>{current.summary ?? 'This recording has not been analyzed.'}</p>
      {!!current.recognized_people?.length && <p className="helper">Possible face match: {current.recognized_people.join(', ')}.</p>}
      {!!current.recognized_people?.length && current.ai_summary && current.summary !== current.ai_summary && !current.corrected_summary && current.labels_source !== 'owner' && <details><summary>Original AI description</summary><p>{current.ai_summary}</p></details>}
      {(current.corrected_summary || current.labels_source === 'owner') && <p className="helper">Your description. Original AI description: {current.ai_summary ?? 'Not available'}</p>}
      <dl><dt>Recorded</dt><dd>{event.captured_at ? new Date(event.captured_at).toLocaleString(undefined, { timeZone: timezone }) : 'Unknown · recording time was not supplied'}</dd>
        <dt>{event.source_type === 'manual_import' ? 'Imported' : 'Discovered'}</dt><dd>{new Date(event.discovered_at).toLocaleString(undefined, { timeZone: timezone })}</dd>
        {event.historical && <><dt>Historical import</dt><dd>Saved for review. Alerts and automatic AI are disabled for this recording.</dd></>}
        <dt>Analysis</dt><dd>{analysisLabel(current.analysis_status)} · local playback is available</dd></dl>
      {analysis && <div className="notice"><strong>AI-generated description · revision {analysis.revision}</strong><p>{image ? 'Single image' : `${analysis.frame_count} sampled frames`} · {analysis.elapsed_seconds.toFixed(1)} seconds</p>{!!current.recognized_people?.length && <p>Local face recognition suggests {current.recognized_people.join(', ')}. Please verify against the recording.</p>}{analysis.uncertainty.map(item => <p key={item}>{item}</p>)}<details><summary>Analysis details</summary><p>Model: {analysis.model}<br />Workload: {analysis.workload ?? 'balanced'}<br />Model digest: {analysis.model_digest}</p></details></div>}
      {analysis?.entities?.length ? <div className="observation-list">{analysis.entities.map((entity, index) => <p key={index}><strong>{entity.subtype ?? entity.category}</strong> · {entity.actions.join(', ').replaceAll('_', ' ')} · {entity.direction.replaceAll('_', ' ')}{entity.color ? ` · ${entity.color}` : ''}</p>)}</div> : null}
      {analysis && <EvidenceStrip eventId={event.id} analysis={analysis} onSeek={image ? undefined : seconds => { if (video.current) video.current.currentTime = seconds }} />}
      {!image && !analysis?.evidence_frames?.length && analysis?.sample_offsets_ms?.length ? <div className="evidence-times"><span>Sampled moments</span>{analysis.sample_offsets_ms.map(offset => <button className="secondary" key={offset} onClick={() => { if (video.current) video.current.currentTime = offset / 1000 }}>{(offset / 1000).toFixed(1)}s</button>)}</div> : null}
      <button className="secondary" onClick={analyze} disabled={!aiReady || busy || ['queued', 'analyzing'].includes(current.analysis_status)}><Sparkles size={17} />{current.analysis_status === 'analyzed' ? 'Analyze again' : current.analysis_status === 'analysis_failed' ? 'Retry analysis' : 'Analyze recording'}</button>
      <p className="helper">{aiReady ? 'Analyzing this recording leaves your automatic-analysis setting unchanged.' : 'Select and test a local vision model in Settings to analyze this recording.'}</p>
      <FaceDetectionPanel eventId={event.id} onSeek={image ? undefined : seconds => { if (video.current) video.current.currentTime = seconds }} />
      <LabelEditor event={current} analysis={analysis} onSaved={saved => { setCurrent(saved); onSaved() }} />
      <label htmlFor="event-note">Your notes</label>
      <textarea id="event-note" value={note} onChange={e => setNote(e.target.value)} maxLength={2000} rows={3} placeholder="Add a note to help find this recording later" />
      <label htmlFor="event-correction">Your description</label><textarea id="event-correction" value={correction} onChange={e => setCorrection(e.target.value)} maxLength={500} rows={2} placeholder="Correct the description here; the AI revision is preserved" />
      <div className="detail-actions">
        <button className={favourite ? 'secondary selected' : 'secondary'} aria-pressed={favourite} onClick={() => setFavourite(v => !v)}><Star size={17} />{favourite ? 'Favourite' : 'Add to favourites'}</button>
        <a className="secondary button-link" href={`/api/v1/media/${event.media_id}`} download={`porchlight-${event.id}.${image ? 'jpg' : 'mp4'}`}><Download size={17} />Download original</a>
        <button className="primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button>
      </div>
      {confirmDelete ? <div className="notice"><strong>Delete this local recording?</strong><p>Its local description and notes will also be removed. Blink's copy is unaffected. Shared video is kept if another recording uses it.</p><div className="detail-actions"><button className="secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>Keep recording</button><button className="danger" disabled={busy} onClick={remove}>Delete local recording</button></div></div> : <button className="text-link" disabled={busy} onClick={() => setConfirmDelete(true)}><Trash2 size={16} />Delete local recording</button>}
      {feedback && <p role="status" className="feedback">{feedback}</p>}
    </div>
  </dialog>
}
