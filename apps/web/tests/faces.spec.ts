import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { enterWorkspace } from './session'

test('local face detection: native clip, separate automatic toggle and reviewed timestamp UI', async ({ page }, info) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-face-ui-'))
  const errors: string[] = []
  page.on('pageerror', err => errors.push(err.message))
  try {
    const file = join(directory, 'generated.mp4')
    execFileSync(join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=orange:s=320x240:d=2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-y', file])
    await enterWorkspace(page)
    await page.getByRole('link', { name: 'Faces', exact: true }).click()
    const automatic = page.getByLabel('Detect faces in new Blink recordings automatically')
    await expect(automatic).not.toBeChecked()
    const detector = await (await page.request.get('/api/v1/face-detection/status')).json()
    if (!detector.ready) {
      await expect(automatic).toBeDisabled()
      await expect(page.getByText(detector.message, { exact: true })).toBeVisible()
      return // Portable no-install behavior; native backend test marks missing model explicitly.
    }
    await automatic.click()
    await expect(automatic).toBeChecked()
    await expect.poll(async () => (await (await page.request.get('/api/v1/face-detection/status')).json()).enabled).toBe(true)
    await automatic.click()
    await expect(automatic).not.toBeChecked()
    await expect.poll(async () => (await (await page.request.get('/api/v1/face-detection/status')).json()).enabled).toBe(false)
    if (detector.recognition_ready) {
      const autoSamples = page.getByLabel('Automatically add exceptionally strong face matches as samples')
      await expect(autoSamples).toBeEnabled()
      await autoSamples.click()
      await expect(autoSamples).toBeChecked()
      await expect.poll(async () => (await (await page.request.get('/api/v1/face-detection/status')).json()).auto_enroll_enabled).toBe(true)
      await autoSamples.click()
      await expect(autoSamples).not.toBeChecked()
      await expect.poll(async () => (await (await page.request.get('/api/v1/face-detection/status')).json()).auto_enroll_enabled).toBe(false)
    }
    await page.screenshot({ path: info.outputPath('face-settings.png'), fullPage: true })
    const session = await (await page.request.get('/api/v1/auth/session')).json()
    const imported = await page.request.post('/api/v1/imports', { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token, 'Content-Type': 'video/mp4' }, data: readFileSync(file) })
    expect(imported.status()).toBe(201)
    const event = await imported.json()
    await page.getByRole('link', { name: 'Activity', exact: true }).click()
    await page.getByRole('button', { name: /Imported recording/ }).first().click()
    await expect.poll(() => page.locator('dialog video').evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2)
    const panel = page.locator('.face-detection')
    await expect(panel.getByRole('button', { name: 'Detect faces', exact: true })).toBeEnabled()
    await panel.getByRole('button', { name: 'Detect faces', exact: true }).click()
    await expect(panel.getByText('No faces detected in sampled frames', { exact: true })).toBeVisible({ timeout: 20000 })
    const saved = await (await page.request.get(`/api/v1/events/${event.id}/faces`)).json()
    expect(saved.status).toBe('done')
    expect(saved.report.frames).toHaveLength(8)
    expect((await (await page.request.get('/api/v1/face-detection/status')).json()).enabled).toBe(false)
    expect((await (await page.request.get(`/api/v1/events/${event.id}`)).json()).analysis_status).toBe('not_analyzed')
    await page.screenshot({ path: info.outputPath('native-face-detail.png') })
    // Only the positive rendering fixture is simulated. Native inference above used generated video.
    await page.route(`**/api/v1/events/${event.id}/faces`, route => route.request().method() === 'GET'
      ? route.fulfill({ json: { ...saved, report: { ...saved.report, frames: saved.report.frames.map((frame: object) => ({ ...frame, faces: [{ x: 10, y: 15, width: 30, height: 40, score: .95, small: true, low_sharpness: true }] })) } } })
      : route.continue())
    await expect(panel.getByText('Up to 1 face visible in a sampled frame', { exact: true })).toBeVisible()
    await expect(panel.getByText(/No people have been named yet/)).toBeVisible()
    await expect(panel.getByText('1 face · small face · low sharpness').first()).toBeVisible()
    // Recognition is a separate local result, surfaced alongside the AI description.
    await page.route(`**/api/v1/events/${event.id}`, async route => {
      const response = await route.fetch()
      const detail = await response.json()
      await route.fulfill({ response, json: { ...detail, summary: 'Someone visited the door.', recognized_people: ['Alex'] } })
    })
    await page.route(`**/api/v1/events/${event.id}/analysis`, route => route.fulfill({ json: {
      revision: 1, model: 'synthetic-local-model', model_digest: 'synthetic', created_at: new Date().toISOString(),
      elapsed_seconds: 1, frame_count: 2, workload: 'balanced', uncertainty: [], entities: [],
      sample_offsets_ms: [], evidence_frames: [], scene_visibility: 'clear',
    } }))
    await expect(page.locator('dialog').getByText('Someone visited the door. Possible face match: Alex.')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('dialog').getByText('Local face recognition suggests Alex. Please verify against the recording.')).toBeVisible()
    await panel.getByRole('button', { name: 'Review faces at 1.9 seconds', exact: true }).click()
    await expect.poll(() => page.locator('dialog video').evaluate((video: HTMLVideoElement) => video.currentTime)).toBeCloseTo(1.88, 1)
    await panel.getByText('Detection details', { exact: true }).click()
    await expect(panel.getByText(/uncalibrated heuristics/)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    expect(errors).toEqual([])
    await page.screenshot({ path: info.outputPath('synthetic-positive-faces.png') })
    await page.getByRole('button', { name: 'Close recording' }).click()
    await page.unroute(`**/api/v1/events/${event.id}/faces`)
    expect((await page.request.delete(`/api/v1/events/${event.id}`, { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token } })).status()).toBe(204)
    expect((await page.request.get(`/api/v1/events/${event.id}/faces`)).status()).toBe(404)
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('name a synthetic face in Faces, then rename and remove its local profile', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await enterWorkspace(page)
  const id = 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d'
  const eventId = 'e2084102-74da-463d-b5f4-d255744090f5'
  let people: { id: string; name: string; created_at: string; samples: number }[] = []
  await page.route('**/api/v1/face-detection/people**', async route => {
    const method = route.request().method()
    if (method === 'GET') return route.fulfill({ json: { people } })
    if (method === 'POST') {
      const body = route.request().postDataJSON() as { name?: string; person_id?: string }
      people = body.person_id
        ? [{ ...people[0], samples: people[0].samples + 1 }]
        : [{ id, name: body.name!, created_at: '2026-10-08T00:00:00Z', samples: 1 }]
      return route.fulfill({ status: 201, json: people[0] })
    }
    if (method === 'PATCH') {
      const body = route.request().postDataJSON() as { name: string }
      people = [{ ...people[0], name: body.name }]
      return route.fulfill({ json: people[0] })
    }
    people = []
    return route.fulfill({ status: 204, body: '' })
  })
  await page.route('**/api/v1/face-detection/candidates', route => route.fulfill({ json: { faces: [{
    event_id: eventId, captured_at: '2026-10-08T00:00:00Z', offset_ms: 1200,
    face_index: 0, width: 320, height: 240,
    box: { x: 80, y: 40, width: 100, height: 100, score: .99, small: false, low_sharpness: false, profile_id: null, match_score: null },
  }] } }))
  await page.route('**/api/v1/events/*/faces/frames/*', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240"><rect width="320" height="240" fill="#b5c9bd"/><circle cx="130" cy="90" r="42" fill="#6c8174"/></svg>',
  }))
  await page.getByRole('link', { name: 'Faces', exact: true }).click()
  const section = page.locator('.face-people')
  await expect(section.getByText('Recognize familiar people')).toBeVisible()
  await section.getByText(/Choose a face to name/).click()
  await expect(section.locator('.face-candidate')).toHaveCount(1)
  await section.locator('.face-candidate').click()
  await section.getByLabel('Name this selected face').fill('Alex')
  await section.getByRole('button', { name: 'Save person' }).click()
  await expect(section.getByLabel('Name for Alex')).toHaveValue('Alex')
  await section.getByLabel('Name for Alex').fill('Sam')
  await section.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(section.getByLabel('Name for Sam')).toHaveValue('Sam')
  await section.locator('.face-candidate').click()
  await section.getByLabel('Save face as').selectOption(id)
  await section.getByRole('button', { name: 'Add sample' }).click()
  await expect(section.getByText('2 samples', { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: info.outputPath('synthetic-named-person-settings.png'), fullPage: true })
  page.once('dialog', dialog => { void dialog.accept() })
  await section.getByRole('button', { name: 'Remove' }).click()
  await expect(section.getByLabel('Name for Sam')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
  await page.screenshot({ path: info.outputPath('synthetic-face-people-settings.png'), fullPage: true })
})

test('gallery multi-select assigns photos across cards to an existing person', async ({ page }, info) => {
  await enterWorkspace(page)
  const personId = 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d'
  const eventId = 'e2084102-74da-463d-b5f4-d255744090f5'
  const secondEventId = '73e8773e-9f53-4c11-ad9e-f16eef6d728e'
  let samples = 8
  let assigned = 0
  const person = () => ({ id: personId, name: 'Known person', created_at: '2026-10-08T00:00:00Z', samples })
  const candidate = (offset_ms: number, event_id = eventId) => ({
    event_id, captured_at: '2026-10-08T00:00:00Z', offset_ms,
    face_index: 0, width: 320, height: 240,
    box: { x: 80, y: 40, width: 100, height: 100, score: .99, small: false, low_sharpness: false, profile_id: null, match_score: null },
  })
  await page.route('**/api/v1/face-detection/gallery', route => route.fulfill({ json: {
    groups: [
      { id: 'unknown-synthetic', person_id: null, name: null, suggested_person_id: personId, suggested_name: 'Known person', sightings: 2, samples: [candidate(1200), candidate(1600)] },
      { id: 'unknown-other', person_id: null, name: null, sightings: 1, samples: [candidate(2500, secondEventId)] },
    ],
    recordings_reviewed: 2, omitted_faces: 0,
  } }))
  await page.route('**/api/v1/face-detection/people**', route => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as { samples: { event_id: string }[] }
      assigned = body.samples.length
      expect(new Set(body.samples.map(sample => sample.event_id)).size).toBe(2)
      samples += assigned
      return route.fulfill({ status: 201, json: person() })
    }
    return route.fulfill({ json: { people: [person()] } })
  })
  await page.route('**/api/v1/events/*/faces/thumbnails/**', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40" fill="#748b74"/></svg>',
  }))
  await page.getByRole('link', { name: 'Faces', exact: true }).click()
  const groups = page.locator('.face-group-card')
  await expect(groups).toHaveCount(3)
  await expect(groups.first().getByRole('heading', { name: 'Known person' })).toBeVisible()
  await expect(groups.nth(1).locator('.face-group-photo')).toHaveCount(2)
  await expect(groups.nth(1).getByText('Possible match: Known person')).toBeVisible()
  await groups.nth(1).getByRole('button', { name: 'Select photos' }).click()
  await expect(page.locator('.face-batch-form').getByLabel('Save faces as')).toHaveValue(personId)
  await groups.nth(2).locator('.face-group-photo').click()
  await expect(page.locator('.face-group-photo[aria-pressed="true"]')).toHaveCount(3)
  await expect(page.getByRole('region', { name: 'Selected faces' })).toBeVisible()
  await page.getByRole('button', { name: 'Assign a name' }).click()
  const batch = page.locator('.face-batch-form')
  await expect(batch).toBeInViewport()
  await expect(batch.getByText('3 of 12 images selected.')).toBeVisible()
  await expect(batch.getByLabel('Save faces as')).toHaveValue('')
  await batch.getByLabel('Save faces as').selectOption(personId)
  await page.screenshot({ path: info.outputPath('synthetic-face-batch-selection.png'), fullPage: true })
  await batch.getByRole('button', { name: 'Assign 3 images' }).click()
  await expect(page.getByRole('status').getByText('3 images assigned. Future scans can compare these face samples.')).toBeVisible()
  await expect(page.locator('.face-person-row').getByText('11 samples')).toBeVisible()
  expect(assigned).toBe(3)
  expect(samples).toBe(11)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('synthetic-face-gallery.png'), fullPage: true })
})

