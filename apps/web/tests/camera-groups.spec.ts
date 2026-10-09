import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('camera arrangement separates identically named networks and supports local groups', async ({ page }, testInfo) => {
  const cameras = [
    { id: '7a87d6af-292f-4e5b-b8a8-25261edfdcb7', name: 'Synthetic porch', network_id: 'network-one', observed_armed: true, group: 'Front yard' },
    { id: '25742683-801b-45b5-8a7d-f67d6c84c59f', name: 'Synthetic driveway', network_id: 'network-one', observed_armed: true, group: 'Front yard' },
    { id: 'de0511da-7270-4cda-aac9-8d06c33fe142', name: 'Synthetic back yard', network_id: 'network-two', observed_armed: null, group: '' },
  ].map(camera => ({ ...camera, family: 'cameras', network_name: 'Home', network_control: true, motion_control: true, observed_motion: true, live_view: 'disabled', recording_access: 'unverified' }))
  await page.route('**/api/v1/cameras', route => route.fulfill({ json: { items: cameras } }))
  await page.route('**/api/v1/cameras/*/commands/latest*', route => route.fulfill({ json: null }))
  await enterWorkspace(page)
  await page.getByRole('button', { name: 'Manage cameras', exact: true }).click()
  const first = page.getByRole('region', { name: 'Home · network 1', exact: true })
  const second = page.getByRole('region', { name: 'Home · network 2', exact: true })
  await expect(first.getByText('Armed · 2 cameras', { exact: true })).toBeVisible()
  await expect(first.getByRole('heading', { name: 'Synthetic driveway' })).toBeVisible()
  await expect(second.getByText('Unknown · 1 camera', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Network controls · Armed', exact: true }).click()
  const controls = page.getByRole('dialog', { name: 'Home', exact: true })
  await expect(first.getByRole('button', { name: 'Disarm network', exact: true })).toHaveCount(0)
  await expect(controls.getByRole('button', { name: 'Disarm network', exact: true })).toBeEnabled()
  await controls.getByRole('button', { name: 'Disarm network', exact: true }).click()
  await expect(controls.getByText('Disarm all cameras in Home?', { exact: false })).toBeVisible()
  await controls.getByRole('button', { name: 'Cancel change' }).click()
  await controls.getByRole('button', { name: 'Close network controls', exact: true }).click()
  await page.getByLabel('Camera', { exact: true }).selectOption(cameras[2].id)
  await page.getByRole('button', { name: 'Network controls · Unknown', exact: true }).click()
  await expect(controls.getByRole('button', { name: 'Disarm network', exact: true })).toBeDisabled()
  await controls.getByRole('button', { name: 'Close network controls', exact: true }).click()
  await page.getByLabel('Camera', { exact: true }).selectOption(cameras[0].id)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('network-controls.png'), fullPage: true })
  await page.getByLabel('Arrange cameras by').selectOption('local')
  await expect(page.getByRole('region', { name: 'Front yard', exact: true }).getByText('2 cameras', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ungrouped cameras', exact: true }).getByRole('heading', { name: 'Synthetic back yard' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('camera-groups.png'), fullPage: true })
})
