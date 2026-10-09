import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { type CameraList } from '../lib/api'
import { CameraControls } from './CameraControls'

export default function NetworkControlsDialog({ camera, timezone, onSaved, onClose }: {
  camera: CameraList['items'][number]; timezone: string; onSaved: () => Promise<void>; onClose: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef(document.activeElement as HTMLElement | null)
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => {
      element.close()
      window.requestAnimationFrame(() => { if (opener.current?.isConnected) opener.current.focus({ preventScroll: true }) })
    }
  }, [])
  return <dialog ref={dialog} className="event-dialog network-dialog" aria-labelledby="network-title" onCancel={event => { event.preventDefault(); onClose() }} onKeyDown={event => {
    if (event.key !== 'Tab') return
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')).filter(control => control.tabIndex >= 0 && control.getClientRects().length)
    const first = controls[0], last = controls.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }}>
    <div className="dialog-heading"><div><span className="eyebrow">Network controls</span><h2 id="network-title">{camera.network_name}</h2></div>
      <button className="icon-button" aria-label="Close network controls" autoFocus onClick={onClose}><X size={20} /></button>
    </div>
    <div className="network-dialog-body"><p className="network-observed-state">Current state: <strong>{camera.observed_armed == null ? 'Unknown' : camera.observed_armed ? 'Armed' : 'Disarmed'}</strong></p>
      <CameraControls camera={camera} timezone={timezone} onSaved={onSaved} scope="network" />
    </div>
  </dialog>
}
