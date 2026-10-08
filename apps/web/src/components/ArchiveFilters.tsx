import type { CameraList } from '../lib/api'

export type FilterDraft = Record<'camera_id' | 'category' | 'color' | 'direction' | 'action' | 'source' | 'analysis' | 'start' | 'end', string>
export const emptyFilters: FilterDraft = { camera_id: '', category: '', color: '', direction: '', action: '', source: '', analysis: '', start: '', end: '' }

export default function ArchiveFilters({ value, cameras, onChange }: {
  value: FilterDraft; cameras: CameraList['items']; onChange: (value: FilterDraft) => void
}) {
  const active = Object.values(value).filter(Boolean).length
  const select = (key: keyof FilterDraft, label: string, options: string[]) => <label>{label}<select value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })}>
    <option value="">All</option>{options.map(option => <option key={option} value={option}>{option.replaceAll('_', ' ')}</option>)}
  </select></label>
  return <details className="panel archive-filters"><summary>Filters{active > 0 ? ` · ${active} active` : ''}</summary>
    <div className="filter-grid">
      <label>Camera<select value={value.camera_id} onChange={e => onChange({ ...value, camera_id: e.target.value })}><option value="">All cameras</option>{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select></label>
      {select('category', 'Observed category', ['person', 'vehicle', 'animal', 'package', 'other', 'unknown'])}
      {select('color', 'Observed colour', ['black', 'white', 'gray', 'silver', 'blue', 'red', 'green', 'yellow', 'orange', 'brown', 'beige', 'other'])}
      {select('direction', 'Observed direction', ['left_to_right', 'right_to_left', 'toward_camera', 'away_from_camera', 'stationary', 'unknown'])}
      {select('action', 'Observed action', ['visible', 'moving', 'passing', 'approaching', 'departing', 'stopping', 'parked', 'placing_object', 'picking_up_object', 'unknown'])}
      {select('source', 'Recording source', ['blink_cloud', 'blink_local', 'manual_import'])}
      {select('analysis', 'Analysis status', ['not_analyzed', 'queued', 'analyzing', 'analyzed', 'analysis_failed'])}
      {(['start', 'end'] as const).map(key => <label key={key}>{key === 'start' ? 'From' : 'Until'} (device time)<input type="datetime-local" value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })} /></label>)}
    </div><p className="helper">Object filters use your labels when supplied, otherwise the latest validated AI observation. Unanalyzed clips remain in the archive. Until is exclusive.</p>
    <button className="secondary" type="button" onClick={() => onChange(emptyFilters)}>Clear filters</button>
  </details>
}
