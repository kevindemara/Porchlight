import { useEffect, useRef, useState } from 'react'
import { api, message, type CameraCommand, type CameraList } from '../lib/api'

type Operation = CameraCommand['operation']
type Change = { operation: Operation; desired: boolean }
const waiting = (command: CameraCommand | null) => command?.state === 'pending' || command?.state === 'sending'

export function CameraControls({ camera, timezone, onSaved, scope = 'all' }: {
  camera: CameraList['items'][number]; timezone: string; onSaved: () => Promise<void>; scope?: 'all' | 'network' | 'motion'
}) {
  const [command, setCommand] = useState<CameraCommand | null>(null)
  const [confirmation, setConfirmation] = useState<Change | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const saved = useRef(onSaved)
  useEffect(() => { saved.current = onSaved }, [onSaved])
  useEffect(() => {
    const controller = new AbortController()
    void api<CameraCommand | null>(`/cameras/${camera.id}/commands/latest${scope === 'all' ? '' : `?operation=${scope === 'network' ? 'network_armed' : 'motion_enabled'}`}`, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setCommand(result) })
      .catch(() => { /* Camera details remain usable during a command-history outage. */ })
    return () => controller.abort()
  }, [camera.id, scope])
  const pending = waiting(command)
  useEffect(() => {
    if (!command || !pending) return
    const controller = new AbortController()
    let inFlight = false
    const refresh = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const result = await api<CameraCommand>(`/camera-commands/${command.id}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setCommand(result)
        if (!waiting(result)) await saved.current()
      } catch (error) { if (!controller.signal.aborted) setFeedback(message(error)) }
      finally { inFlight = false }
    }
    void refresh(); const timer = window.setInterval(() => { void refresh() }, 2000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [command?.id, pending])
  async function submit(change: Change) {
    setBusy(true); setFeedback(''); setConfirmation(null)
    try {
      const result = await api<CameraCommand>(`/cameras/${camera.id}/commands`, {
        method: 'POST', body: JSON.stringify({ request_id: crypto.randomUUID(), ...change, confirm_disable: !change.desired }),
      })
      setCommand(result)
      if (!waiting(result)) await onSaved()
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function verify() {
    if (!command) return
    setBusy(true); setFeedback('')
    try {
      setCommand(await api<CameraCommand>(`/camera-commands/${command.id}/verify`, { method: 'POST' }))
      await onSaved()
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  function choose(operation: Operation, desired: boolean) {
    if (!desired) setConfirmation({ operation, desired })
    else void submit({ operation, desired })
  }
  const unavailable = busy || pending || !!confirmation
  const content = <>
    <p className="helper">{scope === 'network' ? `Network arming affects every camera in ${camera.network_name}.` : scope === 'motion' ? 'Motion detection affects this camera.' : `Network arming affects every camera in ${camera.network_name}. Motion detection affects this camera.`} Porchlight confirms changes by reading Blink’s state.</p>
    {scope !== 'network' && <p>Motion detection: {camera.observed_motion == null ? 'unknown' : camera.observed_motion ? 'enabled' : 'disabled'}</p>}
    <div className="camera-control-actions">
      {scope !== 'motion' && <button className="secondary" disabled={unavailable || !camera.network_control || camera.observed_armed == null} onClick={() => choose('network_armed', !camera.observed_armed)}>{camera.observed_armed === false ? 'Arm network' : 'Disarm network'}</button>}
      {scope !== 'network' && <button className="secondary" disabled={unavailable || !camera.motion_control || camera.observed_motion == null} onClick={() => choose('motion_enabled', !camera.observed_motion)}>{camera.observed_motion === false ? 'Enable motion detection' : 'Disable motion detection'}</button>}
    </div>
    {((scope !== 'motion' && !camera.network_control) || (scope !== 'network' && !camera.motion_control)) && <p className="helper">Controls without a readable Blink state are unavailable.</p>}
    {confirmation && <div className="control-confirmation" role="group" aria-label="Confirm camera change">
      <p>{confirmation.operation === 'network_armed' ? `Disarm all cameras in ${camera.network_name}?` : `Disable motion detection for ${camera.name}?`} Motion-triggered recordings will stop for the affected cameras until enabled again.</p>
      <div className="camera-control-actions"><button className="secondary" onClick={() => setConfirmation(null)}>Cancel change</button><button className="primary" onClick={() => { void submit(confirmation) }}>Confirm {confirmation.operation === 'network_armed' ? 'disarm' : 'disable motion'}</button></div>
    </div>}
    {command && <div role="status" className="control-status">
      <p>{pending ? 'Command pending · waiting for Blink read-back.' : command.state === 'confirmed' ? 'Blink read-back confirmed this command.' : command.state === 'failed' ? 'The command did not run.' : 'The outcome is unconfirmed. Check Blink’s current state before another change.'}</p>
      <p className="helper">{command.operation === 'network_armed' ? 'Network arming' : 'Motion detection'} · requested {command.desired ? 'on' : 'off'} · observed {command.observed == null ? 'unknown' : command.observed ? 'on' : 'off'} · {new Date(command.created_at).toLocaleString(undefined, { timeZone: timezone })}</p>
      {command.safe_error && <p className="helper">{command.safe_error.replaceAll('_', ' ').toLowerCase()}</p>}
      {command.state === 'unknown' && <button className="secondary" disabled={busy} onClick={() => { void verify() }}>Verify current state</button>}
    </div>}
    {feedback && <p role="alert">{feedback}</p>}
  </>
  return scope === 'network' ? <div className="network-controls" aria-label={`Network controls for ${camera.network_name}`}>{content}</div> : <details className="camera-edit camera-controls"><summary>Camera controls and status</summary>{content}</details>
}
