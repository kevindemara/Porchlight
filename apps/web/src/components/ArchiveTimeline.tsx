import { Fragment, useMemo } from 'react'
import { ChevronRight, Star } from 'lucide-react'
import { analysisLabel, sourceLabel, type CameraList, type Event, type Health } from '../lib/api'
import RecordingThumbnail from './RecordingThumbnail'
import WindowedList from './WindowedList'
import ActivityCapture from './ActivityCapture'

export function ArchiveCoverage({ health }: { health: Health | null }) {
  if (!health) return null
  const listing = health.checks?.find(check => check.key === 'listing')
  const workers = health.checks?.filter(check => ['worker_recordings', 'worker_local_recordings'].includes(check.key)) ?? []
  const stopped = workers.some(check => check.state === 'unavailable')
  const issue = stopped ? 'A recording worker needs attention.' : listing?.state === 'disabled' ? 'Recording sync is paused.' : listing?.state === 'unavailable' ? 'Some recording checks need attention.' : health.blink.state !== 'ready' ? 'The Blink connection is unavailable.' : null
  return issue ? <aside className="notice coverage-note" aria-label="Recording coverage"><strong>{issue}</strong><p>Saved recordings remain available. Activity may be incomplete during a retrieval interruption. Review Readiness in Settings.</p></aside> : null
}

export function ArchiveTimeline({ events, cameras, timezone, onRecording, onCaptureChanged }: {
  events: Event[]; cameras: CameraList['items']; timezone: string; onRecording: (id: string) => void; onCaptureChanged: () => Promise<void>
}) {
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' })
  const day = (event: Event) => formatter.format(new Date(event.captured_at ?? event.discovered_at))
  const names = new Map(cameras.map(camera => [camera.id, camera.name]))
  const keys = useMemo(() => events.map(event => `${event.capture ? 'capture' : 'event'}:${event.id}`), [events])
  return <WindowedList keys={keys} renderRow={index => { const event = events[index]; return <Fragment>
    {(index === 0 || day(events[index - 1]) !== day(event)) && <h2 className="timeline-date">{new Date(event.captured_at ?? event.discovered_at).toLocaleDateString(undefined, { timeZone: timezone, weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</h2>}
    {event.capture ? <ActivityCapture capture={event.capture} timezone={timezone} onChanged={onCaptureChanged} /> : <button className="event-card" onClick={click => { click.currentTarget.focus({ preventScroll: true }); onRecording(event.id) }}><RecordingThumbnail mediaId={event.media_id} />
      <div className="event-copy"><span className="eyebrow">{event.camera_id && names.get(event.camera_id) ? `${names.get(event.camera_id)} · ` : ''}{sourceLabel(event)}</span>
        <h3>{event.summary ?? (event.media_type === 'image/jpeg' ? 'Imported image' : event.source_type === 'manual_import' ? 'Imported recording' : 'Camera recording')}</h3>
        {!!event.recognized_people?.length && <p className="event-provenance">Possible face match: {event.recognized_people.join(', ')}</p>}
        <p>{event.captured_at ? new Date(event.captured_at).toLocaleString(undefined, { timeZone: timezone }) : `Saved ${new Date(event.discovered_at).toLocaleString(undefined, { timeZone: timezone })} · recording time unknown`}</p>
        {!!event.object_categories?.length && <span className="object-chips">{event.object_categories.map(category => <span key={category}>{category === 'unknown' ? 'Uncertain' : category}</span>)}</span>}
        {(event.corrected_summary || event.labels_source === 'owner') && <p className="event-provenance">Owner reviewed</p>}{event.historical && <p className="event-provenance">Historical import · alerts paused</p>}{event.note && <p className="event-note">{event.note}</p>}
      </div><div className="event-meta"><span>{event.media_type === 'image/jpeg' ? 'Image' : `${event.duration_seconds.toFixed(1)}s`}</span><span className="badge">{analysisLabel(event.analysis_status)}</span>{event.favourite && <Star size={16} aria-label="Favourite recording" />}</div><ChevronRight size={18} />
    </button>}
  </Fragment> }} />
}
