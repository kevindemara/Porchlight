import { useEffect, useState } from 'react'
import { ScanFace } from 'lucide-react'
import { api, message, type FaceResult, type FaceStatus } from '../lib/api'

export default function FaceDetectionPanel({ eventId, onSeek }: { eventId: string; onSeek?: (seconds: number) => void }) {
  const [status, setStatus] = useState<FaceStatus | null>(null)
  const [result, setResult] = useState<FaceResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let pending = false
    async function load() {
      if (pending) return
      pending = true
      try {
        const [state, detail] = await Promise.all([
          api<FaceStatus>('/face-detection/status', { signal: controller.signal }),
          api<FaceResult>(`/events/${eventId}/faces`, { signal: controller.signal }),
        ])
        if (!controller.signal.aborted) { setStatus(state); setResult(detail) }
      } catch (err) { if (!controller.signal.aborted) setFeedback(message(err)) }
      finally { pending = false }
    }
    void load()
    const timer = window.setInterval(() => { void load() }, 3000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [eventId])
  async function detect() {
    setBusy(true); setFeedback('')
    try { setResult(await api<FaceResult>(`/events/${eventId}/faces`, { method: 'POST', body: JSON.stringify({ reanalyze: !!result?.report }) })) }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  const frames = result?.report?.frames ?? []
  const visible = frames.filter(frame => frame.faces.length > 0)
  const peak = Math.max(0, ...frames.map(frame => frame.faces.length))
  const working = result?.status === 'running' || result?.status === 'queued'
  const known = result?.people ?? {}
  const detectorThreshold = result?.report?.policy === 'yunet-sampled-v3' ? '0.80' : '0.90'
  return <section className="notice face-detection" aria-labelledby="face-detection-title">
    <h3 id="face-detection-title"><ScanFace size={18} />Face detection</h3>
    {result?.report && <>
      <p><strong>{peak ? `Up to ${peak} ${peak === 1 ? 'face' : 'faces'} visible in a sampled frame` : 'No faces detected in sampled frames'}</strong></p>
      {!peak && <p className="helper">A person may still be in the recording. This tool needs a visible face; someone facing away, too far from the camera, or between sampled moments may not be detected. SFace cannot suggest a name without a detected face. For this clip, you can add the name in Your description below; to set up future recognition, choose a recording where the person’s face is clear.</p>}
      <p className="helper">{frames.length} frames sampled · {result.elapsed_seconds?.toFixed(1)} seconds to process. Counts are per frame. Named matches are suggestions to review in the original recording; faces may appear between samples.</p>
      {working && <p className="helper">Showing the previous result while the new request runs.</p>}
      {visible.length > 0 && <div className="face-moments">{visible.map(frame => <div key={frame.offset_ms}>
        {onSeek ? <button className="secondary" onClick={() => onSeek(frame.offset_ms / 1000)} aria-label={`Review faces at ${(frame.offset_ms / 1000).toFixed(1)} seconds`}>{(frame.offset_ms / 1000).toFixed(1)}s</button> : <strong>Image</strong>}
        <span>{frame.faces.length} {frame.faces.length === 1 ? 'face' : 'faces'}{frame.faces.some(face => face.small) ? ' · small face' : ''}{frame.faces.some(face => face.low_sharpness) ? ' · low sharpness' : ''}</span>
        {frame.faces.some(face => face.profile_id && known[face.profile_id]) && <span className="face-match">Possible match: {frame.faces.flatMap(face => face.profile_id && known[face.profile_id] ? [known[face.profile_id]] : []).join(', ')}</span>}
      </div>)}</div>}
      {peak > 0 && !Object.keys(known).length && <p className="helper">{status?.people_count ? 'No saved person matched these faces. Add a sample from the Faces page.' : 'No people have been named yet. Open Faces → Recognize familiar people and label a clear sampled face to include a name in Activity analysis.'}</p>}
      <details><summary>Detection details</summary><p className="helper">YuNet 2023mar · CPU · detector score threshold {detectorThreshold}. Optional SFace matching uses saved local samples. Neither score is measured accuracy or proof of identity. Size and sharpness flags are uncalibrated heuristics on resized frames.</p><p className="helper">Sampled at {frames.map(frame => `${(frame.offset_ms / 1000).toFixed(1)}s`).join(', ')}.</p></details>
    </>}
    <button className="secondary" onClick={() => { void detect() }} disabled={busy || working || !status?.ready}><ScanFace size={17} />{working ? (result?.status === 'running' ? 'Detecting faces…' : 'Face detection queued') : result?.report ? 'Detect faces again' : 'Detect faces'}</button>
    <p className="helper">{status?.ready ? 'Runs locally without changing the automatic-detection setting.' : status?.message ?? 'Checking the optional detector…'}</p>
    {result?.message && <p role="status">{result.message}</p>}
    {result?.status === 'expired' && <p className="helper">Automatic work was paused or became too old. You can request detection here.</p>}
    {feedback && <p role="alert" className="feedback">{feedback}</p>}
  </section>
}
