import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

function generatedClip(color: string) {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-ai-ui-'))
  try {
    const path = join(directory, 'synthetic.mp4')
    execFileSync(join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', `color=c=${color}:s=320x240:d=1`, '-c:v', 'mpeg4', '-y', path])
    return readFileSync(path)
  } finally { rmSync(directory, { recursive: true, force: true }) }
}

test('synthetic camera card: authenticated clip thumbnail, evidence, playback and fallback', async ({ page }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-camera-preview-'))
  const video = join(directory, 'generated.mp4')
  const executable = join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe')
  execFileSync(executable, ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=orange:s=320x240:d=1', '-c:v', 'mpeg4', '-y', video])
  try {
    await enterWorkspace(page)
    const session = await (await page.request.get('/api/v1/auth/session')).json()
    const response = await page.request.post('/api/v1/imports', { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token, 'Content-Type': 'video/mp4', 'X-Recorded-At': '2026-10-06T12:00:00Z' }, data: readFileSync(video) })
    expect(response.status()).toBe(201)
    const event = await response.json()
    // Inventory/evidence is a synthetic fixture; JPEG extraction, authentication and playback use the real local API.
    let unavailable = false
    await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: [{ id: 'synthetic-preview-camera', name: 'Generated porch fixture', network_name: 'Synthetic network', observed_armed: true, family: 'doorbells', recording_access: 'cloud_archived', live_view: 'disabled', latest_recording: { summary: 'Generated fixture description', summary_source: 'ai', analysis_status: 'analyzed', event_id: event.id, media_id: event.media_id, captured_at: unavailable ? null : event.captured_at, discovered_at: event.discovered_at } }] } }))
    await page.reload()
    await page.getByRole('button', { name: 'Manage cameras', exact: true }).click()
    const image = page.getByRole('img', { name: 'Latest recorded clip from Generated porch fixture' })
    await expect(image).toBeVisible()
    await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0)
    await expect(page.getByText('Recording access verified', { exact: true })).toBeVisible()
    await expect(page.getByText('AI description: Generated fixture description', { exact: true })).toBeVisible()
    await expect(page.getByText('Recording access unverified', { exact: true })).toHaveCount(0)
    await expect(page.getByText(/^Recorded /)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('camera-preview.png'), fullPage: true })
    await page.getByRole('button', { name: 'Open latest recording from Generated porch fixture' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.locator('video')).toHaveAttribute('src', `/api/v1/media/${event.media_id}`)
    await page.keyboard.press('Escape')
    unavailable = true
    await page.route(`**/api/v1/media/${event.media_id}/thumbnail`, route => route.fulfill({ status: 404 }))
    await page.reload()
    await page.getByRole('button', { name: 'Manage cameras', exact: true }).click()
    await expect(page.getByText('Preview unavailable · open recording')).toBeVisible()
    await expect(page.getByText(/recording time unknown/)).toBeVisible()
    await page.getByRole('button', { name: 'Open latest recording from Generated porch fixture' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('owner setup, real empty state, navigation, theme and sign-out', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await enterWorkspace(page)
  await expect(page.getByText('No cameras connected yet')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link')).toHaveText(['Live View', 'Activity', 'Faces', 'Settings'])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  // Synthetic profile only; no populated password/code fields or real camera imagery.
  await page.screenshot({ path: testInfo.outputPath('cameras.png'), fullPage: true })
  await page.getByRole('link', { name: 'Live View', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Live View', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'No cameras connected yet', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start live view', exact: true })).toHaveCount(0)
  await page.getByRole('navigation').getByRole('link', { name: 'Settings' }).click()
  await expect(page.getByRole('heading', { name: 'Blink cameras' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Save camera recordings' })).toBeVisible()
  await page.getByRole('button', { name: 'Sync recordings', exact: true }).click()
  await expect(page.getByText('Connect Blink before syncing recordings.').last()).toBeVisible()
  await page.getByLabel('Blink recording entitlement').selectOption('paid')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('settings.png'), fullPage: true })
  await page.getByRole('button', { name: 'Appearance', exact: true }).click()
  await page.getByLabel('Appearance', { exact: true }).selectOption('dark')
  await page.getByRole('button', { name: 'AI', exact: true }).click()
  await page.getByLabel('AI workload').selectOption('light')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Settings saved.')).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: 'Cameras & recording', exact: true }).click()
  await expect(page.getByLabel('Blink recording entitlement')).toHaveValue('paid')
  await page.reload()
  await page.getByRole('button', { name: 'AI', exact: true }).click()
  await expect(page.getByLabel('AI workload')).toHaveValue('light')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: 'Appearance', exact: true }).click()
  await page.getByLabel('Appearance', { exact: true }).selectOption('light')
  await page.getByRole('button', { name: 'AI', exact: true }).click()
  await page.getByLabel('AI workload').selectOption('balanced')
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Settings saved.')).toBeVisible()
  await page.getByRole('button', { name: 'Sign out of Porchlight', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to Porchlight' })).toBeVisible()
  expect(errors).toEqual([])
})

test('import, authenticated playback, notes, favourites and literal search', async ({ page }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-synthetic-video-'))
  const executable = join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe')
  const video = join(directory, 'synthetic.mp4')
  execFileSync(executable, ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=orange:s=320x240:d=1', '-c:v', 'mpeg4', '-y', video])
  try {
    await enterWorkspace(page)
    await page.getByRole('navigation').getByRole('link', { name: 'Activity' }).click()
    await page.getByLabel('Choose an MP4 recording').setInputFiles({ name: 'synthetic.mp4', mimeType: 'video/mp4', buffer: readFileSync(video) })
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Analyze recording', exact: true })).toBeDisabled()
    const source = await page.locator('video').getAttribute('src')
    expect(source).toMatch(/^\/api\/v1\/media\//)
    const response = await page.request.get(source!, { headers: { Range: 'bytes=0-15' } })
    expect(response.status()).toBe(206)
    await page.getByLabel('Your notes').fill('Synthetic porch test 100%')
    const favourite = page.getByRole('button', { name: /^Add to favourites$|^Favourite$/ })
    if (await favourite.getAttribute('aria-pressed') === 'false') await favourite.click()
    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('Saved.', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).not.toBeVisible()
    await expect(page).toHaveURL(/#activity$/)
    await page.getByLabel('Search recordings').fill('100%')
    await expect(page.locator('.event-card')).toHaveCount(1)
    await expect(page.getByRole('button', { name: /Imported recording.*Synthetic porch test 100%/ })).toBeVisible()
    const thumbnail = page.locator('.event-card .recording-symbol img')
    await expect(thumbnail).toBeVisible()
    await expect.poll(() => thumbnail.evaluate(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0)).toBe(true)
    const layout = await thumbnail.evaluate(image => {
      const rect = image.getBoundingClientRect()
      const container = image.parentElement!.getBoundingClientRect()
      const card = image.closest('.event-card')!.getBoundingClientRect()
      return {
        imageFits: rect.top >= container.top - 1 && rect.bottom <= container.bottom + 1 && rect.left >= container.left - 1 && rect.right <= container.right + 1,
        containerFits: container.top >= card.top && container.bottom <= card.bottom && container.left >= card.left && container.right <= card.right,
      }
    })
    expect(layout).toEqual({ imageFits: true, containerFits: true })
    await page.screenshot({ path: testInfo.outputPath('synthetic-activity-thumbnail.png'), fullPage: true })
    await page.reload()
    await page.getByLabel('Search recordings').fill('100%')
    await expect(page.locator('.event-card')).toHaveCount(1)
    await expect(page.getByRole('button', { name: /Imported recording.*Synthetic porch test 100%/ })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('synthetic AI UI fixture: opt-in, queued clip, evidence and searchable description', async ({ page }, testInfo) => {
  // UI state fixtures only. Actual API/queue/decoder integration is tested in test_analysis.py.
  let savedSettings: Record<string, unknown> | null = null
  let analyzing = false
  let evidenceMedia = ''
  let failSecondSample = true
  await page.route('**/api/v1/settings', async route => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      savedSettings = { ...body, revision: Number(body.revision) + 1 }
    } else if (!savedSettings) {
      savedSettings = await (await route.fetch()).json() as Record<string, unknown>
    }
    await route.fulfill({ json: savedSettings })
  })
  await page.route('**/api/v1/analysis/status', route => route.fulfill({ json: {
    enabled: savedSettings?.ai_enabled ?? false, ready: true, cloud_disabled: true,
    model: 'synthetic-vision', message: 'Synthetic local AI UI fixture.', queued: 0, running: 0, completed: 0, failed: 0,
  } }))
  await page.route('**/api/v1/ollama/models', route => route.fulfill({ json: {
    version: 'synthetic', models: [{ name: 'synthetic-vision', digest: 'synthetic', size_bytes: 100, local: true, vision: true, reason: 'Synthetic fixture' }],
  } }))
  await page.route('**/api/v1/ollama/test', route => route.fulfill({ json: {
    passed: true, model: 'synthetic-vision', digest: 'synthetic', elapsed_seconds: 0.1, message: 'Synthetic fixture test.',
  } }))
  await page.route(/\/api\/v1\/events\/[^/]+\/analyze$/, async route => {
    analyzing = true
    await route.fulfill({ json: { job_id: 'synthetic-job', status: 'queued' } })
  })
  await page.route(/\/api\/v1\/events\/[^/]+\/analysis$/, route => route.fulfill({ json: analyzing ? {
    revision: 1, model: 'synthetic-vision', model_digest: 'synthetic', created_at: '2026-10-06T12:00:00Z', elapsed_seconds: 0.5, frame_count: 2, uncertainty: ['Synthetic fixture evidence.'],
    evidence_frames: [{ frame_id: 'f001', offset_ms: 0 }, { frame_id: 'f002', offset_ms: 500 }],
  } : null }))
  await page.route(/\/api\/v1\/events\/[^/]+\/analysis\/1\/frames\/f\d{3}/, async route => {
    if (route.request().url().includes('f002') && failSecondSample) {
      failSecondSample = false
      return route.fulfill({ status: 503, json: { message: 'Synthetic sample outage.' } })
    }
    const response = await page.request.get(`/api/v1/media/${evidenceMedia}/thumbnail`)
    await route.fulfill({ status: response.status(), contentType: 'image/jpeg', body: await response.body() })
  })
  await page.route(/\/api\/v1\/events\/[^/]+$/, async route => {
    const response = await route.fetch()
    const original = await response.json() as Record<string, unknown>
    evidenceMedia = String(original.media_id)
    await route.fulfill({ json: analyzing ? { ...original, analysis_status: 'analyzed', summary: 'A dog is visible.' } : original })
  })
  await enterWorkspace(page)
  const evidenceSession = await (await page.request.get('/api/v1/auth/session')).json()
  const evidenceImport = await page.request.post('/api/v1/imports', { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': evidenceSession.csrf_token, 'Content-Type': 'video/mp4' }, data: generatedClip('lime') })
  expect(evidenceImport.status()).toBe(201)
  await page.getByRole('navigation').getByRole('link', { name: 'Settings' }).click()
  await page.getByRole('button', { name: 'AI', exact: true }).click()
  await page.getByRole('button', { name: 'Check local models' }).click()
  await page.getByRole('button', { name: 'Test with a synthetic image' }).click()
  await expect(page.getByText('Image test passed', { exact: true })).toBeVisible()
  await page.getByLabel('Analyze new recordings automatically').check()
  await page.getByRole('button', { name: 'Save settings' }).click()
  await expect(page.getByText('Settings saved.')).toBeVisible()
  await page.getByRole('navigation').getByRole('link', { name: 'Activity' }).click()
  await page.getByRole('button', { name: /Imported recording/ }).first().click()
  await page.getByRole('button', { name: 'Analyze recording', exact: true }).click()
  await expect(page.getByText('A dog is visible.', { exact: true })).toBeVisible()
  await expect(page.getByText('AI-generated description · revision 1')).toBeVisible()
  await expect(page.getByText('Synthetic fixture evidence.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Analyze again' })).toBeEnabled()
  await expect(page.getByRole('region', { name: 'Images used for AI analysis' })).toBeVisible()
  const first = page.getByRole('img', { name: 'AI input frame at 0.0s' })
  await expect.poll(() => first.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await expect(page.getByText('Image unavailable', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Retry image', exact: true }).click()
  const second = page.getByRole('img', { name: 'AI input frame at 0.5s' })
  await expect.poll(() => second.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Review sampled frame at 0.5s', exact: true }).click()
  await expect.poll(() => page.locator('dialog video').evaluate(video => (video as HTMLVideoElement).currentTime)).toBeCloseTo(0.5, 1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('analysis.png'), fullPage: true })
})

test('live navigation: camera selection, unsupported state and pending-start cleanup', async ({ page }) => {
  const cameras = [
    { id: 'first', name: 'First synthetic camera', live_view: 'experimental' },
    { id: 'second', name: 'Second synthetic camera', live_view: 'experimental' },
    { id: 'unavailable', name: 'Unavailable synthetic camera', live_view: 'disabled' },
  ].map(camera => ({ ...camera, family: 'doorbells', network_name: 'Synthetic network', observed_armed: null, recording_access: 'unverified' }))
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: cameras } }))
  let starts = 0
  let stops = 0
  let release = () => {}
  await page.route('**/api/v1/cameras/*/live', async route => {
    const index = ++starts
    await new Promise<void>(resolve => { release = resolve })
    await route.fulfill({ status: 202, json: { id: `pending-${index}`, camera_id: index === 1 ? 'first' : 'second', state: 'starting', message: 'Synthetic pending start', expires_at: new Date(Date.now() + 90000).toISOString(), bytes_received: 0, media_age_seconds: null } })
  })
  await page.route('**/api/v1/live/*/stop', route => { stops++; return route.fulfill({ status: 204 }) })
  await enterWorkspace(page)
  await page.getByRole('link', { name: 'Live View', exact: true }).click()
  expect(starts).toBe(0)
  await page.getByLabel('Camera', { exact: true }).selectOption('unavailable')
  await expect(page.getByRole('heading', { name: 'Live view unavailable', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start live view', exact: true })).toHaveCount(0)
  await page.getByLabel('Camera', { exact: true }).selectOption('first')
  await expect(page.getByRole('button', { name: 'Start live view', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Start live view from player', exact: true }).click()
  await expect.poll(() => starts).toBe(1)
  await expect(page.getByRole('button', { name: 'Start live view from player', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Starting…', exact: true })).toBeDisabled()
  await page.getByLabel('Camera', { exact: true }).selectOption('second')
  release()
  await expect.poll(() => stops).toBe(1)
  await expect(page.getByRole('heading', { name: 'Second synthetic camera', exact: true })).toBeVisible()
  await expect(page.getByText('Not started', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Start live view', exact: true }).click()
  await expect.poll(() => starts).toBe(2)
  await page.getByRole('link', { name: 'Activity', exact: true }).click()
  release()
  await expect.poll(() => stops).toBe(2)
  await page.goto('/#live')
  await expect(page.getByRole('link', { name: 'Live View', exact: true })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByText('Not started', { exact: true })).toBeVisible()
  expect(starts).toBe(2)
})

test('generated live capture UI: record, displayed-frame snapshot and Activity playback', async ({ page }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-capture-ui-'))
  const video = join(directory, 'generated.mp4')
  const executable = join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe')
  execFileSync(executable, ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=12:duration=3', '-an', '-c:v', 'libx264', '-threads', '2', '-profile:v', 'baseline', '-pix_fmt', 'yuv420p', '-g', '12', '-bf', '0', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', '-y', video])
  const cameraId = '00000000-0000-4000-8000-000000000031'
  const sessionId = '00000000-0000-4000-8000-000000000032'
  const recordingId = '00000000-0000-4000-8000-000000000033'
  const snapshotId = '00000000-0000-4000-8000-000000000034'
  let stopped = false
  let jpeg = Buffer.alloc(0)
  const captures: Array<{ id: string; camera_id: string; camera_name: string; kind: string; state: string; saved_at: string; bytes: number; duration_seconds: number | null; width: number; height: number; safe_error: null }> = []
  const capture = (id: string, kind: string, state: string) => ({ id, camera_id: cameraId, camera_name: 'Generated capture camera', kind, state, saved_at: new Date().toISOString(), bytes: 1000, duration_seconds: kind === 'recording' ? 3 : null, width: 320, height: 240, safe_error: null })
  const status = () => ({ id: sessionId, camera_id: cameraId, state: stopped ? 'ended' : 'receiving', message: 'Synthetic capture transport', expires_at: new Date(Date.now() + 90000).toISOString(), mime_type: 'video/mp4; codecs="avc1.42E01E"', audio_status: 'unavailable', bytes_received: 1000, media_age_seconds: 0, recording: captures.find(item => item.kind === 'recording') ?? null })
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: [{ id: cameraId, name: 'Generated capture camera', family: 'doorbells', network_name: 'Synthetic network', observed_armed: true, recording_access: 'unverified', live_view: 'experimental' }] } }))
  await page.route(`**/api/v1/cameras/${cameraId}/live`, route => route.fulfill({ status: 202, json: status() }))
  await page.route(`**/api/v1/live/${sessionId}/heartbeat`, route => route.fulfill({ json: status() }))
  await page.route(`**/api/v1/live/${sessionId}/media`, route => route.fulfill({ body: readFileSync(video), contentType: 'video/mp4; codecs="avc1.42E01E"' }))
  await page.route(`**/api/v1/live/${sessionId}/stop`, route => { stopped = true; return route.fulfill({ status: 204 }) })
  await page.route(`**/api/v1/live/${sessionId}/record`, route => { const result = capture(recordingId, 'recording', 'recording'); captures.push(result); return route.fulfill({ status: 201, json: result }) })
  await page.route(`**/api/v1/live/${sessionId}/record/stop`, route => { captures[0].state = 'ready'; return route.fulfill({ json: captures[0] }) })
  await page.route(`**/api/v1/live/${sessionId}/snapshot`, route => {
    jpeg = route.request().postDataBuffer() ?? Buffer.alloc(0)
    expect(jpeg.subarray(0, 2)).toEqual(Buffer.from([255, 216]))
    expect(route.request().headers()['content-type']).toBe('image/jpeg')
    const result = capture(snapshotId, 'snapshot', 'ready'); captures.push(result)
    return route.fulfill({ status: 201, json: result })
  })
  await page.route('**/api/v1/events?*', route => {
    const kind = new URL(route.request().url()).searchParams.get('media_kind')
    const selected = captures.filter(item => kind === 'snapshots' ? item.kind === 'snapshot' : kind === 'recordings' ? item.kind === 'recording' : true)
    return route.fulfill({ json: { items: selected.map(item => ({ id: item.id, source_type: `live_${item.kind}`, camera_id: item.camera_id, captured_at: item.saved_at, discovered_at: item.saved_at, timestamp_quality: 'local_capture', media_id: item.id, analysis_status: 'not_analyzed', summary: `Live ${item.kind} from ${item.camera_name}`, favourite: false, note: '', duration_seconds: item.duration_seconds ?? 0, capture: item })), next_cursor: null } })
  })
  await page.route(`**/api/v1/library/${recordingId}`, route => route.fulfill({ json: captures[0] }))
  await page.route(`**/api/v1/library/${recordingId}/media`, route => route.fulfill({ body: readFileSync(video), contentType: 'video/mp4' }))
  await page.route(`**/api/v1/library/${recordingId}/thumbnail`, route => route.fulfill({ body: jpeg, contentType: 'image/jpeg' }))
  await page.route(`**/api/v1/library/${snapshotId}/media`, route => route.fulfill({ body: jpeg, contentType: 'image/jpeg' }))
  try {
    await enterWorkspace(page)
    await page.getByRole('link', { name: 'Live View', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Record', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Snapshot', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: 'Start live view', exact: true }).click()
    await expect(page.getByText('LIVE', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Unmute audio', exact: true })).toBeDisabled()
    await expect(page.getByText('This session supplied no audio track.')).toBeVisible()
    await page.getByRole('button', { name: 'Record', exact: true }).click()
    await expect(page.getByText('Recording to Activity', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Snapshot', exact: true }).click()
    await expect(page.getByText('Snapshot saved to Activity.')).toBeVisible()
    expect(jpeg.length).toBeGreaterThan(1000)
    await page.screenshot({ path: testInfo.outputPath('recording-controls.png'), fullPage: true })
    await page.getByRole('button', { name: 'Stop recording', exact: true }).click()
    await expect(page.getByText('Recording saved to Activity.')).toBeVisible()
    await page.getByRole('link', { name: 'Activity', exact: true }).click()
    await expect.poll(() => stopped).toBe(true)
    await expect(page.locator('.activity-capture video')).toHaveCount(0)
    await page.locator('.activity-capture summary').filter({ hasText: 'Live snapshot from Generated capture camera' }).click()
    await page.locator('.activity-capture summary').filter({ hasText: 'Live recording from Generated capture camera' }).click()
    await expect(page.getByRole('img', { name: 'Snapshot from Generated capture camera' })).toBeVisible()
    await expect.poll(() => page.getByRole('img', { name: 'Snapshot from Generated capture camera' }).evaluate((element: HTMLImageElement) => element.naturalWidth)).toBe(320)
    await page.getByLabel('Recording from Generated capture camera').evaluate((element: HTMLVideoElement) => element.play())
    await expect.poll(() => page.getByLabel('Recording from Generated capture camera').evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0)
    await page.locator('.activity-capture summary').filter({ hasText: 'Live recording from Generated capture camera' }).click()
    await expect(page.getByLabel('Recording from Generated capture camera')).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Download snapshot', exact: true })).toBeVisible()
    const kind = page.getByRole('group', { name: 'Activity media type' })
    await kind.getByRole('button', { name: 'Snapshots', exact: true }).click()
    await expect(page.locator('.activity-capture')).toHaveCount(1)
    await expect(page.locator('.activity-capture summary')).toContainText('Live snapshot')
    await kind.getByRole('button', { name: 'Recordings', exact: true }).click()
    await expect(page.locator('.activity-capture')).toHaveCount(1)
    await expect(page.locator('.activity-capture summary')).toContainText('Live recording')
    await kind.getByRole('button', { name: 'All', exact: true }).click()
    await expect(page.locator('.activity-capture')).toHaveCount(2)
    await page.locator('.activity-capture summary').filter({ hasText: 'Live snapshot from Generated capture camera' }).click()
    await page.locator('.activity-capture summary').filter({ hasText: 'Live recording from Generated capture camera' }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('library.png'), fullPage: true })
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('synthetic live UI fixture: decoder, freshness, certificate review and cleanup', async ({ page }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-synthetic-live-'))
  const executable = join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe')
  const video = join(directory, 'generated.mp4')
  execFileSync(executable, ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=12:duration=3', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000:duration=3', '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'aac', '-c:v', 'libx264', '-threads', '2', '-profile:v', 'baseline', '-level:v', '3.0', '-pix_fmt', 'yuv420p', '-g', '12', '-bf', '0', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', '-y', video])
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  let stopped = false
  let starts = 0
  const cameraId = '00000000-0000-4000-8000-000000000001'
  const id = '00000000-0000-4000-8000-000000000002'
  const status = () => ({ id, camera_id: cameraId, state: stopped ? 'ended' : 'receiving', message: stopped ? 'Live view ended.' : 'Synthetic live transport fixture', expires_at: new Date(Date.now() + 90000).toISOString(), mime_type: 'video/mp4; codecs="avc1.42E01E,mp4a.40.2"', audio_status: 'available', bytes_received: 1000, media_age_seconds: 0 })
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: [{ id: cameraId, name: 'Generated camera fixture', family: 'doorbells', network_name: 'Synthetic network', observed_armed: true, recording_access: 'unverified', live_view: 'experimental' }] } }))
  await page.route(`**/api/v1/cameras/${cameraId}/live`, route => { starts++; return route.fulfill({ status: 202, json: status() }) })
  await page.route(`**/api/v1/live/${id}/heartbeat`, route => route.fulfill({ json: status() }))
  await page.route(`**/api/v1/live/${id}/stop`, route => { stopped = true; return route.fulfill({ status: 204 }) })
  await page.route(`**/api/v1/live/${id}/media`, route => route.fulfill({ body: readFileSync(video), contentType: 'video/mp4; codecs="avc1.42E01E,mp4a.40.2"', headers: { 'Cache-Control': 'no-store' } }))
  try {
    await enterWorkspace(page)
    await page.getByRole('link', { name: 'Live View', exact: true }).click()
    await expect(page).toHaveURL(/#live$/)
    await expect(page.getByRole('link', { name: 'Live View', exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByLabel('Camera', { exact: true })).toHaveValue(cameraId)
    await expect(page.getByText('Not started', { exact: true })).toBeVisible()
    expect(starts).toBe(0)
    await page.evaluate(() => Object.defineProperty(document, 'fullscreenEnabled', { configurable: true, value: false }))
    await page.getByRole('button', { name: 'Enter fullscreen', exact: true }).click()
    await expect(page.getByText('Fullscreen is unavailable in this browser.')).toBeVisible()
    await page.evaluate(() => Reflect.deleteProperty(document, 'fullscreenEnabled'))
    await expect(page.getByRole('button', { name: 'Start live view', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Start live view from player', exact: true }).click()
    await expect(page.getByText('LIVE', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start live view from player', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Play', exact: true })).toHaveCount(0)
    expect(await page.locator('video').evaluate((element: HTMLVideoElement) => element.currentTime > 0 && element.videoWidth > 0)).toBe(true)
    expect(await page.locator('video').evaluate((element: HTMLVideoElement) => element.muted)).toBe(true)
    await page.getByRole('button', { name: 'Unmute audio', exact: true }).click()
    expect(await page.locator('video').evaluate((element: HTMLVideoElement) => element.muted)).toBe(false)
    const volume = page.getByRole('slider', { name: 'Live audio volume', exact: true })
    await volume.focus()
    await page.keyboard.press('Home')
    await page.keyboard.press('ArrowRight')
    await expect.poll(() => page.locator('video').evaluate((element: HTMLVideoElement) => element.volume)).toBeCloseTo(0.05)
    await page.getByRole('button', { name: 'Mute audio', exact: true }).click()
    expect(await page.locator('video').evaluate((element: HTMLVideoElement) => element.muted)).toBe(true)
    await page.getByRole('button', { name: 'Network controls · Armed', exact: true }).click()
    await expect(page.getByRole('dialog', { name: 'Synthetic network', exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    expect(stopped).toBe(false)
    expect(starts).toBe(1)
    await page.getByRole('button', { name: 'Enter fullscreen', exact: true }).click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement?.classList.contains('live-screen'))).toBe(true)
    await page.locator('.live-screen-controls').getByRole('button', { name: 'Unmute audio', exact: true }).click()
    expect(await page.locator('video').evaluate((element: HTMLVideoElement) => element.muted)).toBe(false)
    await page.locator('.live-screen-controls').getByRole('button', { name: 'Mute audio', exact: true }).click()
    expect(starts).toBe(1)
    await page.screenshot({ path: testInfo.outputPath('live-fullscreen.png') })
    await page.getByRole('button', { name: 'Exit fullscreen', exact: true }).click()
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('live.png'), fullPage: true })
    await page.locator('video').evaluate((element: HTMLVideoElement) => element.pause())
    await expect(page.getByText('LIVE', { exact: true })).not.toBeVisible()
    await page.getByRole('button', { name: 'Play', exact: true }).click()
    await expect(page.getByText('LIVE', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Play', exact: true })).toHaveCount(0)
    expect(starts).toBe(1)
    await page.locator('video').evaluate((element: HTMLVideoElement) => element.pause())
    await expect(page.getByText('LIVE', { exact: true })).not.toBeVisible()
    await expect(page.getByText('Waiting for fresh video…')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start live view from player', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Enter fullscreen', exact: true }).click()
    await page.locator('.live-screen-controls').getByRole('button', { name: 'Stop live view', exact: true }).click()
    await expect(page.getByText('Live view ended.', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start live view from player', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Exit fullscreen', exact: true }).click()
    stopped = false
    await page.getByRole('button', { name: 'Start live view', exact: true }).click()
    await expect(page.getByText('LIVE', { exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Activity', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Live View', exact: true })).not.toBeVisible()
    await expect.poll(() => stopped).toBe(true)
    expect(starts).toBe(2)
    let approved = false
    const fingerprint = 'a'.repeat(64)
    await page.route(`**/api/v1/cameras/${cameraId}/live`, route => route.fulfill({ status: 202, json: { ...status(), state: 'failed', message: 'Blink’s live relay needs certificate review.', certificate_sha256: fingerprint } }))
    await page.route(`**/api/v1/live/${id}/trust-certificate`, route => { approved = true; return route.fulfill({ status: 204 }) })
    await page.getByRole('link', { name: 'Live View', exact: true }).click()
    await page.getByRole('button', { name: 'Start live view', exact: true }).click()
    await expect(page.getByText('Review Blink relay certificate', { exact: true })).toBeVisible()
    await expect(page.getByText(fingerprint, { exact: true })).toBeVisible()
    expect(approved).toBe(false)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('certificate.png'), fullPage: true })
    await page.getByRole('button', { name: 'Trust this certificate for Porchlight', exact: true }).click()
    await expect.poll(() => approved).toBe(true)
    await expect(page.getByText('Certificate pinned for Porchlight.', { exact: false })).toBeVisible()
    await page.getByRole('link', { name: 'Activity', exact: true }).click()
    expect(errors).toEqual([])
  } finally { rmSync(directory, { recursive: true, force: true }) }
})
