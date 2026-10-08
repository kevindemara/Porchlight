import { useEffect, useRef, useState } from 'react'
import { Camera, Circle, Maximize, Minimize, Play, Square } from 'lucide-react'
import { api, message, type CameraList, type Capture, type LiveSession } from '../lib/api'

function waitFor(target: EventTarget, event: string, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const clean = () => { target.removeEventListener(event, done); target.removeEventListener('error', fail); signal.removeEventListener('abort', fail) }
    const done = () => { clean(); resolve() }
    const fail = () => { clean(); reject(new Error('Video playback was interrupted.')) }
    if (signal.aborted) { fail(); return }
    target.addEventListener(event, done, { once: true }); target.addEventListener('error', fail, { once: true }); signal.addEventListener('abort', fail, { once: true })
  })
}

export default function LiveView({ camera }: { camera: CameraList['items'][number] }) {
  const mounted = useRef(false)
  const video = useRef<HTMLVideoElement>(null)
  const screen = useRef<HTMLDivElement>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [session, setSession] = useState<LiveSession | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [fresh, setFresh] = useState(false)
  const [remaining, setRemaining] = useState(90)
  const [playerReady, setPlayerReady] = useState(false)
  const [captureBusy, setCaptureBusy] = useState(false)
  const recording = session?.recording
  const recordingActive = recording?.state === 'recording'
  const recordingPending = recordingActive || recording?.state === 'saving'
  const sessionId = session?.id
  const ended = session?.state === 'ended' || session?.state === 'failed'
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    const element = screen.current
    const changed = () => setFullscreen(document.fullscreenElement === element)
    document.addEventListener('fullscreenchange', changed)
    return () => {
      document.removeEventListener('fullscreenchange', changed)
      if (element && document.fullscreenElement === element) void document.exitFullscreen().catch(() => {})
    }
  }, [])

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement === screen.current) await document.exitFullscreen()
      else if (document.fullscreenEnabled && screen.current) await screen.current.requestFullscreen()
      else setFeedback('Fullscreen is unavailable in this browser.')
    } catch { setFeedback('Fullscreen could not be opened or closed. Use the browser’s fullscreen exit control to return.') }
  }

  async function start() {
    if (typeof MediaSource === 'undefined' || !MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"')) {
      setFeedback('This browser cannot play live video. Try a current desktop Edge or Chrome browser.'); return
    }
    setBusy(true); setFeedback(''); setFresh(false); setPlayerReady(false)
    try {
      const started = await api<LiveSession>(`/cameras/${camera.id}/live`, { method: 'POST' })
      if (mounted.current) setSession(started)
      else await api(`/live/${started.id}/stop`, { method: 'POST', keepalive: true })
    }
    catch (error) { if (mounted.current) setFeedback(message(error)) }
    finally { if (mounted.current) setBusy(false) }
  }
  async function stop() {
    if (!sessionId) return
    setFresh(false); setBusy(true)
    try { await api(`/live/${sessionId}/stop`, { method: 'POST' }); setSession(previous => previous ? { ...previous, state: 'ended', message: 'Live view ended.' } : previous) }
    catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function trustCertificate() {
    if (!sessionId) return
    setBusy(true)
    try {
      await api(`/live/${sessionId}/trust-certificate`, { method: 'POST' })
      setSession(previous => previous ? { ...previous, certificate_sha256: null } : previous)
      setFeedback('Certificate pinned for Porchlight. Wait a minute between attempts, then start a new session.')
    } catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }

  async function record() {
    if (!sessionId || (!recordingActive && (!fresh || video.current?.paused))) return
    setCaptureBusy(true); setFeedback('')
    try {
      const capture = await api<Capture>(`/live/${sessionId}/record${recordingActive ? '/stop' : ''}`, { method: 'POST' })
      if (!mounted.current) return
      setSession(previous => previous ? { ...previous, recording: capture } : previous)
      if (capture.state === 'ready') setFeedback('Recording saved to Library.')
      else if (capture.state === 'failed') setFeedback(capture.safe_error ?? 'The recording could not be saved.')
    } catch (error) { if (mounted.current) setFeedback(message(error)) }
    finally { if (mounted.current) setCaptureBusy(false) }
  }

  async function snapshot() {
    const player = video.current
    if (!sessionId || !fresh || !player || player.paused || !player.videoWidth) return
    setCaptureBusy(true); setFeedback('')
    try {
      const canvas = document.createElement('canvas')
      canvas.width = player.videoWidth; canvas.height = player.videoHeight
      const context = canvas.getContext('2d')
      if (!context) throw new Error('This browser cannot capture a snapshot.')
      context.drawImage(player, 0, 0)
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('The snapshot could not be created.')), 'image/jpeg', 0.92))
      const saved = await api<Capture>(`/live/${sessionId}/snapshot`, { method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: blob })
      if (mounted.current) setFeedback(saved.state === 'ready' ? 'Snapshot saved to Library.' : saved.safe_error ?? 'The snapshot could not be saved.')
    } catch (error) { if (mounted.current) setFeedback(message(error)) }
    finally { if (mounted.current) setCaptureBusy(false) }
  }

  useEffect(() => {
    if (!recording || !recordingPending) return
    const controller = new AbortController()
    let pending = false
    const update = async () => {
      if (pending) return
      pending = true
      try {
        const saved = await api<Capture>(`/library/${recording.id}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setSession(previous => previous?.recording?.id === saved.id ? { ...previous, recording: saved } : previous)
        if (saved.state === 'ready') setFeedback('Recording saved to Library.')
        if (saved.state === 'failed') setFeedback(saved.safe_error ?? 'The recording could not be saved.')
      } catch (error) { if (!controller.signal.aborted) setFeedback(message(error)) }
      finally { pending = false }
    }
    const timer = window.setInterval(() => { void update() }, 1000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [recording?.id, recordingPending])

  useEffect(() => {
    if (!sessionId || ended || !video.current) return
    const controller = new AbortController()
    const player = video.current
    const source = new MediaSource()
    const url = URL.createObjectURL(source)
    let lastPresented = 0
    let lastMediaTime = -1
    let lastStatus: LiveSession | null = null
    let callback = 0
    let heartbeatBusy = false
    const presented: VideoFrameRequestCallback = (_, metadata) => {
      if (metadata.mediaTime > lastMediaTime) { lastPresented = Date.now(); lastMediaTime = metadata.mediaTime; setPlayerReady(true) }
      if (!controller.signal.aborted) callback = player.requestVideoFrameCallback(presented)
    }
    if ('requestVideoFrameCallback' in player) callback = player.requestVideoFrameCallback(presented)
    const opened = waitFor(source, 'sourceopen', controller.signal)
    player.src = url
    async function play() {
      try {
        await opened
        const buffer = source.addSourceBuffer('video/mp4; codecs="avc1.42E01E"')
        const response = await fetch(`/api/v1/live/${sessionId}/media`, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal })
        if (!response.ok || !response.body) throw new Error('The live video connection could not be opened.')
        const reader = response.body.getReader()
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read()
          if (done) break
          const updated = waitFor(buffer, 'updateend', controller.signal)
          buffer.appendBuffer(value); await updated
          if (buffer.buffered.length) {
            const edge = buffer.buffered.end(buffer.buffered.length - 1)
            if (edge - player.currentTime > 4) player.currentTime = Math.max(buffer.buffered.start(0), edge - 1)
            if (player.currentTime > 8 && buffer.buffered.start(0) < player.currentTime - 6) {
              const removed = waitFor(buffer, 'updateend', controller.signal)
              buffer.remove(0, player.currentTime - 6); await removed
            }
            if (player.paused) await player.play().catch(() => { if (!controller.signal.aborted) setFeedback('Select Play to begin watching.') })
          }
        }
        if (!controller.signal.aborted && source.readyState === 'open') source.endOfStream()
      } catch (error) {
        if (!controller.signal.aborted) { setFeedback(message(error)); void api(`/live/${sessionId}/stop`, { method: 'POST' }).catch(() => {}) }
      }
    }
    async function heartbeat() {
      if (heartbeatBusy || controller.signal.aborted) return
      heartbeatBusy = true
      try {
        lastStatus = await api<LiveSession>(`/live/${sessionId}/heartbeat`, { method: 'POST', signal: controller.signal })
        if (controller.signal.aborted) return
        setSession(lastStatus)
        setRemaining(Math.max(0, Math.ceil((Date.parse(lastStatus.expires_at) - Date.now()) / 1000)))
        if (lastStatus.state === 'ended' || lastStatus.state === 'failed') { setFresh(false); player.pause() }
      } catch (error) {
        lastStatus = null
        if (!controller.signal.aborted) { setFresh(false); setFeedback(message(error)) }
      } finally { heartbeatBusy = false }
    }
    const freshness = window.setInterval(() => {
      setFresh(Date.now() - lastPresented < 3000 && lastStatus?.state === 'receiving' && (lastStatus.media_age_seconds ?? 99) < 5 && !player.paused)
    }, 500)
    const poll = window.setInterval(() => { void heartbeat() }, 2000)
    const hide = () => { if (document.hidden) void api(`/live/${sessionId}/stop`, { method: 'POST', keepalive: true }).catch(() => {}) }
    document.addEventListener('visibilitychange', hide)
    void play(); void heartbeat()
    return () => {
      controller.abort(); window.clearInterval(poll); window.clearInterval(freshness)
      document.removeEventListener('visibilitychange', hide)
      if (callback) player.cancelVideoFrameCallback(callback)
      player.pause(); player.removeAttribute('src'); player.load(); URL.revokeObjectURL(url)
      void api(`/live/${sessionId}/stop`, { method: 'POST', keepalive: true }).catch(() => {})
    }
  }, [sessionId, ended])
  useEffect(() => { if (ended) { setFresh(false); video.current?.pause() } }, [ended])

  return <section className="panel live-player" aria-labelledby="live-title">
    <div className="dialog-heading"><div><span className="eyebrow">Experimental live view</span><h2 id="live-title">{camera.name}</h2></div></div>
    <div ref={screen} className="live-screen"><video ref={video} muted autoPlay playsInline aria-label="Live camera video" />
      {!fresh && <div className="live-overlay"><strong>{ended ? session.message : session ? (playerReady ? 'Waiting for fresh video…' : 'Connecting to your camera…') : 'Ready when you are'}</strong><span>{ended ? 'Start a new session to reconnect.' : 'Live status appears only while fresh video is playing.'}</span></div>}
      <div className="live-screen-controls">
        {fullscreen && <><button className="live-screen-button" disabled={captureBusy || (!recordingActive && (!fresh || recordingPending))} onClick={record}>{recordingActive ? <Square size={17} /> : <Circle size={17} />}{recordingActive ? 'Stop recording' : 'Record'}</button><button className="live-screen-button" disabled={!fresh || captureBusy} onClick={snapshot}><Camera size={17} />Snapshot</button></>}
        {fullscreen && session && !ended && <button className="live-screen-button" disabled={busy} onClick={stop}><Square size={17} />Stop live view</button>}
        <button className="live-screen-button" aria-label={fullscreen ? 'Exit fullscreen' : 'Enter fullscreen'} aria-pressed={fullscreen} onClick={toggleFullscreen}>{fullscreen ? <Minimize size={18} /> : <Maximize size={18} />}<span>{fullscreen ? 'Exit fullscreen' : 'Fullscreen'}</span></button>
      </div>
      {fullscreen && fresh && <span className="live-fullscreen-status">Live video</span>}
      {recordingPending && <span className="live-recording-status" role="status">{recordingActive ? 'Recording to Library' : 'Saving recording…'}</span>}
    </div>
    <div className="detail-body"><div className="live-state" role="status"><span className={`badge ${fresh ? 'ready' : ''}`}>{fresh ? 'LIVE' : ended ? 'Ended' : session ? 'Connecting' : 'Not started'}</span><span>{session && !ended ? `${remaining}s remaining` : 'Up to 90 seconds per session'}</span></div>
      <div className="live-control-bar">
        <div className="detail-actions">{!session || ended ? <button className="primary" disabled={busy} onClick={start}><Play size={17} />{busy ? 'Starting…' : 'Start live view'}</button> : <><button className="secondary" disabled={busy} onClick={stop}><Square size={16} />Stop live view</button><button className="secondary" onClick={() => { void video.current?.play() }}>Play</button></>}</div>
        <div className="capture-actions"><button className="secondary" disabled={captureBusy || (!recordingActive && (!fresh || recordingPending))} onClick={record}>{recordingActive ? <Square size={17} /> : <Circle size={17} />}{recordingActive ? 'Stop recording' : 'Record'}</button><button className="secondary" disabled={!fresh || captureBusy} onClick={snapshot}><Camera size={17} />Snapshot</button></div>
      </div>
      <p className="helper">On demand via Blink’s internet service. Live viewing uses camera battery. Record saves video locally; Snapshot saves the displayed frame. Audio is unavailable.</p>
      {feedback && <p className="feedback" role="alert">{feedback}</p>}
      {session?.certificate_sha256 && <div className="notice"><strong>Review Blink relay certificate</strong><p>Blink supplied a relay with a self-signed certificate. It has not been independently authenticated by a trusted certificate authority. Approving pins this exact certificate for Porchlight; a changed certificate requires a new review. Windows and other apps are unaffected.</p><p className="helper">SHA-256 fingerprint</p><code className="certificate-fingerprint">{session.certificate_sha256}</code><button className="secondary" disabled={busy} onClick={trustCertificate}>Trust this certificate for Porchlight</button></div>}
      <a className="text-link" href="#library">Open Library</a>
    </div>
  </section>
}
