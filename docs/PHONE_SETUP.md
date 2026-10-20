# Phone setup without Cloudflare One/WARP

Use a stable HTTPS address in Chrome and install Porchlight from its menu. Choose a connection explicitly; the app does not publish itself or require a hosted account for local operation.

| Route | Phone requirement | Main boundary |
|---|---|---|
| [Direct home HTTPS](DIRECT_HTTPS.md) | Browser/home-screen app, no VPN | Public WAN address, approved TCP 443 forwarding, HTTPS proxy, DNS and renewal |
| [Cloudflare private backup](CLOUDFLARE_BACKUP.md) | Enrolled Cloudflare One/WARP client | Private route and owner access policy; same-hostname backup needs independent LAN resolution |
| Tailscale Funnel below | Browser/home-screen app, no VPN | Optional PC account/client; beta and non-configurable bandwidth limits |
| Published Cloudflare tunnel below | Browser/home-screen app, no VPN | Public hostname video restrictions apply; not an unrestricted camera-streaming recommendation |

Direct HTTPS and private backup can use the same exact origin so transport switching does not itself migrate the installed app or push pairing. They must still be tested independently. Neither a saved origin nor a healthy tunnel proves phone reachability. Keep real domains, WAN addresses, credentials, certificates and personal routing outside the repository.

## First choice to test: Tailscale Funnel, no purchased domain

