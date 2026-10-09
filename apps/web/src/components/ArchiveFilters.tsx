import type { CameraList, EventFilters } from '../lib/api'

export type FilterDraft = Record<'camera_id' | 'category' | 'color' | 'direction' | 'action' | 'source' | 'analysis' | 'start' | 'end', string>
export const emptyFilters: FilterDraft = { camera_id: '', category: '', color: '', direction: '', action: '', source: '', analysis: '', start: '', end: '' }

export function draftFromFilters(filters: EventFilters): FilterDraft {
  const draft = { ...emptyFilters }
  for (const key of Object.keys(draft) as (keyof FilterDraft)[]) {
    const value = filters[key]
    if (!value) continue
    if (key === 'start' || key === 'end') {
      const date = new Date(value)
      // datetime-local controls explicitly use the browser/device timezone.
      draft[key] = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 19)
    } else draft[key] = value
  }
  return draft
}

export default function ArchiveFilters({ value, cameras, onChange, onClear }: {
  value: FilterDraft; cameras: CameraList['items']; onChange: (value: FilterDraft) => void; onClear: () => void
}) {
  const select = (key: keyof FilterDraft, label: string, options: string[]) => <label>{label}<select value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })}>
    <option value="">All</option>{options.map(option => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}
  </select></label>
  return <div className="panel archive-tool-panel">
    <div className="filter-grid">
      <label>Camera<select value={value.camera_id} onChange={e => onChange({ ...value, camera_id: e.target.value })}><option value="">All cameras</option>{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select></label>
      {select('category', 'Observed category', ['person', 'vehicle', 'animal', 'package', 'other', 'unknown'])}
      {select('color', 'Observed colour', ['black', 'white', 'gray', 'silver', 'blue', 'red', 'green', 'yellow', 'orange', 'brown', 'beige', 'other'])}
      {select('direction', 'Observed direction', ['left_to_right', 'right_to_left', 'toward_camera', 'away_from_camera', 'stationary', 'unknown'])}
      {select('action', 'Observed action', ['visible', 'moving', 'passing', 'approaching', 'departing', 'stopping', 'parked', 'placing_object', 'picking_up_object', 'unknown'])}
      {select('source', 'Recording source', ['blink_cloud', 'blink_local', 'manual_import', 'live_capture', 'live_recording', 'live_snapshot'])}
      {select('analysis', 'Analysis status', ['not_analyzed', 'queued', 'analyzing', 'analyzed', 'analysis_failed'])}
      {(['start', 'end'] as const).map(key => <label key={key}>{key === 'start' ? 'From' : 'Until'} (device time)<input type="datetime-local" value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })} /></label>)}
    </div><p className="helper">Object filters use your labels when supplied, otherwise the latest validated AI observation. Unanalyzed clips remain in the archive. Until is exclusive.</p>
    <button className="secondary" type="button" onClick={onClear}>Clear filters</button>
  </div>
}
