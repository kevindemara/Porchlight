import type { CameraList } from '../lib/api'

export type Scope = { camera_ids: string[]; categories: string[]; colors: string[]; directions: string[] }
const groups = [
  { key: 'categories', title: 'Categories', all: 'All categories', limit: 6, values: ['person', 'vehicle', 'animal', 'package', 'other', 'unknown'] },
  { key: 'colors', title: 'Colours', all: 'All colours', limit: 12, values: ['black', 'white', 'gray', 'silver', 'blue', 'red', 'green', 'yellow', 'orange', 'brown', 'beige', 'other'] },
  { key: 'directions', title: 'Directions', all: 'All directions', limit: 6, values: ['left_to_right', 'right_to_left', 'toward_camera', 'away_from_camera', 'stationary', 'unknown'] },
] as const

export default function RuleScope({ value, cameras, onChange, disabled }: {
  value: Scope; cameras: CameraList['items']; onChange: (update: Partial<Scope>) => void; disabled: boolean
}) {
  const cameraChoices = cameras.map(camera => ({ id: camera.id, name: `${camera.name} · ${camera.network_name}` }))
  value.camera_ids.filter(id => !cameraChoices.some(camera => camera.id === id)).forEach((id, index) => cameraChoices.push({ id, name: `Unavailable camera · saved selection ${index + 1}` }))
  const choose = (key: keyof Scope, id: string, checked: boolean) => onChange({ [key]: checked ? [...value[key], id] : value[key].filter(item => item !== id) })
  const choices = (key: keyof Scope, title: string, all: string, limit: number, options: { id: string; name: string }[]) => <details className="rule-choice">
    <summary>{title}: {value[key].length ? `${value[key].length} selected` : all}</summary>
    <fieldset disabled={disabled}><legend>Choose {title.toLowerCase()}</legend><div className="rule-choice-options">
      {options.map(option => <label className="checkbox-label" key={option.id}><input type="checkbox" checked={value[key].includes(option.id)} disabled={!value[key].includes(option.id) && value[key].length >= limit} onChange={event => choose(key, option.id, event.target.checked)} />{option.name}</label>)}
    </div><button className="secondary" type="button" onClick={() => onChange({ [key]: [] })}>{all}</button></fieldset>
  </details>
  return <div className="rule-scope" aria-label="Rule object and camera choices">
    <p className="helper">Choose any matching value within each group. Category, colour and direction must describe the same object. Leaving a group empty matches all its values.</p>
    {choices('camera_ids', 'Cameras', 'All cameras', 32, cameraChoices)}
    {groups.map(group => <div key={group.key}>{choices(group.key, group.title, group.all, group.limit, group.values.map(id => ({ id, name: id.replaceAll('_', ' ') })))}</div>)}
  </div>
}
