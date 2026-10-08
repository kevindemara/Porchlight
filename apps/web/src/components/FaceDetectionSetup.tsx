import { useEffect, useState } from 'react'
import { ScanFace } from 'lucide-react'
import { api, message, type FaceStatus } from '../lib/api'
import FacePeopleSetup from './FacePeopleSetup'

export default function FaceDetectionSetup({ onPeopleChanged }: { onPeopleChanged?: () => void }) {
  const [status, setStatus] = useState<FaceStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let pending = false
    async function load() {
      if (pending) return
      pending = true
      try {
        const result = await api<FaceStatus>('/face-detection/status', { signal: controller.signal })
        if (!controller.signal.aborted) { setStatus(result); setFeedback('') }
      } catch (err) { if (!controller.signal.aborted) setFeedback(message(err)) }
      finally { pending = false }
    }
    void load()
    const timer = window.setInterval(() => { void load() }, 10000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [])
  async function toggle(enabled: boolean) {
    setBusy(true); setFeedback('')
    try { setStatus(await api<FaceStatus>('/face-detection/control', { method: 'PUT', body: JSON.stringify({ enabled }) })) }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  async function toggleAutoEnroll(enabled: boolean) {
    setBusy(true); setFeedback('')
    try { setStatus(await api<FaceStatus>('/face-detection/auto-enroll', { method: 'PUT', body: JSON.stringify({ enabled }) })) }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section">
    <div className="section-heading"><ScanFace size={22} /><div><h2>Detection settings</h2><p>See when faces are visible in a recording.</p></div></div>
    <p className="helper">YuNet and optional SFace run on this PC’s CPU, separately from Qwen. You can name detected faces below to match clear faces in future clips.</p>
    <p role="status">{status?.message ?? 'Checking the optional detector…'}</p>
    <label className="checkbox-label"><input type="checkbox" checked={status?.enabled ?? false} disabled={busy || !status || (!status.ready && !status.enabled)} onChange={e => { void toggle(e.target.checked) }} />Detect faces in new Blink recordings automatically</label>
    {busy && <p role="status" className="helper">Saving automatic detection…</p>}
    <p className="helper">This switch takes effect immediately. Only new, recent recordings are queued; older clips and manual imports can be checked from their recording details. Turning it off pauses queued automatic work.</p>
    <label className="checkbox-label"><input type="checkbox" checked={status?.auto_enroll_enabled ?? false} disabled={busy || !status?.recognition_ready} onChange={e => { void toggleAutoEnroll(e.target.checked) }} />Automatically add exceptionally strong face matches as samples</label>
    <p className="helper">Requires at least eight images you assigned yourself, two clear matching frames in one recording and a strict match against those owner-assigned images. Adds at most one sample per person per recording. Suggestions are still fallible; review names in Activity. This applies to future face scans.</p>
    <p className="helper">Detection samples up to 48 frames and may miss faces between them. Counts describe faces in a frame, not unique visitors. Small or blurred faces can be missed.</p>
    {status && <p className="helper">{status.queued} queued · {status.running} detecting · {status.completed} completed · {status.failed} need attention</p>}
    {status && !status.ready && <details><summary>Set up the optional detector</summary><p className="helper">In the repository, run scripts/enable-face-detection.ps1 to preview the installation. After approving it locally, run it with -Install and restart Porchlight. See docs/FACE_DETECTION.md for model paths and licenses.</p></details>}
    {status && <FacePeopleSetup ready={status.recognition_ready} onPeopleChanged={onPeopleChanged} />}
    {feedback && <p role="alert" className="feedback">{feedback}</p>}
  </section>
}
