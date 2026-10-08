import { useState } from 'react'
import { Camera } from 'lucide-react'
import { analysisLabel, api, message, type CameraList } from '../lib/api'
import { CameraControls } from './CameraControls'

type Props = {
  camera: CameraList['items'][number]
  timezone: string
  onRecording: (eventId: string) => void
  onSaved: () => Promise<void>
  networkControlsAtGroup?: boolean
}

export default function CameraCard({ camera, timezone, onRecording, onSaved, networkControlsAtGroup = false }: Props) {
  const [failedSource, setFailedSource] = useState('')
  const [name, setName] = useState(camera.name)
  const [group, setGroup] = useState(camera.group ?? '')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  async function save() {
    setBusy(true); setFeedback('')
    try { await api(`/cameras/${camera.id}/metadata`, { method: 'PATCH', body: JSON.stringify({ name, group }) }); await onSaved(); setFeedback('Local camera details saved.') }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  const recording = camera.latest_recording
  const source = recording ? `/api/v1/media/${recording.media_id}/thumbnail` : ''
  return <section className="panel camera-card">
    {recording ? <figure className="camera-preview">
      <button className="camera-preview-button" aria-label={`Open latest recording from ${camera.name}`} onClick={() => onRecording(recording.event_id)}>
        {failedSource === source ? <span className="camera-placeholder"><Camera size={32} /><span>Preview unavailable · open recording</span></span>
          : <img src={source} alt={`Latest recorded clip from ${camera.name}`} onError={() => setFailedSource(source)} />}
      </button>
      <figcaption><strong>Latest saved clip</strong><span>{recording.captured_at
        ? `Recorded ${new Date(recording.captured_at).toLocaleString(undefined, { timeZone: timezone })}`
        : `Saved ${new Date(recording.discovered_at).toLocaleString(undefined, { timeZone: timezone })} · recording time unknown`}</span></figcaption>
    </figure> : <div className="camera-placeholder"><Camera size={32} /><span>No saved recordings yet</span></div>}
    <div className="camera-card-body">
      <span className="eyebrow">{camera.network_name}</span><h2>{camera.name}</h2>
      <p>Observed network state: {camera.observed_armed === null ? 'unknown' : camera.observed_armed ? 'armed' : 'disarmed'}</p>
      <span className="badge">{camera.recording_access === 'cloud_archived' || camera.recording_access === 'local_archived' ? 'Recording access verified' : 'Recording access unverified'}</span>
      {camera.recording_access === 'cloud_archived' && <p className="helper">Cloud clips saved locally</p>}
      {camera.recording_access === 'local_archived' && <p className="helper">Sync Module clips saved locally · No-plan access still unverified</p>}
      {camera.group && <p className="helper">Group: {camera.group}</p>}
      <p className="camera-metrics">Battery: {camera.battery_state ?? 'unknown'} · Temperature: {camera.temperature_c == null ? 'unknown' : `${camera.temperature_c} °C`}</p>
      {camera.observed_at && <p className="helper">Last observed {new Date(camera.observed_at).toLocaleString(undefined, { timeZone: timezone })}</p>}
      {recording && <div className="camera-latest"><span className="badge">{analysisLabel(recording.analysis_status)}</span>{recording.summary && <p>{recording.summary_source === 'owner' ? 'Your description' : 'AI description'}: {recording.summary}</p>}</div>}
      <CameraControls camera={camera} timezone={timezone} onSaved={onSaved} scope={networkControlsAtGroup ? 'motion' : 'all'} />
      <details className="camera-edit"><summary>Camera details</summary><label>Local name<input value={name} maxLength={120} onChange={e => setName(e.target.value)} /></label><label>Group<input value={group} maxLength={80} onChange={e => setGroup(e.target.value)} placeholder="For example, front yard" /></label><button className="secondary" disabled={busy} onClick={save}>Save camera details</button><p className="helper">Names and groups are stored in Porchlight.</p>{feedback && <p role="status">{feedback}</p>}</details>
    </div>
  </section>
}
