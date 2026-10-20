# Optional Cloudflare private tunnel backup

Keep this as an opt-in alternative to [direct HTTPS](DIRECT_HTTPS.md), or use it as the primary private route. It requires Cloudflare One/WARP on the phone. It cannot provide independence from Cloudflare outages, and it does not provide offline Blink access. A tunnel shown Healthy does not prove end-to-end phone connectivity.

The repository contains generic instructions only. Store your account/domain choices, tunnel credentials, device enrollment, Caddyfile and launcher/process records outside Git. Core Porchlight needs no Cloudflare account. Never paste credentials into chat, command-line arguments, source or diagnostics.

## New installations

1. Configure and test local Porchlight first. Create a private Cloudflare Tunnel using the [official private-hostname guide](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/private-net/cloudflared/connect-private-hostname/). Use a **dedicated** tunnel and current official connector; review software installation and any terms locally. Do not replace an unrelated project's tunnel.
2. Add only your Porchlight hostname as a private hostname route. Enroll the intended phone in your organization and configure owner-only access. The official guide notes that enrolled devices may otherwise have broad default private access; review identity/network policies instead of assuming the tunnel name is access control.
3. Make the connector host resolve that hostname to the HTTPS proxy's **private LAN address**. Cloudflared uses its host's system resolver by default. Confirm this independently of what public DNS returns. A specific, owner-approved local hosts entry is one option; local split DNS is another. Do not disable DNS or browser security protections.
4. Install/use your HTTPS proxy for that exact hostname, forwarding only to 127.0.0.1:8765 with trusted HTTPS metadata. Configure Porchlight's exact origin using the preview-first helper in [phone setup](PHONE_SETUP.md). Keep authentication and protected media enabled, including over the private tunnel.
5. Connect the phone's Cloudflare One/WARP client and test browser, installed app, playback, bounded live sessions and push thumbnails on WiFi and cellular. Inspect the real connection error if it fails; consult [Cloudflare status](https://www.cloudflarestatus.com/) before changing a healthy app.

## Same-hostname direct access plus backup

One hostname can serve both transports without adding a second app origin:

| Connection | Resolution and path |
|---|---|
| Phone VPN off | Public DNS A → home WAN → TCP 443 forward → HTTPS proxy |
| Phone VPN connected | Gateway private-hostname route → dedicated connector → LAN HTTPS proxy |
| Connector host | System/local DNS → LAN proxy address, independently of public DNS |

The third row is essential. After replacing a private-address public DNS record with a WAN-address record, the backup must not depend on router NAT loopback. If using Windows hosts, add **only the one reviewed hostname/address mapping**, back up the existing file and check for conflicts; do not replace the file or change other applications' entries. Keep it synchronized with the PC's reserved LAN address. Confirm actual cloudflared resolution and phone backup playback; a generic hosts-file example is not hardware verification.

Public DNS and the direct route can stay configured while the backup is off. Turning the connector off does **not** close direct public access. Removing the router forward does **not** automatically connect WARP. A backup that depends on the same PC will not help if that PC is asleep or offline.

## Enable and disable deliberately

Keep connector credentials and its private hostname route when switching to direct access. To enable backup, start only the dedicated Porchlight connector using your existing credential file/approved launcher, wait for readiness, connect the phone's enrolled WARP client, then open the same hostname. Do not start another Porchlight account actor, publish the raw backend, or register a Windows service silently.

To disable backup, disconnect WARP on the phone and stop only the connector you started. A foreground connector can be stopped with Ctrl+C in its own terminal. Background launchers must verify PID, executable, start time and command identity before stopping the recorded process. Never kill all cloudflared processes or use a global tunnel reset. Preserve other projects and the shared Ollama service.

Using a different backup hostname is also possible, but the current app accepts **one exact external origin**. Switching origin requires an explicit configuration change/restart and phone sign-in/push pairing for the new origin. Do not add wildcard origins to hide this distinction.

## Public Cloudflare tunnels are a different option

A published HTTP tunnel avoids a phone VPN, but is not the private backup described here. Cloudflare's [video-delivery policy](https://developers.cloudflare.com/fundamentals/reference/policies-compliances/delivering-videos-with-cloudflare/) explicitly applies to public hostname routes and exempts private network routes. Do not advertise a free published tunnel as an unrestricted camera-streaming route. Retain any published-route instructions only with that provider boundary, and never automatically switch to public exposure when the private route fails.
