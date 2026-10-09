import { useState } from 'react'
import type { CameraList } from '../lib/api'
import CameraCard from './CameraCard'
import { CameraControls } from './CameraControls'

type Camera = CameraList['items'][number]
export default function CameraGroups({ cameras, timezone, onSaved, onRecording, networkControls = true }: {
  cameras: Camera[]; timezone: string; onSaved: () => Promise<void>; onRecording: (id: string) => void; networkControls?: boolean
}) {
  const [grouping, setGrouping] = useState('network')
  const groups = new Map<string, { name: string; cameras: Camera[] }>()
  for (const camera of cameras) {
    const name = grouping === 'network' ? camera.network_name : camera.group?.trim() || 'Ungrouped cameras'
    // Cached inventories predating network IDs fall back to their network label.
    const key = grouping === 'network' ? camera.network_id ?? `cached:${name}` : name
    const group = groups.get(key) ?? { name, cameras: [] }
    group.cameras.push(camera); groups.set(key, group)
  }
  const repeatedNames = new Map<string, number>()
  return <div className="camera-groups">
    <label className="camera-group-selector">Arrange cameras by<select value={grouping} onChange={event => setGrouping(event.target.value)}><option value="network">Blink network</option><option value="local">Local group</option></select></label>
    {[...groups.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name) || a[0].localeCompare(b[0])).map(([key, group]) => {
      const sameName = [...groups.values()].filter(value => value.name === group.name).length > 1
      const number = (repeatedNames.get(group.name) ?? 0) + 1
      repeatedNames.set(group.name, number)
      const name = `${group.name}${sameName ? ` · network ${number}` : ''}`
      const armed = group.cameras.every(camera => camera.observed_armed === true) ? 'Armed' : group.cameras.every(camera => camera.observed_armed === false) ? 'Disarmed' : 'Unknown'
      return <section className="camera-group" key={key} aria-label={name}>
        <div className="camera-group-heading"><h2>{name}</h2><span className="badge">{grouping === 'network' ? `${armed} · ` : ''}{group.cameras.length} {group.cameras.length === 1 ? 'camera' : 'cameras'}</span></div>
        {grouping === 'network' && networkControls && <CameraControls key={group.cameras[0].id} camera={{ ...group.cameras[0], observed_armed: armed === 'Unknown' ? null : armed === 'Armed' }} timezone={timezone} onSaved={onSaved} scope="network" />}
        <div className="camera-grid">{group.cameras.map(camera => <CameraCard key={camera.id} camera={camera} networkControlsAtGroup={grouping === 'network'} timezone={timezone} onSaved={onSaved} onRecording={onRecording} />)}</div>
      </section>
    })}
  </div>
}