test('Faces page loads older scans and combines known-person cards', async ({ page }, info) => {
  await enterWorkspace(page)
  const personId = 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d'
  const olderPersonId = '16a65947-633a-4ba0-beb6-c151dca28e1e'
  const candidate = (event_id: string) => ({
    event_id, captured_at: '2026-01-01T00:00:00Z', offset_ms: 0,
    face_index: 0, width: 320, height: 240,
    box: { x: 80, y: 40, width: 100, height: 100, score: .99, small: false, low_sharpness: false, profile_id: personId, match_score: .9 },
  })
  const unknown = candidate('40ac775d-f43c-4864-a25f-572c768d7311')
  const olderSample = candidate('81eb5e5a-ae64-4764-bfb2-fd367d024249')
  olderSample.box.profile_id = olderPersonId
  await page.route('**/api/v1/face-detection/gallery**', route => {
    const older = new URL(route.request().url()).searchParams.get('offset') === '20'
    return route.fulfill({ json: {
      groups: [
        ...(!older ? [{ id: 'unidentified', person_id: null, name: null, sightings: 1,
          samples: [{ ...unknown, box: { ...unknown.box, profile_id: null, match_score: null } }] }] : []),
        { id: personId, person_id: personId, name: 'Known person', sightings: older ? 2 : 3,
          samples: [candidate(older ? '73e8773e-9f53-4c11-ad9e-f16eef6d728e' : 'e2084102-74da-463d-b5f4-d255744090f5')] },
        ...(older ? [{ id: olderPersonId, person_id: olderPersonId, name: 'Older saved person', sightings: 1,
          samples: [olderSample] }] : []),
      ],
      saved_people: [
        { person_id: personId, name: 'Known person', samples: [candidate('e2084102-74da-463d-b5f4-d255744090f5')] },
        { person_id: olderPersonId, name: 'Older saved person', samples: [olderSample] },
      ],
      recordings_reviewed: older ? 2 : 20, total_recordings: 22,
      next_offset: older ? null : 20, omitted_faces: 0,
    } })
  })
  await page.route('**/api/v1/face-detection/people**', route => route.fulfill({ json: { people: [] } }))
  await page.route('**/api/v1/events/*/faces/thumbnails/**', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>',
  }))
  await page.getByRole('link', { name: 'Faces', exact: true }).click()
  await expect(page.getByText('20 of 22 scanned recordings loaded')).toBeVisible()
  await expect(page.locator('.face-group-card').first().getByRole('heading', { name: 'Known person' })).toBeVisible()
  await expect(page.locator('.face-group-card').nth(1).getByRole('heading', { name: 'Older saved person' })).toBeVisible()
  await expect(page.locator('.face-group-card').nth(1).locator('.face-group-photo')).toHaveCount(1)
  await page.screenshot({ path: info.outputPath('synthetic-all-saved-people-initially.png'), fullPage: true })
  await page.getByRole('button', { name: 'Load older detections' }).click()
  await expect(page.getByText('22 of 22 scanned recordings loaded')).toBeVisible()
  await expect(page.locator('.face-group-card')).toHaveCount(3)
  await expect(page.locator('.face-group-card').first().getByRole('heading', { name: 'Known person' })).toBeVisible()
  await expect(page.locator('.face-group-card').nth(1).getByRole('heading', { name: 'Older saved person' })).toBeVisible()
  await expect(page.locator('.face-group-card').last().getByRole('heading', { name: 'Unidentified appearance' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('synthetic-named-faces-first.png'), fullPage: true })
  await expect(page.getByRole('button', { name: 'Load older detections' })).toHaveCount(0)
})

