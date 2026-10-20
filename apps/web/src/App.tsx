import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Activity, Bell, HardDrive, LogOut, ScanFace, Settings as SettingsIcon, ShieldCheck, Upload, Video } from 'lucide-react'
import BrandMark from './components/BrandMark'
import OwnerForm from './components/OwnerForm'
import SettingsView from './components/SettingsView'
import { EventDetail } from './components/EventDetail'
import LivePage from './components/LivePage'
import { draftFromFilters, emptyFilters, type FilterDraft } from './components/ArchiveFilters'
import ActivityTools from './components/ActivityTools'
import { ArchiveCoverage, ArchiveTimeline } from './components/ArchiveTimeline'
import NotificationsPage from './components/NotificationsPage'
import FacialRecognitionPage from './components/FacialRecognitionPage'
import { useStateUpdates } from './lib/state-updates'
import { api, ApiError, message, setSession, type AnalysisStatus, type CameraList, type Event, type EventFilters, type EventList, type Health, type SavedView, type Session, type Settings, type Setup } from './lib/api'

type Page = 'live' | 'activity' | 'faces' | 'settings' | 'notifications'
const navigation = [ { id: 'live', label: 'Live View', icon: Video }, { id: 'activity', label: 'Activity', icon: Activity }, { id: 'faces', label: 'Faces', icon: ScanFace }, { id: 'settings', label: 'Settings', icon: SettingsIcon } ] as const

function currentPage(): Page {
  const id = location.hash.slice(1).split('?')[0]
  if (id === 'search' || id === 'library') return 'activity'
  if (id === 'cameras') return 'live'
  return id === 'notifications' || navigation.some(page => page.id === id) ? id as Page : 'live'
}

function routeId(key: string): string | null {
  const value = new URLSearchParams(location.hash.split('?')[1] ?? '').get(key)
  return value && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value) ? value : null
}

