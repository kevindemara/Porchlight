import { useState } from 'react'
import { type Capture } from '../lib/api'
import LibraryCard from './LibraryCard'

export default function ActivityCapture({ capture, timezone, onChanged }: {
  capture: Capture; timezone: string; onChanged: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  return <details className="activity-capture" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>
      <span className="eyebrow">Local live {capture.kind}</span>
      <strong>Live {capture.kind} from {capture.camera_name}</strong>
      <span>{new Date(capture.saved_at).toLocaleString(undefined, { timeZone: timezone })} · {capture.state}{capture.favourite ? ' · Favourite' : ''}</span>
      <span className="text-link">{open ? 'Close saved' : 'View saved'} {capture.kind}</span>
    </summary>
    {open && <LibraryCard item={capture} timezone={timezone} onChanged={onChanged} />}
  </details>
}
