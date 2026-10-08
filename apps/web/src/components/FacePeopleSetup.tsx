import { useEffect, useState, type FormEvent } from 'react'
import { ScanFace } from 'lucide-react'
import { api, message, type FaceCandidate, type FaceCandidates, type PersonProfile, type PersonProfiles } from '../lib/api'

function sampleUrl(face: FaceCandidate) {
  return `/api/v1/events/${face.event_id}/faces/frames/${face.offset_ms}`
}

function FaceSample({ face }: { face: FaceCandidate }) {
  const rectangle = {
    left: `${100 * face.box.x / face.width}%`,
    top: `${100 * face.box.y / face.height}%`,
    width: `${100 * face.box.width / face.width}%`,
    height: `${100 * face.box.height / face.height}%`,
  }
  return <span className="face-sample" aria-hidden="true">
    <img src={sampleUrl(face)} alt="" loading="lazy" />
    <span className="face-sample-box" style={rectangle} />
  </span>
}

export default function FacePeopleSetup({ ready, onPeopleChanged }: { ready: boolean; onPeopleChanged?: () => void }) {
  const [people, setPeople] = useState<PersonProfile[]>([])
  const [candidates, setCandidates] = useState<FaceCandidate[]>([])
  const [selected, setSelected] = useState<FaceCandidate | null>(null)
  const [name, setName] = useState('')
  const [targetPerson, setTargetPerson] = useState('')
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')

  async function refresh(signal?: AbortSignal) {
    const [profiles, samples] = await Promise.all([
      api<PersonProfiles>('/face-detection/people', { signal }),
      api<FaceCandidates>('/face-detection/candidates', { signal }),
    ])
    if (!signal?.aborted) {
      setPeople(profiles.people)
      setCandidates(samples.faces)
      setEdits(Object.fromEntries(profiles.people.map(person => [person.id, person.name])))
    }
  }
  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal).catch(error => { if (!controller.signal.aborted) setFeedback(message(error)) })
    return () => controller.abort()
  }, [])

  async function enroll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || (!targetPerson && !name.trim())) return
    setBusy(true); setFeedback('')
    try {
      await api<PersonProfile>('/face-detection/people', { method: 'POST', body: JSON.stringify({
        event_id: selected.event_id, offset_ms: selected.offset_ms, face_index: selected.face_index,
        ...(targetPerson ? { person_id: targetPerson } : { name: name.trim() }),
      }) })
      setName(''); setTargetPerson(''); setSelected(null)
      await refresh()
      onPeopleChanged?.()
      setFeedback(targetPerson ? 'Another sample was added to this person.' : 'Person saved. Clear faces in future clips can now be matched locally.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  async function rename(person: PersonProfile) {
    const next = edits[person.id]?.trim()
    if (!next || next === person.name) return
    setBusy(true); setFeedback('')
    try {
      await api<PersonProfile>(`/face-detection/people/${person.id}`, { method: 'PATCH', body: JSON.stringify({ name: next }) })
      await refresh()
      onPeopleChanged?.()
      setFeedback('Name updated.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  async function remove(person: PersonProfile) {
    if (!window.confirm(`Remove ${person.name} from local face recognition?`)) return
    setBusy(true); setFeedback('')
    try {
      await api<void>(`/face-detection/people/${person.id}`, { method: 'DELETE' })
      await refresh()
      onPeopleChanged?.()
      setFeedback('Person removed. Future clips will no longer match this profile.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  const unnamed = candidates.filter(face => !face.box.profile_id).slice(0, 18)
  return <div className="face-people">
    <div className="section-heading"><ScanFace size={19} /><div><h3>Recognize familiar people</h3><p>Name a detected face once to match it in future clips.</p></div></div>
    <p className="helper">Face templates are encrypted for your Windows account. Matching runs on this PC. Check the original recording before relying on a match; unclear or small faces stay unnamed.</p>
    {!ready && <p role="status" className="helper">Install the verified SFace model to enable names. Detection still works without it.</p>}
    {people.length > 0 && <div className="face-people-list"><h4>Saved people</h4>{people.map(person => <div className="face-person-row" key={person.id}>
      <label><span className="sr-only">Name for {person.name}</span><input value={edits[person.id] ?? person.name} maxLength={64} disabled={busy} onChange={event => setEdits(current => ({ ...current, [person.id]: event.target.value }))} /><small>{person.samples ?? 1} {(person.samples ?? 1) === 1 ? 'sample' : 'samples'}{person.automatic_samples ? ` · ${person.automatic_samples} added automatically` : ''}</small></label>
      <button type="button" className="secondary" disabled={busy || !edits[person.id]?.trim() || edits[person.id]?.trim() === person.name} onClick={() => { void rename(person) }}>Save</button>
      <button type="button" className="secondary" disabled={busy} onClick={() => { void remove(person) }}>Remove</button>
    </div>)}</div>}
    <details><summary>Choose a face to name · {unnamed.length} recent samples</summary>
      <button type="button" className="secondary face-refresh" disabled={busy} onClick={() => { void refresh().catch(error => setFeedback(message(error))) }}>Refresh detected faces</button>
      {unnamed.length === 0 ? <p className="helper">No unnamed faces are ready. Detect faces from a recording in Activity, then return here.</p> : <div className="face-candidate-grid">{unnamed.map(face => {
        const key = `${face.event_id}:${face.offset_ms}:${face.face_index}`
        const active = selected && `${selected.event_id}:${selected.offset_ms}:${selected.face_index}` === key
        return <button type="button" key={key} className={`face-candidate ${active ? 'selected' : ''}`} aria-pressed={!!active} onClick={() => setSelected(face)}>
          <FaceSample face={face} />
          <span>{new Date(face.captured_at).toLocaleString()} · {(face.offset_ms / 1000).toFixed(1)}s · face {face.face_index + 1}</span>
          {(face.box.small || face.box.low_sharpness) && <small>Small or blurry; another sample may match better</small>}
        </button>
      })}</div>}
      {selected && <form className="face-enroll-form" onSubmit={event => { void enroll(event) }}>
        {people.length > 0 && <label>Save face as<select value={targetPerson} onChange={event => setTargetPerson(event.target.value)}><option value="">New person</option>{people.map(person => <option key={person.id} value={person.id} disabled={(person.samples ?? 1) >= 32}>{person.name} · {person.samples ?? 1} samples</option>)}</select></label>}
        {!targetPerson && <label>Name this selected face<input value={name} onChange={event => setName(event.target.value)} maxLength={64} placeholder="Person’s name" required /></label>}
        <button className="primary" disabled={busy || !ready || (!targetPerson && !name.trim())}>{busy ? 'Saving…' : targetPerson ? 'Add sample' : 'Save person'}</button>
      </form>}
    </details>
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </div>
}
