import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { RefreshCw, ScanFace, X } from 'lucide-react'
import { api, message, type FaceApprovalResult, type FaceGallery, type FaceGroup, type FaceRescan, type FaceStatus, type PersonProfile, type PersonProfiles } from '../lib/api'
import FaceDetectionSetup from './FaceDetectionSetup'

type Sample = FaceGroup['samples'][number]

function thumbnail(sample: Sample) {
  return `/api/v1/events/${sample.event_id}/faces/thumbnails/${sample.offset_ms}/${sample.face_index}`
}

function sampleKey(sample: Sample) {
  return `${sample.event_id}:${sample.offset_ms}:${sample.face_index}`
}

function appendGallery(current: FaceGallery, older: FaceGallery): FaceGallery {
  const groups = new Map(current.groups.map(group => [group.id, group]))
  for (const group of older.groups) {
    const existing = groups.get(group.id)
    if (!existing) { groups.set(group.id, group); continue }
    const samples = [...existing.samples, ...group.samples]
      .filter((sample, index, all) => all.findIndex(other => sampleKey(other) === sampleKey(sample)) === index)
      .slice(0, 3)
    groups.set(group.id, { ...existing, sightings: existing.sightings + group.sightings, samples })
  }
  return {
    ...older,
    groups: [...groups.values()],
    saved_people: older.saved_people,
    labeled_totals: older.labeled_totals,
    confirmed_totals: older.confirmed_totals,
    suggestions: [...(current.suggestions ?? []), ...(older.suggestions ?? [])]
      .filter((item, index, all) => all.findIndex(other => sampleKey(other.face) === sampleKey(item.face)) === index),
    recordings_reviewed: current.recordings_reviewed + older.recordings_reviewed,
    omitted_faces: current.omitted_faces + older.omitted_faces,
  }
}