Follow the [official Funnel guide](https://tailscale.com/docs/features/tailscale-funnel) and [CLI reference](https://tailscale.com/docs/reference/tailscale-cli/funnel). This publishes your Porchlight login to the Internet; finish local owner setup and choose a strong unique passphrase first. Review [Tailscale’s terms](https://tailscale.com/terms). The provider documents encrypted relaying with TLS termination on your PC; it is still an external connectivity service, not offline operation. Beta status, non-configurable bandwidth limits and plan eligibility must be reviewed, not advertised as unlimited video hosting.

1. Explicitly install [Tailscale for Windows](https://tailscale.com/download/windows) on the **PC** and sign in to your own account. Use a current client supporting the modern Funnel CLI (1.52 or later). The phone does **not** need the Tailscale app or membership for a public Funnel URL.
2. Run `tailscale serve status` and `tailscale funnel status`. If another project already uses HTTPS port 443/root on this device, **stop here and choose the separate Cloudflare tunnel route below or a dedicated device**. Never reset/replace another project’s Serve/Funnel configuration.
3. In PowerShell in the Porchlight checkout, get this PC’s generated hostname and preview the app’s origin:

   ```powershell
   $porchNode = tailscale status --json | ConvertFrom-Json
   $porchHostname = $porchNode.Self.DNSName.TrimEnd('.')
   $porchAddress = 'https://' + $porchHostname
   .\scripts\configure-phone.ps1 -Origin $porchAddress
   ```

   If the hostname is empty or sign-in is incomplete, finish Tailscale’s setup first. Keep the status data private. Apply only after reviewing:

   ```powershell
   .\scripts\configure-phone.ps1 -Origin $porchAddress -Apply
   .\stop.ps1
   .\start.ps1
   ```

   The helper saves the exact origin in your Windows user folder; it does not enable Funnel. Keep the app terminal running. Existing explicit origin environment overrides take precedence and must be reviewed if the address does not match.
4. In a second terminal, after verifying there is no conflicting route, explicitly publish only Porchlight:

   ```powershell
   tailscale funnel --https=443 http://127.0.0.1:8765
   ```

   Review and approve Tailscale’s browser prompts for MagicDNS/HTTPS/Funnel permissions and certificates. Keep the command in the foreground for the first test. Do not forward a directory, the Vite server, Ollama or arbitrary network services. No background-persistent Funnel is enabled by this guide.
5. Open the printed HTTPS URL in the phone’s Chrome **with Wi-Fi and phone VPN off**, sign in and play a recording. Continue with **Install on the actual phone** and **Add notifications** below. DNS propagation may delay initial availability; the official guide describes troubleshooting. Keep the hostname stable once the phone is paired.

Current upstream [proxy implementation](https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go) preserves the incoming Host and supplies forwarded HTTPS metadata, consistent with Porchlight’s exact-origin boundary. That code review is **not** a native Funnel test; this route has not been installed or exposed on the development PC. A different proxy/version must pass the same checks without relaxing authentication.

To stop this foreground Funnel, press Ctrl+C in its own terminal. If necessary, use the scoped matching command `tailscale funnel --https=443 off` for this route after checking it is still yours; never use a global reset or stop Tailscale for unrelated apps. Then use the origin-disable commands at the end of this guide and restart Porchlight. No Windows service registration or background Funnel persistence is performed here.

## Advanced alternative: published Cloudflare tunnel

This route publishes the Porchlight sign-in to the Internet. Complete owner setup locally first, use a strong unique passphrase and keep dependencies updated. Media stays authenticated; Ollama is never published. Cloudflare terminates HTTPS and relays traffic, so viewing footage uses that third-party infrastructure. The local archive and AI do not move to a cloud database or inference service.

Cloudflare's [video-delivery policy](https://developers.cloudflare.com/fundamentals/reference/policies-compliances/delivering-videos-with-cloudflare/) explicitly applies to public tunnel hostname routes and exempts private network routes. Review it before choosing this path; it is not an unrestricted free camera-streaming option. Do not switch private backups to a public tunnel automatically. The [direct HTTPS guide](DIRECT_HTTPS.md) and [private backup guide](CLOUDFLARE_BACKUP.md) describe the owner's selected primary/backup architecture without relying on a public media proxy.

The published route below is an implementation guide awaiting clean-machine and real cellular/locked-phone acceptance. The existing development owner’s private setup does not validate this separate route. No personal domain, account or connector token is in this repository.

## Before starting

- Confirm a fresh recording imports and plays on **http://127.0.0.1:8765**. Finish local owner creation before accepting an external address.
- Have a domain using Cloudflare DNS and permission to configure a hostname such as `porchlight.example.com`. The examples are placeholders, not a working domain.
- Review the [official locally managed tunnel guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/). We use browser login so connector credentials need not be pasted into command arguments, source files or chat.
- Download/install **cloudflared for Windows** using [Cloudflare’s official downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/). Make `cloudflared` available in this terminal, or use the full path to the downloaded executable. This optional installation is a local action you choose; Porchlight does not perform it automatically.

## 1. Authorize a dedicated PC connector

In PowerShell on the PC:

```powershell
cloudflared tunnel login
cloudflared tunnel create porchlight
```

The first command opens a browser to authorize your own domain. The second creates a **new dedicated tunnel**. If that name already belongs to another app, use a different new name; do not reuse or delete another project’s tunnel. Record the resulting tunnel UUID locally. Cloudflared stores its certificate/credential JSON under `%USERPROFILE%\.cloudflared`; keep those files private, outside the checkout and backups intended for publication.

## 2. Set the exact address and generate routing

Open Terminal in the Porchlight checkout. Replace the two placeholders with your hostname and the UUID printed by cloudflared:

```powershell
$porchAddress = 'https://porchlight.example.com'
$porchTunnel = [guid]'00000000-0000-0000-0000-000000000001' # Replace with your real tunnel UUID
.\scripts\configure-phone.ps1 -Origin $porchAddress -TunnelId $porchTunnel
```

That command is a **preview**. After reviewing it, explicitly apply:

```powershell
.\scripts\configure-phone.ps1 -Origin $porchAddress -TunnelId $porchTunnel -Apply
```

It saves only the hostname and routing configuration under `%LOCALAPPDATA%\PorchlightSetup`, outside Git. It does not install/start a connector, change DNS/firewall, trust certificates or stop other services. A different saved origin is refused until you explicitly disable it. Keep this default port **8765** for the generated route.

Stop Porchlight with `./stop.ps1` from its normal user/configured data profile, then run `./start.ps1` in its terminal. Start reads this optional private origin file; an explicit `PORCHLIGHT_PUBLIC_ORIGIN` environment setting takes precedence. Existing personal launchers may already supply that override—review them rather than replacing them.

## 3. Publish only this app and run the tunnel

In a **second PowerShell terminal**, using your real UUID and hostname:

```powershell
$porchTunnel = [guid]'00000000-0000-0000-0000-000000000001' # Replace
cloudflared tunnel route dns $porchTunnel porchlight.example.com
$porchRoute = Join-Path $env:LOCALAPPDATA 'PorchlightSetup\tunnel.yml'
cloudflared tunnel --config $porchRoute ingress validate
cloudflared tunnel --config $porchRoute run $porchTunnel
```

The DNS command changes only the selected hostname for your tunnel. The running connector forwards it to `http://127.0.0.1:8765`, sets its exact Host, and uses a final **404** catch-all. HTTPS must be enforced for visitors: choose the zone’s HTTPS redirect for this hostname through a scoped rule if other apps share the zone. Cloudflare’s visitor-protocol header must reach Porchlight as `X-Forwarded-Proto: https`. Plain HTTP cannot access the authenticated app. See the [routing guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/) and [protocol header reference](https://developers.cloudflare.com/fundamentals/reference/http-headers/#x-forwarded-proto).

Keep both app and connector terminals running for the first test. No Windows service or startup task is installed by these instructions. For later unattended operation, review a dedicated connector’s startup separately; never stop every `cloudflared` process or reuse another project’s connector.

Do not tunnel port **11434** (Ollama), **5174** (development UI), your archive directory or an arbitrary local network. Keep all Host/Origin/CSRF/authentication checks enabled. Do not create public/signed thumbnail routes or cache private API/media at the proxy. Porchlight marks private responses no-store; ensure no conflicting cache rule overrides that.

For this browser-only test, use Porchlight’s own login as the authentication gate. Adding Cloudflare Access can add another login barrier, but an expired Access session can prevent a background notification worker from fetching its thumbnail/receipt. Test that separately; do not bypass private media authentication to fix it.

## 4. Install on the actual phone

1. Open your **exact HTTPS address in Chrome** and sign in with your local Porchlight owner. A PC `localhost` or `10.0.0.x` address is not this outside-network path.
2. Turn Wi-Fi off and disconnect phone VPN/WARP for this test. Reload and play a recording on cellular. If that fails, the published route is not yet verified.
3. In Chrome, tap **⋮ → Add to home screen → Install** (or Create shortcut if offered). Open the new icon. Installation availability is a browser/device decision; the app’s install button appears only when Chrome offers the prompt.
4. Confirm navigation, playback/audio, fullscreen and sign-in after closing/reopening. The PC still must be awake/online; installation does not copy footage to the phone for offline use.

## 5. Add notifications, optionally

On the **PC**, preview `./scripts/enable-webpush.ps1`, then explicitly run with **-Install** if you want the optional pinned push packages. Restart Porchlight. In local Settings → Notifications choose **Create local push keys**. They are encrypted for this Windows user.

On the **phone’s HTTPS app**, go to Settings → Notifications, name the browser, click **Pair this browser** and allow the browser permission. Send a push test. Create/enable an activity rule with **Also send to paired browsers** and generic/unknown events included. AI need not be installed for generic activity alerts. Descriptions and saved face names need their separate local pipelines and the descriptive privacy option; thumbnails have their own opt-in setting.

Test locked-screen Wi-Fi and cellular, app closed, and tap-to-recording. A provider-accepted status is not evidence Android displayed anything. A worker receipt reports browser handling, not the user seeing the image. Private thumbnails require a reachable server and active phone login, with text-only fallback. See [push details](WEB_PUSH.md).

## Troubleshooting and undo

| Symptom | Check |
|---|---|
| No page / tunnel error | Both terminals still running; correct DNS/UUID; connector connected; PC awake |
| HOST_REJECTED / ORIGIN_REJECTED | Same exact hostname in saved origin and tunnel; restart; no conflicting environment override; no wildcard |
| HTTPS_REQUIRED | Open HTTPS; preserve forwarded HTTPS protocol; no conflicting proxy header rewrite |
| Browser works, home-screen launch fails | Fully close/reopen installed app; confirm exact installed hostname; check authentication, not a cached error |
| Pair button disabled | Actual configured HTTPS origin; push packages/keys ready; supported browser; permission allowed |
| Text arrives, no thumbnail/video | Sign in again, inspect worker receipt; verify server/cellular reachability; expand the Android notification |

To stop published access, stop **this connector’s terminal** with Ctrl+C. To remove acceptance of its origin:

```powershell
.\scripts\configure-phone.ps1 -Disable        # Preview
.\scripts\configure-phone.ps1 -Disable -Apply # Explicit removal
```

Stop/restart Porchlight. Remove any explicit origin environment override in its launching shell as well. Cloudflare users can remove only their dedicated tunnel/DNS record if no longer needed. Saved clips and unrelated projects remain intact. The helper’s private routing file is preserved for review; stopping the connector and removing its DNS/tunnel are separate actions.
