import { useState } from 'react'
import { Video } from 'lucide-react'
import { type CameraList } from '../lib/api'
import LiveView from './LiveView'

export default function LivePage({ cameras }: { cameras: CameraList['items'] }) {
  const [selectedId, setSelectedId] = useState('')
  const camera = cameras.find(item => item.id === selectedId)
    ?? cameras.find(item => item.live_view === 'experimental') ?? cameras[0]

  if (!camera) return <section className="panel empty-state">
    <div className="empty-icon"><Video size={32} strokeWidth={1.5} /></div>
    <h2>No cameras connected yet</h2>
    <p>Connect Blink in Settings to check which cameras support live view.</p>
    <a className="text-link" href="#settings">Open Settings</a>
  </section>

  return <>
    <div className="live-camera-picker">
      <label htmlFor="live-camera">Camera</label>
      <select id="live-camera" value={camera.id} onChange={event => setSelectedId(event.target.value)}>
        {cameras.map(item => <option key={item.id} value={item.id}>{item.name}{item.live_view !== 'experimental' ? ' · Live view unavailable' : ''}</option>)}
      </select>
    </div>
    {camera.live_view === 'experimental' ? <LiveView key={camera.id} camera={camera} />
      : <section className="panel empty-state"><div className="empty-icon"><Video size={32} /></div>
        <h2>Live view unavailable</h2><p>{camera.name} does not support live view through its current connection.</p>
        <a className="text-link" href="#cameras">View saved recordings</a>
      </section>}
  </>
}
