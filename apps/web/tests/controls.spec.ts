import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { enterWorkspace } from './session'

test('synthetic camera controls confirm disabling and verify unknown outcomes without replay', async ({ page }, testInfo) => {
  const cameraId = 'e74a5649-a2ed-44b0-89fd-0845a2ef76c5'
  let motion = true
  let submissions = 0
  let verifications = 0
  let command: Record<string, unknown> | null = null
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: [{
    id: cameraId, name: 'Synthetic control camera', network_name: 'Synthetic network', family: 'doorbells',
    observed_armed: true, observed_motion: motion, network_control: true, motion_control: true,
    observed_at: '2026-10-07T12:00:00Z', battery_state: 'ok', temperature_c: 20, recording_access: 'unverified', live_view: 'disabled',
  }] } }))
  await page.route(`**/api/v1/cameras/${cameraId}/commands/latest*`, route => { const operation = new URL(route.request().url()).searchParams.get('operation'); return route.fulfill({ json: operation && command?.operation !== operation ? null : command }) })
  await page.route(`**/api/v1/cameras/${cameraId}/commands`, route => {
    submissions++
    const body = route.request().postDataJSON()
    expect(body.confirm_disable).toBe(true)
    command = { id: body.request_id, camera_id: cameraId, operation: body.operation, desired: body.desired, state: 'pending', observed: null, safe_error: null, created_at: '2026-10-07T12:00:00Z' }
    return route.fulfill({ status: 202, json: command })
  })
  await page.route('**/api/v1/camera-commands/*', route => route.fulfill({ json: { ...command, state: 'unknown', safe_error: 'READBACK_UNCONFIRMED' } }))
  await page.route('**/api/v1/camera-commands/*/verify', route => {
    verifications++; motion = false
    command = { ...command, state: 'confirmed', observed: false, safe_error: null }
    return route.fulfill({ json: command })
  })
  await enterWorkspace(page)
  await expect(page.getByRole('heading', { name: 'Synthetic control camera' })).toBeVisible()
  await page.getByText('Camera controls and status', { exact: true }).click()
  await page.getByRole('button', { name: 'Disarm network', exact: true }).click()
  await expect(page.getByText('Disarm all cameras in Synthetic network?', { exact: false })).toBeVisible()
  expect(submissions).toBe(0)
  await page.getByRole('button', { name: 'Cancel change' }).click()
  await page.getByRole('button', { name: 'Disable motion detection', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm disable motion' }).click()
  await expect(page.getByText('The outcome is unconfirmed.', { exact: false })).toBeVisible()
  await expect(page.getByText('Motion detection: enabled', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Verify current state' }).click()
  await expect(page.getByText('Blink read-back confirmed this command.', { exact: true })).toBeVisible()
  await expect(page.getByText('Motion detection: disabled', { exact: true })).toBeVisible()
  expect(submissions).toBe(1); expect(verifications).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('camera-controls.png'), fullPage: true })
  await page.reload()
  await page.getByText('Camera controls and status', { exact: true }).click()
  await expect(page.getByText('Blink read-back confirmed this command.', { exact: true })).toBeVisible()
  expect(submissions).toBe(1)
  let localEnabled = false
  const localStatus = () => ({ eligible: true, modules: [{ id: cameraId, name: 'Synthetic module', storage_ready: true, message: 'Synthetic active-storage metadata. Hardware unverified.', checked_at: '2026-10-07T12:00:00Z' }], sync: { enabled: localEnabled, source: 'blink_local', discovered: 0, archived: 0, pending: 0, failed: 0, state: localEnabled ? 'queued' : 'not_started', message: 'Synthetic local-storage fixture.', no_plan_verified: false } })
  await page.route('**/api/v1/integrations/blink/local-recordings', route => route.fulfill({ json: localStatus() }))
  await page.route('**/api/v1/integrations/blink/local-sync', route => {
    localEnabled = route.request().postDataJSON().enabled
    return route.fulfill({ status: 202, json: localStatus() })
  })
  await page.getByRole('navigation').getByRole('link', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sync Module local storage', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Sync local recordings', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Pause local sync', exact: true })).toBeVisible()
  expect(localEnabled).toBe(true)
  await page.getByRole('button', { name: 'Pause local sync', exact: true }).click()
  expect(localEnabled).toBe(false)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download redacted diagnostics' }).click()
  const file = await download
  expect(file.suggestedFilename()).toBe('porchlight-diagnostics.json')
  const report = JSON.parse(readFileSync((await file.path())!, 'utf8'))
  expect(report.format).toBe('porchlight-redacted-diagnostics-v1')
  expect(report.excluded).toContain('credentials')
  await page.screenshot({ path: testInfo.outputPath('local-storage-settings.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
