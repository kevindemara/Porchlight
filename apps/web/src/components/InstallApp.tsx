import { useState, useSyncExternalStore } from 'react'
import { Download, Smartphone } from 'lucide-react'
import { getInstallState, promptInstall, subscribeInstall } from '../lib/install'

export default function InstallApp() {
  const { available, installed } = useSyncExternalStore(subscribeInstall, getInstallState)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  async function install() {
    setBusy(true); setFeedback('')
    try {
      const outcome = await promptInstall()
      setFeedback(outcome === 'accepted' ? 'Installation requested. Look for the Porchlight icon on your home screen.' : outcome === 'dismissed' ? 'Installation cancelled. You can still use Porchlight in the browser.' : 'Use your browser menu to add Porchlight to your home screen.')
    } catch { setFeedback('The browser could not open installation. Try its Add to home screen menu instead.') }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section install-app">
    <div className="section-heading"><Smartphone size={22} /><div><h2>Install Porchlight</h2><p>Add the Porchlight icon to your phone’s home screen.</p></div></div>
    {installed ? <p role="status">Porchlight is installed. Open its home-screen icon for app mode.</p> : <>
      {available && <button className="primary" disabled={busy} onClick={() => { void install() }}><Download size={18} />{busy ? 'Opening installation…' : 'Install Porchlight'}</button>}
      <p className="helper">On Android, open your approved HTTPS address in Chrome. Tap ⋮ → Add to home screen → Install (or Create shortcut, if offered). Open the new Porchlight icon afterward.</p>
      {location.protocol !== 'https:' && <p className="helper">Use your HTTPS address on the phone, rather than this PC’s localhost address.</p>}
    </>}
    <p className="helper">The app uses the same account and archive. Your PC must be awake and reachable; private recordings are not cached offline. With private VPN access, keep your VPN connected to open the app.</p>
    <p className="helper">Home-screen installation and notification permission are separate. Pair this browser below to receive alerts, then send a push test and check the phone with its screen locked.</p>
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </section>
}