export default function FacialRecognitionPage() {
  const [gallery, setGallery] = useState<FaceGallery | null>(null)
  const [people, setPeople] = useState<PersonProfile[]>([])
  const [status, setStatus] = useState<FaceStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [gatheringAll, setGatheringAll] = useState(false)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [selectedSamples, setSelectedSamples] = useState<Sample[]>([])
  const [excludedSuggestions, setExcludedSuggestions] = useState<Set<string>>(new Set())
  const [targetPerson, setTargetPerson] = useState('')
  const [newName, setNewName] = useState('')
  const [setupRevision, setSetupRevision] = useState(0)
  const scanWasRunning = useRef(false)
  const gatherAbort = useRef<AbortController | null>(null)

  const loadGallery = useCallback(async (signal?: AbortSignal) => {
    gatherAbort.current?.abort()
    setLoading(true)
    try {
      const [nextGallery, profiles] = await Promise.all([
        api<FaceGallery>('/face-detection/gallery', { signal }),
        api<PersonProfiles>('/face-detection/people', { signal }),
      ])
      if (!signal?.aborted) { setGallery(nextGallery); setPeople(profiles.people); setFeedback('') }
    } catch (error) { if (!signal?.aborted) setFeedback(message(error)) }
    finally { if (!signal?.aborted) setLoading(false) }
  }, [])

  async function loadOlder() {
    if (loadingOlder || gallery?.next_offset == null) return
    setLoadingOlder(true)
    try {
      const older = await api<FaceGallery>(`/face-detection/gallery?offset=${gallery.next_offset}`)
      setGallery(current => current ? appendGallery(current, older) : older)
    } catch (error) { setFeedback(message(error)) }
    finally { setLoadingOlder(false) }
  }

  async function gatherAll() {
    if (loadingOlder || gallery?.next_offset == null) return
    const controller = new AbortController()
    gatherAbort.current = controller
    setLoadingOlder(true); setGatheringAll(true)
    try {
      let current = gallery
      while (current.next_offset != null && !controller.signal.aborted) {
        const older = await api<FaceGallery>(
          `/face-detection/gallery?offset=${current.next_offset}`,
          { signal: controller.signal },
        )
        current = appendGallery(current, older)
        setGallery(current)
      }
    } catch (error) { if (!controller.signal.aborted) setFeedback(message(error)) }
    finally {
      if (gatherAbort.current === controller) gatherAbort.current = null
      setLoadingOlder(false); setGatheringAll(false)
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    void loadGallery(controller.signal)
    void api<FaceStatus>('/face-detection/status', { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) { setStatus(value); scanWasRunning.current = value.queued + value.running > 0 } })
      .catch(() => {})
    const timer = window.setInterval(() => {
      void api<FaceStatus>('/face-detection/status', { signal: controller.signal }).then(value => {
        if (controller.signal.aborted) return
        const scanning = value.queued + value.running > 0
        if (scanWasRunning.current && !scanning) {
          void loadGallery(controller.signal)
          setSetupRevision(value => value + 1)
        }
        scanWasRunning.current = scanning
        setStatus(value)
      }).catch(() => {})
    }, 5000)
    return () => { controller.abort(); gatherAbort.current?.abort(); window.clearInterval(timer) }
  }, [loadGallery])

  async function rescan() {
    setBusy(true); setFeedback('')
    try {
      const result = await api<FaceRescan>('/face-detection/rescan-recent', { method: 'POST' })
      scanWasRunning.current = result.queued + result.already_running > 0
      setFeedback(`${result.requested} recent videos selected; ${result.queued} face scans queued. The gallery will refresh when they finish.`)
      if (!scanWasRunning.current) await loadGallery()
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  function toggleSample(group: FaceGroup, sample: Sample) {
    const key = sampleKey(sample)
    if (selectedSamples.some(item => sampleKey(item) === key)) {
      const remaining = selectedSamples.filter(item => sampleKey(item) !== key)
      setSelectedSamples(remaining)
      if (!remaining.length) { setTargetPerson(''); setNewName('') }
    } else if (selectedSamples.length < 12) {
      setSelectedSamples([...selectedSamples, sample])
      const hint = group.person_id || group.suggested_person_id
      if (!selectedSamples.length && hint) setTargetPerson(hint)
      else if (selectedSamples.length && targetPerson && targetPerson !== hint) {
        setTargetPerson('')
        setFeedback('These images come from different groups. Choose the person yourself before assigning.')
      }
    } else {
      setFeedback('Select up to 12 images at a time. Save these, then choose more.')
    }
  }

  function toggleGroup(group: FaceGroup) {
    const keys = new Set(selectedSamples.map(sampleKey))
    const additions = group.samples.filter(sample => !keys.has(sampleKey(sample)))
    if (!additions.length) {
      const own = new Set(group.samples.map(sampleKey))
      const remaining = selectedSamples.filter(sample => !own.has(sampleKey(sample)))
      setSelectedSamples(remaining)
      if (!remaining.length) { setTargetPerson(''); setNewName('') }
      return
    }
    const room = 12 - selectedSamples.length
    if (!room) { setFeedback('Select up to 12 images at a time. Save these, then choose more.'); return }
    setSelectedSamples([...selectedSamples, ...additions.slice(0, room)])
    const hint = group.person_id || group.suggested_person_id
    if (!selectedSamples.length && hint) setTargetPerson(hint)
    else if (selectedSamples.length && targetPerson && targetPerson !== hint) {
      setTargetPerson('')
      setFeedback('These images come from different groups. Choose the person yourself before assigning.')
    }
    if (additions.length > room) setFeedback('Twelve images selected. Save these, then choose more.')
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedSamples.length || (!targetPerson && !newName.trim())) return
    setBusy(true); setFeedback('')
    try {
      const count = selectedSamples.length
      await api<PersonProfile>('/face-detection/people/batch', { method: 'POST', body: JSON.stringify({
        samples: selectedSamples.map(sample => ({
          event_id: sample.event_id,
          offset_ms: sample.offset_ms,
          face_index: sample.face_index,
        })),
        ...(targetPerson ? { person_id: targetPerson } : { name: newName.trim() }),
      }) })
      setSelectedSamples([]); setTargetPerson(''); setNewName('')
      await loadGallery()
      setSetupRevision(value => value + 1)
      setFeedback(`${count} ${count === 1 ? 'image' : 'images'} assigned. Future scans can compare these face samples.`)
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  async function approveSuggested(personId: string, name: string, faces: Sample[]) {
    if (!faces.length) return
    setBusy(true); setFeedback('')
    try {
      const result = await api<FaceApprovalResult>('/face-detection/suggestions/approve', {
        method: 'POST', body: JSON.stringify({
          person_id: personId,
          faces: faces.map(face => ({
            event_id: face.event_id, offset_ms: face.offset_ms,
            face_index: face.face_index, frame_sha256: face.frame_sha256,
            box: face.box,
          })),
        }),
      })
      const approved = new Set(faces.map(sampleKey))
      setGallery(current => current ? {
        ...current,
        suggestions: (current.suggestions ?? []).filter(item => !approved.has(sampleKey(item.face))),
        labeled_totals: { ...current.labeled_totals, [personId]: result.total_labeled },
        confirmed_totals: { ...current.confirmed_totals, [personId]: result.total_confirmed },
      } : current)
      setFeedback(`${result.labeled} ${result.labeled === 1 ? 'face' : 'faces'} labeled as ${name}. ${result.total_confirmed} owner-confirmed detections now have this name across the library.`)
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  const groups = gallery?.groups ?? []
  const unnamed = groups.filter(group => !group.person_id)
  const loadedKnown = groups.filter(group => !!group.person_id)
  const savedPeople = gallery?.saved_people?.length
    ? gallery.saved_people
    : people.map(person => ({ person_id: person.id, name: person.name, samples: [] }))
  const known: FaceGroup[] = [
    ...savedPeople.map((person): FaceGroup => {
      const loaded = loadedKnown.find(group => group.person_id === person.person_id)
      return {
        id: person.person_id, person_id: person.person_id, name: person.name,
        sightings: loaded?.sightings ?? 0,
        samples: person.samples?.length ? person.samples : loaded?.samples ?? [],
      }
    }),
    ...loadedKnown.filter(group => !savedPeople.some(person => person.person_id === group.person_id)),
  ]
  const orderedGroups = [...known, ...unnamed]
  const proposed = new Map<string, { name: string; faces: Sample[] }>()
  const setAside: Sample[] = []
  for (const item of gallery?.suggestions ?? []) {
    if (excludedSuggestions.has(sampleKey(item.face))) { setAside.push(item.face); continue }
    const key = item.person_id
    const entry = proposed.get(key) ?? { name: item.name, faces: [] }
    entry.faces.push(item.face)
    proposed.set(key, entry)
  }
  return <div className="faces-page">
    <section className="panel faces-intro">
      <div><span className="eyebrow">LOCAL REVIEW</span><h2>People seen by your cameras</h2><p>Porchlight keeps a few clear moments from saved face scans together for your review. Similar faces are grouped as suggestions; only you assign names.</p></div>
      <div className="faces-intro-actions"><button className="primary" onClick={() => { void rescan() }} disabled={busy || !status?.ready}><ScanFace size={18} />{busy ? 'Starting…' : 'Rescan recent 20 videos'}</button><span>{status ? `${status.queued} queued · ${status.running} scanning` : 'Checking scanner…'}</span></div>
    </section>
    {feedback && <p role="status" className="feedback">{feedback}</p>}
    <section className="faces-suggestions" aria-label="Suggested matches">
      <div className="faces-gallery-heading"><div><span className="eyebrow">YOUR REVIEW</span><h2>Suggested matches</h2><p>Porchlight groups possible matches to people you have named. Remove any image that does not belong, then approve the remaining faces. No new training samples are added.</p></div>{gallery?.next_offset != null && (gatheringAll ? <button className="secondary" type="button" onClick={() => gatherAbort.current?.abort()}>Stop gathering</button> : <button className="secondary" type="button" disabled={loadingOlder} onClick={() => { void gatherAll() }}>Gather all saved scans</button>)}</div>
      {gatheringAll && gallery && <p role="status" className="helper">Gathering {gallery.recordings_reviewed} of {gallery.total_recordings} scans. Suggested groups will update as older recordings load.</p>}
      {!gatheringAll && gallery && gallery.next_offset == null && gallery.total_recordings > 20 && <p className="helper">All {gallery.total_recordings} saved scans are loaded for review.</p>}
      {loading && <p role="status" className="notice">Checking saved scans for possible matches…</p>}
      {!loading && proposed.size === 0 && <p className="panel faces-suggestion-empty">No suggested matches in the loaded scans. Load older detections below to review more recordings.</p>}
      {!loading && [...proposed].map(([personId, entry]) => <article className="panel faces-suggestion-card" key={personId}>
        <div className="faces-suggestion-top"><div><span className="eyebrow">POSSIBLE MATCH · REVIEW BEFORE SAVING</span><h3>{entry.name}</h3><p>{entry.faces.length} {entry.faces.length === 1 ? 'face' : 'faces'} from loaded scans. Tap any image to set it aside.</p></div><button className="primary" type="button" disabled={busy || loadingOlder} onClick={() => { void approveSuggested(personId, entry.name, entry.faces) }}>{busy ? 'Saving…' : `Approve ${entry.faces.length} for ${entry.name}`}</button></div>
        <div className="faces-suggestion-strip">{entry.faces.map(face => <div className="faces-suggestion-tile" key={sampleKey(face)}><button type="button" className="faces-suggestion-photo" aria-label={`Remove face at ${(face.offset_ms / 1000).toFixed(1)} seconds from suggested ${entry.name} group`} onClick={() => setExcludedSuggestions(current => new Set(current).add(sampleKey(face)))}><img src={thumbnail(face)} alt={`Possible match for ${entry.name}`} loading="lazy" /><span className="faces-suggestion-remove"><X size={14} /> Remove</span></button><a href={`#activity?event=${face.event_id}`}>View clip</a>{(face.box.small || face.box.low_sharpness) && <small>Unclear image</small>}</div>)}</div>
      </article>)}
      {!loading && !!setAside.length && <div className="faces-set-aside"><p>{setAside.length} {setAside.length === 1 ? 'image' : 'images'} set aside and left unnamed.</p><div>{setAside.map(face => <button type="button" key={sampleKey(face)} aria-label={`Restore face at ${(face.offset_ms / 1000).toFixed(1)} seconds to suggested group`} onClick={() => setExcludedSuggestions(current => { const next = new Set(current); next.delete(sampleKey(face)); return next })}><img src={thumbnail(face)} alt="Set-aside face" /><span>Restore</span></button>)}</div></div>}
    </section>
    <section className="faces-gallery" aria-label="Detected people">
      <div className="faces-gallery-heading"><div><h2>Other faces</h2><p>{gallery ? `${gallery.recordings_reviewed} of ${gallery.total_recordings} scanned recordings loaded · ${known.length} saved people · ${unnamed.length} unnamed groups` : 'Gathering face detections…'}</p></div><button className="secondary" disabled={loading || loadingOlder} onClick={() => { void loadGallery() }}><RefreshCw size={16} />Refresh</button></div>
      {loading && <p role="status" className="notice">Building the local face gallery…</p>}
      {!loading && !orderedGroups.length && (proposed.size ? <p className="helper">All reviewable faces in the loaded scans are shown as possible matches above.</p> : <div className="panel empty-state"><ScanFace size={32} /><h3>No other faces in loaded scans</h3><p>Load older detections for more recordings, or run face detection on a new clip.</p></div>)}
      {!loading && !!gallery?.omitted_faces && <p className="helper">Showing the clearest recent examples. {gallery.omitted_faces} lower-ranked detections were left out of this bounded gallery.</p>}
      {!loading && orderedGroups.some(group => group.samples.length > 0) && <p className="helper">Select up to 12 images across any cards, then assign them together. Tap an image again to remove it.</p>}
      {!!selectedSamples.length && <form id="face-batch-form" className="panel face-batch-form" onSubmit={event => { void save(event) }}>
        <div><h3>Assign selected faces</h3><p>{selectedSamples.length} of 12 images selected. All selected images will get the same name; check their original recordings first.</p></div>
        <div className="face-batch-images">{selectedSamples.map(sample => <button key={sampleKey(sample)} type="button" aria-label={`Remove face at ${(sample.offset_ms / 1000).toFixed(1)} seconds from selection`} onClick={() => {
          const remaining = selectedSamples.filter(item => sampleKey(item) !== sampleKey(sample))
          setSelectedSamples(remaining)
          if (!remaining.length) { setTargetPerson(''); setNewName('') }
        }}><img src={thumbnail(sample)} alt="Selected face crop" /><span>×</span></button>)}</div>
        <div className="face-batch-fields">
          {people.length > 0 && <label>Save faces as<select value={targetPerson} onChange={event => setTargetPerson(event.target.value)}><option value="">New person</option>{people.map(person => <option key={person.id} value={person.id} disabled={person.samples + selectedSamples.length > 32}>{person.name} · {person.samples} samples</option>)}</select></label>}
          {!targetPerson && <label>Name<input value={newName} onChange={event => setNewName(event.target.value)} maxLength={64} required placeholder="Person’s name" /></label>}
        </div>
        <div className="face-batch-actions"><button type="submit" className="primary" disabled={busy || (!targetPerson && !newName.trim())}>{busy ? 'Assigning…' : `Assign ${selectedSamples.length} ${selectedSamples.length === 1 ? 'image' : 'images'}`}</button><button type="button" className="secondary" onClick={() => { setSelectedSamples([]); setTargetPerson(''); setNewName('') }}>Clear selection</button></div>
      </form>}
      {!loading && !!orderedGroups.length && <div className="face-group-grid">{orderedGroups.map(group => {
        const savedTotal = group.person_id ? gallery?.labeled_totals?.[group.person_id] : undefined
        const confirmedTotal = group.person_id ? gallery?.confirmed_totals?.[group.person_id] : undefined
        return <article className="face-group-card" key={group.id}>
        <div className="face-group-top"><span className="face-group-avatar"><ScanFace size={22} /></span><div><h3>{group.name ?? 'Unidentified appearance'}</h3><p>{confirmedTotal != null && savedTotal != null ? `${confirmedTotal} owner-confirmed detections · ${Math.max(0, savedTotal - confirmedTotal)} model matches` : `${group.sightings} ${group.sightings === 1 ? 'detection' : 'detections'} · ${group.name ? 'Saved person' : 'Suggested grouping'}`}</p>{confirmedTotal != null && <p>{group.sightings} grouped in loaded scans</p>}{group.suggested_name && <p className="face-suggestion">Possible match: {group.suggested_name} · verify before assigning</p>}</div></div>
        {!!group.samples.length ? <div className="face-group-photos">{group.samples.map(sample => {
          const key = sampleKey(sample)
          const active = selectedSamples.some(item => sampleKey(item) === key)
          return <button type="button" key={key} className={`face-group-photo ${active ? 'selected' : ''}`} aria-pressed={active} aria-label={`Select face at ${(sample.offset_ms / 1000).toFixed(1)} seconds for ${group.name ?? 'unidentified appearance'}`} onClick={() => toggleSample(group, sample)}><img src={thumbnail(sample)} alt="Detected face crop" loading="lazy" /><span>{(sample.offset_ms / 1000).toFixed(1)}s</span></button>
        })}</div> : <p className="helper">No saved face image is available for this person.</p>}
        {!!group.samples.length && <div className="face-group-actions"><button className="secondary" onClick={() => toggleGroup(group)}>{group.samples.every(sample => selectedSamples.some(item => sampleKey(item) === sampleKey(sample))) ? 'Clear photos' : `Select ${group.samples.length === 1 ? 'photo' : 'photos'}`}</button><a className="text-link" href={`#activity?event=${group.samples[0].event_id}`}>Review recording</a></div>}
      </article>})}</div>}
      {!loading && gallery?.next_offset != null && <button className="secondary load-more" disabled={loadingOlder} onClick={() => { void loadOlder() }}>{loadingOlder ? 'Loading older detections…' : 'Load older detections'}</button>}
    </section>
    {!!selectedSamples.length && <div className="face-selection-dock" role="region" aria-label="Selected faces"><span>{selectedSamples.length} {selectedSamples.length === 1 ? 'image' : 'images'} selected</span><button type="button" className="primary" onClick={() => document.getElementById('face-batch-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Assign a name</button></div>}
    <FaceDetectionSetup key={setupRevision} onPeopleChanged={() => { void loadGallery() }} />
  </div>
}
