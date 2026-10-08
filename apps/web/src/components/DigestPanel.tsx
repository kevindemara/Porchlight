import { useState } from 'react'
import { api, message, type DailyDigest } from '../lib/api'

export default function DigestPanel({ timezone, onRecording }: { timezone: string; onRecording: (id: string) => void }) {
  const [day, setDay] = useState(() => new Intl.DateTimeFormat('sv-SE', { timeZone: timezone }).format(new Date()))
  const [digest, setDigest] = useState<DailyDigest | null>(null)
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  async function load() {
    setBusy(true); setFeedback(''); setDigest(null)
    try { setDigest(await api<DailyDigest>(`/digests/daily?day=${encodeURIComponent(day)}`)) }
    catch (err) { setFeedback(message(err)) }
    finally { setBusy(false) }
  }
  return <details className="panel archive-filters"><summary>Daily digest</summary><div className="digest-controls"><label>Day ({timezone})<input type="date" value={day} onChange={e => { setDay(e.target.value); setDigest(null) }} /></label><button className="secondary" disabled={busy || !day} onClick={load}>{busy ? 'Loading…' : 'Show digest'}</button></div>
    {digest && <><p><strong>{digest.recording_count}</strong> saved recordings · {digest.analyzed_count} analyzed · {digest.failed_count} analysis failures</p><p className="helper">{Object.entries(digest.category_clip_counts).map(([category, count]) => `${category}: ${count} clip(s)`).join(' · ') || 'No saved object labels for this day.'}</p><p className="helper">{digest.coverage_note}</p><div className="digest-highlights">{digest.highlights.map(item => <button className="secondary" key={item.event_id} onClick={() => onRecording(item.event_id)}>{item.source === 'owner' ? 'Your description: ' : 'AI: '}{item.text}</button>)}</div></>}
    {feedback && <p role="status">{feedback}</p>}
  </details>
}
