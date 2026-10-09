import { useEffect, useState } from 'react'
import { Camera, ShieldCheck, Video } from 'lucide-react'
import { type CameraList } from '../lib/api'
import LiveView from './LiveView'
import CameraGroups from './CameraGroups'
import NetworkControlsDialog from './NetworkControlsDialog'

export default function LivePage({ cameras, timezone, onSaved, onRecording }: {
  cameras: CameraList['items']; timezone: string; onSaved: () => Promise<void>; onRecording: (id: string) => void
}) {
  const [selectedId, setSelectedId] = useState('')
  const [networkCameraId, setNetworkCameraId] = useState<string | null>(null)
  const [manage, setManage] = useState(() => new URLSearchParams(location.hash.split('?')[1] ?? '').get('manage') === '1')
  useEffect(() => {
    const changed = () => { if (new URLSearchParams(location.hash.split('?')[1] ?? '').get('manage') === '1') setManage(true) }
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const camera = cameras.find(item => item.id === selectedId)
    ?? cameras.find(item => item.live_view === 'experimental') ?? cameras[0]

  if (!camera) return <section className="panel empty-state">
    <div className="empty-icon"><Video size={32} strokeWidth={1.5} /></div>
    <h2>No cameras connected yet</h2>
    <p>Connect Blink in Settings to check which cameras support live view.</p>
    <a className="text-link" href="#settings">Open Settings</a>
  </section>

  return <>
    <div className="live-page-tools"><div className="live-camera-picker">
      <label htmlFor="live-camera">Camera</label>
      <select id="live-camera" value={camera.id} onChange={event => { setNetworkCameraId(null); setSelectedId(event.target.value) }}>
        {cameras.map(item => <option key={item.id} value={item.id}>{item.name}{item.live_view !== 'experimental' ? ' · Live view unavailable' : ''}</option>)}
      </select>
    </div><div className="live-page-actions">
      <button className="secondary" aria-haspopup="dialog" aria-label={`Network controls · ${camera.observed_armed == null ? 'Unknown' : camera.observed_armed ? 'Armed' : 'Disarmed'}`} onClick={() => setNetworkCameraId(camera.id)}><ShieldCheck size={17} />Network · {camera.observed_armed == null ? 'Unknown' : camera.observed_armed ? 'Armed' : 'Disarmed'}</button>
      <button className="secondary" aria-expanded={manage} aria-controls="camera-management" onClick={() => setManage(value => !value)}><Camera size={17} />Manage cameras</button>
    </div></div>
    <section id="camera-management" aria-label="Camera management" hidden={!manage}>
      <CameraGroups cameras={cameras} timezone={timezone} onSaved={onSaved} onRecording={onRecording} networkControls={false} />
      <a className="text-link" href="#settings?section=cameras">Connection and recording settings</a>
    </section>
    {networkCameraId === camera.id && <NetworkControlsDialog camera={camera} timezone={timezone} onSaved={onSaved} onClose={() => setNetworkCameraId(null)} />}
    {camera.live_view === 'experimental' ? <LiveView key={camera.id} camera={camera} />
      : <section className="panel empty-state"><div className="empty-icon"><Video size={32} /></div>
        <h2>Live view unavailable</h2><p>{camera.name} does not support live view through its current connection.</p>
        <a className="text-link" href="#activity">View saved recordings</a>
      </section>}
  </>
}