test('suggested matches let the owner set aside one image and approve the rest', async ({ page }, info) => {
  await enterWorkspace(page)
  const personId = 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d'
  const eventId = 'e2084102-74da-463d-b5f4-d255744090f5'
  const face = (offset_ms: number) => ({
    event_id: eventId, captured_at: '2026-10-08T00:00:00Z', offset_ms,
    frame_sha256: 'a'.repeat(64),
    face_index: 0, width: 320, height: 240,
    box: { x: 80, y: 40, width: 100, height: 100, score: .9, small: false, low_sharpness: false, profile_id: null, match_score: null },
  })
  const suggestions = [1000, 1250, 1500].map(offset => ({ face: face(offset), person_id: personId, name: 'Known person' }))
  const savedFace = { ...face(500), box: { ...face(500).box, profile_id: personId } }
  let approved: number[] = []
  let galleryRequests = 0
  await page.route('**/api/v1/face-detection/gallery**', route => { galleryRequests += 1; return route.fulfill({ json: {
    groups: [{ id: personId, person_id: personId, name: 'Known person', sightings: 17, samples: [savedFace] }],
    suggestions: approved.length ? suggestions.slice(1, 2) : suggestions,
    labeled_totals: { [personId]: approved.length ? 19 : 17 },
    confirmed_totals: { [personId]: approved.length ? 9 : 7 },
    recordings_reviewed: 1, total_recordings: 1, next_offset: null, omitted_faces: 0,
  } }) })
  await page.route('**/api/v1/face-detection/people**', route => route.fulfill({ json: { people: [] } }))
  await page.route('**/api/v1/face-detection/suggestions/approve', route => {
    const body = route.request().postDataJSON() as { person_id: string; faces: { offset_ms: number }[] }
    expect(body.person_id).toBe(personId)
    approved = body.faces.map(item => item.offset_ms)
    return route.fulfill({ json: { labeled: approved.length, total_labeled: 19, total_confirmed: 9 } })
  })
  await page.route('**/api/v1/events/*/faces/thumbnails/**', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>',
  }))
  await page.getByRole('link', { name: 'Faces', exact: true }).click()
  const section = page.getByRole('region', { name: 'Suggested matches' })
  await expect(section.getByRole('button', { name: /Remove face/ })).toHaveCount(3)
  await section.getByRole('button', { name: 'Remove face at 1.3 seconds from suggested Known person group' }).click()
  await expect(section.getByText('1 image set aside and left unnamed.')).toBeVisible()
  await expect(section.getByRole('button', { name: 'Approve 2 for Known person' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('synthetic-face-suggestions.png'), fullPage: true })
  await section.getByRole('button', { name: 'Approve 2 for Known person' }).click()
  await expect(page.getByRole('status').getByText('2 faces labeled as Known person.')).toBeVisible()
  await expect(page.locator('.face-group-card').getByText('9 owner-confirmed detections · 10 model matches')).toBeVisible()
  await expect(page.locator('.face-group-card').getByText('17 grouped in loaded scans')).toBeVisible()
  await page.screenshot({ path: info.outputPath('synthetic-face-counts.png'), fullPage: true })
  expect(approved).toEqual([1000, 1500])
  expect(galleryRequests).toBe(1)
  await page.getByRole('button', { name: 'Refresh' }).click()
  await expect(page.locator('.face-group-card').getByText('9 owner-confirmed detections · 10 model matches')).toBeVisible()
  await expect(section.getByText('1 image set aside and left unnamed.')).toBeVisible()
})

