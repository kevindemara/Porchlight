import { useState } from 'react'
import type { AnalysisView } from '../lib/api'

function Sample({ eventId, revision, frame, onSeek }: {
  eventId: string; revision: number; frame: NonNullable<AnalysisView['evidence_frames']>[number]; onSeek?: (seconds: number) => void
}) {
  const [failed, setFailed] = useState(false)
  const [retry, setRetry] = useState(0)
  const label = `${(frame.offset_ms / 1000).toFixed(1)}s`
  return <div className="evidence-sample">
    <button className="evidence-preview" disabled={!onSeek} aria-label={`Review sampled frame at ${label}`} onClick={() => onSeek?.(frame.offset_ms / 1000)}>
      {failed ? <span className="evidence-missing">Image unavailable</span> : <img src={`/api/v1/events/${eventId}/analysis/${revision}/frames/${frame.frame_id}?retry=${retry}`} alt={`AI input frame at ${label}`} onError={() => setFailed(true)} />}
      <span>{label}</span>
    </button>
    {failed && <button className="text-link" onClick={() => { setFailed(false); setRetry(value => value + 1) }}>Retry image</button>}
  </div>
}

export function EvidenceStrip({ eventId, analysis, onSeek }: { eventId: string; analysis: AnalysisView; onSeek?: (seconds: number) => void }) {
  if (!analysis.evidence_frames?.length) return null
  return <section className="evidence-section" aria-label="Images used for AI analysis">
    <h3>AI analysis images</h3><p className="helper">These images were used for the scene description. Face detection checks its own, more closely spaced frames and shows that count below. Select a moment to review it in the recording.</p>
    <div className="evidence-strip">{analysis.evidence_frames.map(frame => <Sample key={`${analysis.revision}:${frame.frame_id}`} eventId={eventId} revision={analysis.revision} frame={frame} onSeek={onSeek} />)}</div>
  </section>
}