export default function App() {
  const [session, updateSession] = useState<Session | null>(null)
  const [setup, setSetup] = useState<Setup | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState<Page>(currentPage)
  const [health, setHealth] = useState<Health | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [aiReady, setAiReady] = useState(false)
  const [events, setEvents] = useState<Event[]>([])
  const [cameras, setCameras] = useState<CameraList['items']>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null)
  const [query, setQuery] = useState('')
  const [favourites, setFavourites] = useState(false)
  const [mediaKind, setMediaKind] = useState<'all' | 'recordings' | 'snapshots'>('all')
  const [filters, setFilters] = useState<FilterDraft>(emptyFilters)
  const [interpreted, setInterpreted] = useState<EventFilters | null>(null)
  const [viewId, setViewId] = useState(() => routeId('view'))
  const [eventId, setEventId] = useState(() => routeId('event'))
  const [eventReload, setEventReload] = useState(0)
  const [busy, setBusy] = useState('')
  const [feedback, setFeedback] = useState('')
  const upload = useRef<HTMLInputElement>(null)
  const eventRequest = useRef(0)

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [page])

  const acceptSession = useCallback((value: Session | null) => { setSession(value); updateSession(value) }, [])
  const initialize = useCallback(async () => {
    setLoading(true); setError('')
    try {
      setSetup(await api<Setup>('/setup/state'))
      try { acceptSession(await api<Session>('/auth/session')) }
      catch (err) { if (!(err instanceof ApiError && err.status === 401)) throw err }
    } catch (err) { setError(message(err)) }
    finally { setLoading(false) }
  }, [acceptSession])
  useEffect(() => { void initialize() }, [initialize])

  const refresh = useCallback(async () => {
    if (!session) return
    try {
      const [status, values, inventory] = await Promise.all([api<Health>('/health'), api<Settings>('/settings'), api<CameraList>('/cameras')])
      setHealth(status); setSettings(values); setCameras(inventory.items); setError('')
      void api<AnalysisStatus>('/analysis/status').then(analysis => setAiReady(analysis.ready)).catch(() => setAiReady(false))
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) acceptSession(null)
      else setError(message(err))
    }
  }, [session, acceptSession])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => {
    if (!session || page !== 'live') return
    let active = true
    let pending = false
    const update = async () => {
      if (pending) return
      pending = true
      try {
        const inventory = await api<CameraList>('/cameras')
        if (active) setCameras(inventory.items)
      } catch (err) {
        if (active && err instanceof ApiError && err.status === 401) acceptSession(null)
      } finally { pending = false }
    }
    void update()
    const timer = window.setInterval(() => { void update() }, 10000)
    return () => { active = false; window.clearInterval(timer) }
  }, [session, page, acceptSession])
  useEffect(() => {
    const onHash = () => {
      const legacy = location.hash.slice(1).split('?')[0]
      if (['search', 'library', 'cameras'].includes(legacy)) {
        const params = new URLSearchParams(location.hash.split('?')[1] ?? '')
        if (legacy === 'cameras') params.set('manage', '1')
        history.replaceState(null, '', `#${legacy === 'cameras' ? 'live' : 'activity'}${params.size ? `?${params}` : ''}`)
      }
      setPage(currentPage()); setViewId(routeId('view')); setEventId(routeId('event')); setSelectedEvent(previous => previous?.id === routeId('event') ? previous : null); setFeedback('')
    }
    onHash()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    if (!session || !viewId) return
    const controller = new AbortController()
    void api<SavedView>(`/saved-views/${viewId}`, { signal: controller.signal }).then(view => {
      if (controller.signal.aborted) return
      setInterpreted(view.filters); setFilters(emptyFilters); setQuery(view.filters.query ?? ''); setFavourites(view.filters.favourites ?? false); setMediaKind(view.filters.media_kind ?? 'all')
    }).catch(error => { if (!controller.signal.aborted) setFeedback(message(error)) })
    return () => controller.abort()
  }, [session, viewId])
  useEffect(() => {
    if (!session || !eventId) return
    const controller = new AbortController()
    void api<Event>(`/events/${eventId}`, { signal: controller.signal }).then(event => { if (!controller.signal.aborted) setSelectedEvent(event) }).catch(error => { if (!controller.signal.aborted) setFeedback(message(error)) })
    return () => controller.abort()
  }, [session, eventId, eventReload])
  useEffect(() => {
    const theme = settings?.theme ?? 'system'
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const root = document.documentElement
      root.dataset.theme = theme === 'system' ? (media.matches ? 'dark' : 'light') : theme
      document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', getComputedStyle(root).getPropertyValue('--background').trim())
    }
    apply(); media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [settings?.theme])

  const eventParams = useCallback(() => {
      const params = new URLSearchParams({ query, favourites: String(favourites) })
      if (interpreted) {
        for (const [key, value] of Object.entries(interpreted)) {
          if (Array.isArray(value)) for (const item of value) params.append(key, String(item))
          else if (value !== null && value !== undefined && !['cursor', 'query', 'favourites'].includes(key)) params.set(key, String(value))
        }
      }
      for (const [key, value] of Object.entries(filters)) {
        if (value) params.set(key, key === 'start' || key === 'end' ? new Date(value).toISOString() : value)
      }
      params.set('include_captures', 'true'); params.set('media_kind', mediaKind)
      return params
  }, [query, favourites, filters, interpreted, mediaKind])
  const loadEvents = useCallback(async (cursor?: string) => {
    const sequence = ++eventRequest.current
    setBusy('events')
    try {
      const params = eventParams()
      if (cursor) params.set('cursor', cursor)
      const data = await api<EventList>(`/events?${params}`)
      if (sequence !== eventRequest.current) return
      setEvents(previous => cursor ? [...previous, ...data.items.filter(item => !previous.some(event => event.id === item.id && !!event.capture === !!item.capture))] : data.items)
      setNextCursor(data.next_cursor)
    } catch (err) { if (sequence === eventRequest.current) setFeedback(message(err)) }
    finally { if (sequence === eventRequest.current) setBusy('') }
  }, [eventParams])
  async function refreshRecording(id: string) {
    if (events.length <= 30) { await loadEvents(); return }
    const sequence = eventRequest.current
    const origin = currentPage()
    try {
      const updated = await api<Event | null>(`/events/${id}/match?${eventParams()}`)
      if (sequence !== eventRequest.current || origin !== currentPage()) return
      setEvents(previous => previous.flatMap(event => event.id === id && !event.capture ? updated ? [updated] : [] : [event]))
      if (!updated && (nextCursor === id || nextCursor === `e:${id}`)) {
        const last = events.filter(event => event.id !== id || event.capture).at(-1)
        setNextCursor(last ? `${last.capture ? 'c' : 'e'}:${last.id}` : null)
      }
    } catch (err) { if (sequence === eventRequest.current) setFeedback(message(err)) }
  }
  useStateUpdates(!!session, topics => {
    if (topics.some(topic => ['health', 'cameras', 'settings'].includes(topic))) void refresh()
    if (topics.some(topic => ['activity', 'library'].includes(topic)) && currentPage() === 'activity' && events.length <= 30) void loadEvents()
  }, () => acceptSession(null))
  useEffect(() => {
    if (session && page === 'activity') void loadEvents()
  }, [session, page, loadEvents])
  useEffect(() => {
    if (!session || page !== 'activity') return
    const timer = window.setInterval(() => { void refresh(); if (events.length <= 30) void loadEvents() }, 10000)
    return () => { window.clearInterval(timer); ++eventRequest.current }
  }, [session, page, refresh, loadEvents, events.length])

  async function importClip(file?: File) {
    if (!file) return
    const image = file.type === 'image/jpeg' || /\.jpe?g$/i.test(file.name)
    if (file.size > (image ? 32 : 256) * 1024 ** 2) { setFeedback(image ? 'Choose a JPEG smaller than 32 MiB.' : 'Choose an MP4 smaller than 256 MiB.'); return }
    setBusy('import'); setFeedback('')
    try {
      const event = await api<Event>('/imports', { method: 'POST', body: file, headers: { 'Content-Type': image ? 'image/jpeg' : 'video/mp4' } })
      setFeedback('Recording saved locally.'); await loadEvents(); await refresh(); openRecording(event.id)
    } catch (err) { setFeedback(message(err)) }
    finally { setBusy(''); if (upload.current) upload.current.value = '' }
  }
  async function logout() {
    try { await api('/auth/logout', { method: 'POST' }); acceptSession(null); setSetup({ owner_created: true }); setSettings(null); setHealth(null); setEvents([]); setCameras([]); setAiReady(false) }
    catch (err) { setError(message(err)) }
  }
  function openRecording(id: string) {
    const origin = currentPage()
    const params = new URLSearchParams(location.hash.split('?')[1] ?? '')
    params.set('event', id)
    const target = `${origin === 'notifications' ? 'activity' : origin}?${params}`
    if (location.hash === `#${target}`) setEventReload(value => value + 1)
    else location.hash = target
  }
  function closeRecording() {
    setSelectedEvent(null)
    const params = new URLSearchParams(location.hash.split('?')[1] ?? '')
    params.delete('event')
    location.hash = `${currentPage()}${params.size ? `?${params}` : ''}`
  }

  if (loading) return <main className="loading-state"><BrandMark /><p>Opening Porchlight…</p></main>
  if (!session) return error ? <main className="loading-state"><h1>Porchlight is unavailable</h1><p role="alert">{error}</p><button className="primary" onClick={initialize}>Try again</button></main> : <OwnerForm creating={!setup?.owner_created} onSession={value => { acceptSession(value); if (!setup?.owner_created) location.hash = 'settings?setup=1' }} />

  const title = page === 'notifications' ? 'Notifications' : page === 'faces' ? 'Facial recognition' : navigation.find(item => item.id === page)!.label
  const compactPage = page === 'live'
  const currentFilters: EventFilters = { daypart: 'all', ...interpreted, query, favourites, include_captures: true, media_kind: mediaKind, ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value).map(([key, value]) => [key, key === 'start' || key === 'end' ? new Date(value).toISOString() : value])) }
  const displayedDraft = draftFromFilters(currentFilters)
  const hasArchiveFilters = mediaKind !== 'all' || Object.entries(currentFilters).some(([key, value]) => !['cursor', 'include_captures', 'media_kind'].includes(key) && (Array.isArray(value) ? value.length > 0 : !!value && !(key === 'daypart' && value === 'all')))
  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#live"><BrandMark />Porchlight</a>
      <nav aria-label="Main navigation">{navigation.map(item => <a href={`#${item.id}`} key={item.id} aria-current={page === item.id ? 'page' : undefined} className={page === item.id ? 'nav-item active' : 'nav-item'}><item.icon size={21} /><span>{item.label}</span></a>)}</nav>
      <div className="sidebar-footer">
        <a className={page === 'notifications' ? 'nav-item active' : 'nav-item'} href="#notifications" aria-current={page === 'notifications' ? 'page' : undefined}><Bell size={19} /><span>Notifications</span></a>
        <button className="nav-item sign-out" aria-label="Sign out of Porchlight" onClick={logout}><LogOut size={18} /><span>Sign out</span></button>
        <span className="local-label"><ShieldCheck size={16} />Local workspace</span><small>Development · v{health?.version ?? '0.1.0'}</small>
      </div>
    </aside>
    <div className="workspace">
      <main id="main-content" className={compactPage ? 'compact-page' : undefined} tabIndex={-1}>
        <div className="page-heading"><div className="page-title-row"><div className="page-heading-copy"><h1>{title}</h1>{!compactPage && <p>{page === 'activity' ? 'Your recordings, kept close to home.' : 'Make Porchlight work for your home.'}</p>}</div>
          <div className="mobile-workspace-actions"><a className="icon-button" href="#notifications" aria-label="Notifications" aria-current={page === 'notifications' ? 'page' : undefined} title="Notifications"><Bell size={19} /></a><button className="icon-button" aria-label="Sign out of Porchlight" title="Sign out" onClick={logout}><LogOut size={18} /></button></div>
        </div>
          {page === 'activity' && <button className="primary" disabled={!!busy || health?.media_tools.state !== 'ready'} onClick={() => upload.current?.click()}><Upload size={18} />{busy === 'import' ? 'Importing…' : 'Import recording'}</button>}
        </div>
        {error && <div className="notice" role="alert"><strong>Connection needs attention</strong><p>{error}</p><button className="secondary" onClick={refresh}>Check again</button></div>}
        {feedback && <p className="feedback" role="status">{feedback}</p>}
        <input ref={upload} type="file" accept="video/mp4,.mp4,image/jpeg,.jpg,.jpeg" className="visually-hidden" aria-label="Choose an MP4 recording or JPEG image" onChange={e => { void importClip(e.target.files?.[0]) }} />
        {page === 'activity' && <>
          <div className="activity-kind" role="group" aria-label="Activity media type">{(['all', 'recordings', 'snapshots'] as const).map(kind => <button key={kind} className={mediaKind === kind ? 'secondary selected' : 'secondary'} aria-pressed={mediaKind === kind} onClick={() => setMediaKind(kind)}>{kind === 'all' ? 'All' : kind === 'recordings' ? 'Recordings' : 'Snapshots'}</button>)}</div>
          <ActivityTools query={query} favourites={favourites} draft={displayedDraft} filters={currentFilters} cameras={cameras} timezone={settings?.timezone ?? 'America/Toronto'}
            onQuery={setQuery} onFavourites={() => setFavourites(value => !value)} onSearch={() => { void loadEvents() }}
            onDraft={value => {
              setFilters(value)
              setInterpreted(previous => {
                if (!previous) return null
                const next = { ...previous }
                for (const key of Object.keys(value) as (keyof FilterDraft)[]) {
                  if (value[key] === displayedDraft[key]) continue
                  delete next[key]
                  if (key === 'category') delete next.categories
                  if (key === 'camera_id') delete next.camera_ids
                }
                return next
              })
            }}
            onApply={value => { setFilters(emptyFilters); setQuery(value.query ?? ''); setFavourites(value.favourites ?? false); setInterpreted(value) }}
            onSavedView={(value, id) => { setFilters(emptyFilters); setQuery(value.query ?? ''); setFavourites(value.favourites ?? false); setInterpreted(value); setMediaKind(value.media_kind ?? 'all'); location.hash = `activity?view=${id}` }}
            onRemove={key => {
              if (key === 'query') setQuery('')
              if (key === 'favourites') setFavourites(false)
              if (key in emptyFilters) setFilters(previous => ({ ...previous, [key]: '' }))
              setInterpreted(previous => { if (!previous) return null; const next = { ...previous }; delete next[key]; return next })
            }}
            onClear={() => { setInterpreted(null); setFilters(emptyFilters); setQuery(''); setFavourites(false); setMediaKind('all') }}
            onClearFilters={() => { setInterpreted(null); setFilters(emptyFilters) }}
            onRecording={id => { void openRecording(id) }} />
          <ArchiveCoverage health={health} />
          {events.length ? <ArchiveTimeline events={events} cameras={cameras} timezone={settings?.timezone ?? 'America/Toronto'} onRecording={id => { void openRecording(id) }} onCaptureChanged={async () => { await loadEvents() }} />
            : <section className="panel empty-state"><div className="empty-icon"><Activity size={32} /></div><h2>{hasArchiveFilters ? 'No matching recordings' : 'Your timeline starts here'}</h2><p>{hasArchiveFilters ? 'Try different words or clear your filters.' : 'Start Sync recordings in Settings to save available cloud clips, or import an MP4 to test local playback.'}</p>{!hasArchiveFilters && <button className="secondary" disabled={!!busy || health?.media_tools.state !== 'ready'} onClick={() => upload.current?.click()}><Upload size={17} />Import your first recording</button>}</section>}
          {nextCursor && <button className="secondary load-more" disabled={!!busy} onClick={() => { void loadEvents(nextCursor) }}>Load more recordings</button>}
          <div className="quiet-note"><HardDrive size={18} /><p>Manual imports are stored locally. They are separate from Blink recordings and are not evidence of camera connectivity.</p></div>
        </>}
        {page === 'notifications' && <NotificationsPage timezone={settings?.timezone ?? 'America/Toronto'} cameras={cameras} onRecording={id => { void openRecording(id) }} />}
        {page === 'faces' && <FacialRecognitionPage />}
        {page === 'settings' && settings && <SettingsView cameras={cameras} settings={settings} health={health} onSaved={refresh} />}
        {selectedEvent && <EventDetail key={selectedEvent.id} event={selectedEvent} aiReady={aiReady} timezone={settings?.timezone ?? 'America/Toronto'} onClose={closeRecording} onSaved={() => { if (selectedEvent) void refreshRecording(selectedEvent.id) }} />}
        {page === 'live' && <LivePage cameras={cameras} timezone={settings?.timezone ?? 'America/Toronto'} onSaved={refresh} onRecording={openRecording} />}
      </main>
        <footer className="workspace-footer">Porchlight · Stored locally. Looked after by you. · Built by <a href="https://github.com/kevindemara" target="_blank" rel="noopener noreferrer">Kevin DeMara</a></footer>
    </div>
  </div>
}

