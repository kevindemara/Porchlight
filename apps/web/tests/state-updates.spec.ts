import { test, expect } from '@playwright/test'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { execFileSync } from 'node:child_process'
import { enterWorkspace } from './session'

test('actual authenticated event stream refreshes activity and expires a revoked session', async ({ page }, testInfo) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-sse-fixture-'))
  const video = join(directory, 'generated.mp4')
  execFileSync(join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=purple:s=320x240:d=1', '-c:v', 'mpeg4', '-y', video])
  try {
  // Disable ordinary polling so this journey specifically proves the SSE path.
  await page.addInitScript(() => { window.setInterval = () => 0 })
  await enterWorkspace(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Activity', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Activity', exact: true })).toBeVisible()
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  const origin = new URL(page.url()).origin
  const headers = { Origin: origin, 'X-CSRF-Token': session.csrf_token }
  const uploaded = await page.request.post('/api/v1/imports', {
    headers: { ...headers, 'Content-Type': 'video/mp4' },
    data: readFileSync(video),
  })
  expect(uploaded.status()).toBe(201)
  const recording = await uploaded.json()
  const summary = `Synthetic live update ${testInfo.project.name}`
  const patched = await page.request.patch(`/api/v1/events/${recording.id}/annotation`, {
    headers, data: { favourite: false, note: '', corrected_summary: summary },
  })
  expect(patched.status()).toBe(200)
  await expect(page.getByText(summary, { exact: true })).toBeVisible({ timeout: 6000 })
  const revoked = await page.request.post('/api/v1/auth/logout', { headers })
  expect(revoked.status()).toBe(204)
  await expect(page.getByRole('heading', { name: 'Sign in to Porchlight' })).toBeVisible({ timeout: 6000 })
  } finally { rmSync(directory, { recursive: true, force: true }) }
})
