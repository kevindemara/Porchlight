import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('network modal preserves space, keyboard focus, disable confirmation and command read-back', async ({ page }, info) => {
  const id = '00000000-0000-4000-8000-000000000092'
  let armed = true
  let submissions = 0
  let verifications = 0
  let command: Record<string, unknown> | null = null
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: [{ id, name: 'Synthetic porch', network_name: 'Synthetic home', network_id: 'synthetic-network', family: 'doorbells', observed_armed: armed, observed_motion: true, network_control: true, motion_control: true, recording_access: 'unverified', live_view: 'experimental' }] } }))
  await page.route(`**/api/v1/cameras/${id}/commands/latest*`, route => route.fulfill({ json: command }))
  await page.route(`**/api/v1/cameras/${id}/commands`, route => {
    submissions++
    const body = route.request().postDataJSON()
    expect(body.operation).toBe('network_armed')
    expect(body.desired).toBe(false)
    expect(body.confirm_disable).toBe(true)
    command = { id: body.request_id, camera_id: id, operation: body.operation, desired: false, state: 'pending', observed: null, safe_error: null, created_at: '2026-10-08T12:00:00Z' }
    return route.fulfill({ status: 202, json: command })
  })
  await page.route('**/api/v1/camera-commands/*', route => {
    command = { ...command, state: 'unknown', safe_error: 'READBACK_UNCONFIRMED' }
    return route.fulfill({ json: command })
  })
  await page.route('**/api/v1/camera-commands/*/verify', route => {
    verifications++; armed = false
    command = { ...command, state: 'confirmed', observed: false, safe_error: null }
    return route.fulfill({ json: command })
  })
  await enterWorkspace(page)
  const trigger = page.getByRole('button', { name: /^Network controls ·/ })
  const dialog = page.getByRole('dialog', { name: 'Synthetic home', exact: true })
  await expect(trigger).toHaveAccessibleName('Network controls · Armed')
  await expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')
  await expect(page.locator('.live-network-status')).toHaveCount(0)
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('Not started', { exact: true })).toBeVisible()
  await expect(page.getByText('Experimental live view', { exact: true })).toHaveCount(0)
  expect(submissions).toBe(0)
  await page.screenshot({ path: info.outputPath('compact-network-button.png'), fullPage: true })
  await trigger.click()
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Close network controls', exact: true })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(dialog.getByRole('button', { name: 'Disarm network', exact: true })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: 'Close network controls', exact: true })).toBeFocused()
  await dialog.getByRole('button', { name: 'Disarm network', exact: true }).click()
  await expect(dialog.getByRole('group', { name: 'Confirm camera change' })).toContainText('Disarm all cameras in Synthetic home?')
  expect(submissions).toBe(0)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
  await trigger.click()
  await expect(dialog.getByRole('group', { name: 'Confirm camera change' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Disarm network', exact: true }).click()
  await dialog.getByRole('button', { name: 'Confirm disarm', exact: true }).click()
  await expect(dialog.getByText('The outcome is unconfirmed.', { exact: false })).toBeVisible()
  await expect(trigger).toHaveAccessibleName('Network controls · Armed')
  await dialog.getByRole('button', { name: 'Close network controls', exact: true }).click()
  await expect(trigger).toBeFocused()
  await trigger.click()
  await expect(dialog.getByText('The outcome is unconfirmed.', { exact: false })).toBeVisible()
  expect(submissions).toBe(1)
  await dialog.getByRole('button', { name: 'Verify current state', exact: true }).click()
  await expect(dialog.getByText('Blink read-back confirmed this command.', { exact: true })).toBeVisible()
  await expect(trigger).toHaveAccessibleName('Network controls · Disarmed')
  await expect(dialog.getByRole('button', { name: 'Arm network', exact: true })).toBeEnabled()
  expect(submissions).toBe(1); expect(verifications).toBe(1)
  const bounds = await dialog.boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark' })
  await page.screenshot({ path: info.outputPath('network-modal-dark.png') })
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
  await expect(page.getByText('Not started', { exact: true })).toBeVisible()
})
