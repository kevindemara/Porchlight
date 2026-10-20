import { useEffect, useId, useState } from 'react'
import { api, message, type Settings } from '../lib/api'

type ModuleChoice = Settings['blink_module_setup']
export const moduleChoices: { value: ModuleChoice; label: string; storage: string; detail: string }[] = [
  { value: 'unknown', label: 'Not sure yet', storage: 'Check the module name', detail: 'Find its model in the official Blink app or on its label. Porchlight checks available recording sources independently; you can continue without choosing.' },
  { value: 'core', label: 'Sync Module Core (basic module)', storage: 'No removable-storage recording', detail: 'Core does not save recordings to USB or microSD. Available cloud recordings depend on your account. If none are available, you can still import recordings manually; supported live viewing is checked separately.' },
  { value: 'original', label: 'Original Sync Module (1st generation)', storage: 'No removable-storage recording', detail: 'The original module does not provide Sync Module 2 local recording. A USB connector alone does not establish storage support. Check available cloud recordings for your camera/account, or import recordings manually.' },
  { value: 'sync_module_2', label: 'Sync Module 2', storage: 'USB drive', detail: 'Use a compatible Type-A USB drive, 1–256 GB, with at least 375 MB free. Add it and check Local Storage in the official Blink app, then test retrieval below.' },
  { value: 'xr', label: 'Sync Module XR', storage: 'microSD card', detail: 'Use a compatible microSD card, 1–256 GB, with at least 375 MB free. Add it and check Local Storage in the official Blink app, then test retrieval below.' },
  { value: 'xr_plus', label: 'Sync Module XR+', storage: 'microSD card', detail: 'Use a compatible microSD card up to 256 GB. The USB-C connection supplies power, not recording storage. Add the card and check Local Storage in the official Blink app, then test retrieval below.' },
  { value: 'none', label: 'No Sync Module', storage: 'No module storage', detail: 'Some cameras work without a module; others require one. Check your exact camera in the official Blink app. Available cloud clips, supported live viewing and manual imports remain separate options.' },
  { value: 'mixed', label: 'Multiple module types', storage: 'Check each system separately', detail: 'Use USB with Sync Module 2 and microSD with XR/XR+. Core and original modules do not provide removable-storage recording. Check the observed status of each module below; one working module does not verify every camera.' },
]

export default function BlinkHardwareSetup({ settings, onSaved }: { settings: Settings; onSaved: () => Promise<void> }) {
  const id = useId()
  const [camera, setCamera] = useState(settings.blink_camera_setup)
  const [module, setModule] = useState(settings.blink_module_setup)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  useEffect(() => { setCamera(settings.blink_camera_setup); setModule(settings.blink_module_setup) }, [settings.blink_camera_setup, settings.blink_module_setup])
  const choice = moduleChoices.find(item => item.value === module) ?? moduleChoices[0]
  const dirty = camera !== settings.blink_camera_setup || module !== settings.blink_module_setup
  async function save() {
    setBusy(true); setFeedback('')
    let saved = false
    try {
      const latest = await api<Settings>('/settings')
      await api('/settings', { method: 'PUT', body: JSON.stringify({ ...latest, blink_camera_setup: camera, blink_module_setup: module }) })
      saved = true
      await onSaved()
      setFeedback('Hardware choice saved. Recording access is still checked separately.')
    } catch (error) { setFeedback(`${saved ? 'Choice saved, but the status could not refresh: ' : ''}${message(error)}`) }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section beginner-setup">
    <h2>Your Blink hardware</h2>
    <p>Choose what you have so the guide explains the right recording options. Not sure? Leave the choices open and return later.</p>
    <div className="hardware-setup-fields">
      <div><label htmlFor={`${id}-cameras`}>Camera setup</label><select id={`${id}-cameras`} value={camera} disabled={busy} onChange={event => { setCamera(event.target.value as Settings['blink_camera_setup']); setFeedback('') }}>
        <option value="unknown">Not sure yet</option><option value="doorbell">Doorbell only</option><option value="cameras">Cameras only</option><option value="mixed">Doorbell and cameras</option>
      </select></div>
      <div><label htmlFor={`${id}-module`}>Sync Module type</label><select id={`${id}-module`} value={module} disabled={busy} onChange={event => { setModule(event.target.value as ModuleChoice); setFeedback('') }}>
        {moduleChoices.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></div>
    </div>
    <div className="notice" aria-live="polite"><strong>{choice.storage}</strong><p>{choice.detail}</p></div>
    <p className="helper">This is your setup choice, not detected hardware or proof of recording access. Saving it does not enable syncing, change camera settings, format a drive/card or change your subscription.</p>
    <div className="setup-choice-actions"><button className="secondary" disabled={busy || !dirty} onClick={() => { void save() }}>{busy ? 'Saving…' : 'Save hardware choice'}</button></div>
    <details className="archive-help"><summary>Local recording or cloud backup?</summary>
      <p>For cameras covered by a paid plan or free trial, compatible removable storage receives daily backups of cloud clips. Those backups do not prove direct subscription-free recording or automatic access from Porchlight. In a mixed system, check each camera’s plan coverage separately.</p>
      <p>For eligible cameras without an applicable plan or trial, compatible module storage can provide local recordings. Internet is still needed for Blink access. Configure storage in the Blink app, then verify a genuinely new clip imports and plays here. No-plan access stays unverified until tested.</p>
      <p className="helper">Legacy XT, XT2 and Indoor (1st generation) cameras do not support local storage, even with a newer module. Where available, their account-provided cloud storage is a different source.</p>
      <p><a href="https://support.blinkforhome.com/using-your-sync-module/sync-module-2-local-storage-operation" target="_blank" rel="noreferrer">Blink storage guidance</a> · <a href="https://blink.helpjuice.com/en_US/faq-sync-module-xr-plus/sync-module-xr-plus-faq" target="_blank" rel="noreferrer">Sync Module XR+ guidance</a></p>
    </details>
    {feedback && <p className="feedback" role="status">{feedback}</p>}
  </section>
}
