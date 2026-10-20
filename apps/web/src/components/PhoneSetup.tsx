import { useEffect, useState } from 'react'
import { api, message, type PushStatus } from '../lib/api'
import InstallApp from './InstallApp'

export default function PhoneSetup() {
  const [status, setStatus] = useState<PushStatus | null>(null)
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    api<PushStatus>('/push', { signal: controller.signal }).then(setStatus).catch(error => { if (!controller.signal.aborted) setError(message(error)) })
    return () => controller.abort()
  }, [])
  async function refresh() {
    setChecking(true); setError('')
    try { setStatus(await api<PushStatus>('/push')) }
    catch (error) { setError(message(error)) }
    finally { setChecking(false) }
  }
  return <section className="panel settings-section beginner-setup">
    <h2>Phone access and permissions</h2><p>Use a stable HTTPS address to open Porchlight at home or away, then add it to your home screen. Your PC runs the archive and must stay awake and online.</p>
    <div className="notice"><strong>{status?.public_origin ? 'HTTPS address configured' : 'Set up an HTTPS address first'}</strong>
      {status?.public_origin && <><a className="guide-path" href={status.public_origin} target="_blank" rel="noreferrer">{status.public_origin}</a><p className="helper">Configured does not mean reachable from cellular. Test the address on the actual phone.</p></>}
      <button className="secondary" disabled={checking} onClick={() => { void refresh() }}>{checking ? 'Checking…' : 'Recheck phone setup'}</button>
    </div>
    <details className="archive-help"><summary>Direct home HTTPS — no phone VPN</summary>
      <p>Connect your phone directly to your home PC using a stable HTTPS address. This needs a reachable public address, a reviewed router forward to an HTTPS proxy, and certificate renewal. Your sign-in becomes internet-reachable; use a strong unique password. Your recordings and AI stay on the PC.</p>
      <p className="helper">Check the router’s WAN address first; a public outbound address alone does not rule out carrier-grade NAT. This guide does not change your router, DNS or firewall. Verify playback on cellular with phone VPN and WiFi off.</p>
      <a className="secondary button-link" href="/api/v1/setup/guides/direct-https">Download direct HTTPS guide</a>
    </details>
    <details className="archive-help"><summary>Cloudflare private tunnel — optional backup</summary>
      <p>Keep a dedicated private tunnel as an alternative connection. This route needs an enrolled Cloudflare One/WARP client on the phone and remains dependent on Cloudflare. It can use the same HTTPS address when the connector has independent LAN resolution.</p>
      <p className="helper">Enable the connector and phone VPN explicitly when needed. Keeping backup credentials does not enable it, verify it, or close a configured direct public route.</p>
      <a className="secondary button-link" href="/api/v1/setup/guides/cloudflare-backup">Download private tunnel backup guide</a>
    </details>
    <details className="archive-help" open={status !== null && !status.public_origin}><summary>Connect without a phone VPN</summary>
      <p><strong>No domain yet?</strong> The guide starts with Tailscale Funnel: install its client on the PC, sign in, and use its HTTPS address in the phone’s browser. The phone needs no Tailscale app or VPN. Funnel is still beta and has bandwidth limits; test clip playback and locked-screen alerts before relying on it.</p>
      <p>A published Cloudflare HTTPS tunnel can open without Cloudflare One/WARP, but Cloudflare applies video-delivery restrictions to public hostname routes. It is not the private backup above and is not an unrestricted camera-streaming recommendation.</p>
      <ol className="setup-instructions"><li>On the PC, complete local owner setup and confirm clip playback first.</li><li>Follow the downloadable phone guide to install the optional PC connector, sign in through its browser flow, and publish a route for this app only.</li><li>Preview and apply your exact HTTPS address using <code>scripts/configure-phone.ps1</code>, then restart Porchlight. Configuration and connector credentials stay in your Windows user folder.</li><li>Open that address in Chrome on the phone. Turn off Wi-Fi and any VPN temporarily to verify cellular access before calling setup complete.</li></ol>
      <p className="helper">Cloudflare’s route needs a domain/account and a PC connector. Review each provider’s current terms and limits; unlimited free camera streaming is not promised. Existing owner-managed HTTPS hosting is another option. Local desktop use needs neither.</p>
      <a className="secondary button-link" href="/api/v1/setup/guides/phone">Download phone connection guide</a>
    </details>
    <InstallApp />
    <p>On the phone: sign in → Settings → Notifications → pair this browser → allow notifications → send a push test. Then lock the screen, test on Wi-Fi and cellular, and tap an activity alert to open its recording.</p>
    {status && !status.dependency_ready && <p className="helper">Optional push packages are not ready. On the PC, review and run <code>.\scripts\enable-webpush.ps1 -Install</code>, then restart Porchlight. Phone viewing works without push.</p>}
    <p className="helper">AI is not required for generic activity alerts. Use a rule that includes unknown events; person/action rules need analysis. Private notification thumbnails need a reachable server and an active phone login.</p>
    {error && <p className="feedback" role="status">{error}</p>}
  </section>
}