test('one action gathers suggested matches from every scanned page', async ({ page }) => {
  await enterWorkspace(page)
  const personId = 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d'
  let requests = 0
  await page.route('**/api/v1/face-detection/gallery**', route => {
    requests += 1
    const offset = Number(new URL(route.request().url()).searchParams.get('offset') ?? '0')
    const face = {
      event_id: offset === 0 ? 'e2084102-74da-463d-b5f4-d255744090f5' : offset === 20 ? '73e8773e-9f53-4c11-ad9e-f16eef6d728e' : '40ac775d-f43c-4864-a25f-572c768d7311',
      captured_at: '2026-10-08T00:00:00Z', frame_sha256: 'a'.repeat(64),
      offset_ms: 0, face_index: 0, width: 320, height: 240,
      box: { x: 80, y: 40, width: 100, height: 100, score: .9, small: false, low_sharpness: false, profile_id: null, match_score: null },
    }
    return route.fulfill({ json: {
      groups: [], suggestions: [{ face, person_id: personId, name: 'Known person' }],
      recordings_reviewed: offset === 40 ? 5 : 20, total_recordings: 45,
      next_offset: offset === 40 ? null : offset + 20, omitted_faces: 0,
    } })
  })
  await page.route('**/api/v1/face-detection/people**', route => route.fulfill({ json: { people: [] } }))
  await page.route('**/api/v1/events/*/faces/thumbnails/**', route => route.fulfill({
    contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>',
  }))
  await page.getByRole('link', { name: 'Faces', exact: true }).click()
  await page.getByRole('button', { name: 'Gather all saved scans' }).click()
  await expect(page.getByText('All 45 saved scans are loaded for review.')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Suggested matches' }).getByRole('button', { name: /Remove face/ })).toHaveCount(3)
  expect(requests).toBe(3)
})
