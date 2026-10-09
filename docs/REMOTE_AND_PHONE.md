# Browser installation and optional remote access

The production build has a manifest, original 192/512 icons and a service worker. **Settings → Notifications → Install Porchlight** offers the browser's install prompt when available. The prompt is captured at startup and opened only by your click. On Android Chrome, the alternative is **⋮ → Add to home screen → Install**, or Create shortcut if offered. Open the resulting Porchlight icon for app mode. Installation support depends on the browser and secure origin. Service workers require HTTPS, with a localhost development exception. See [MDN's service worker guide](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers).

The worker handles offline navigation with an honest server-unavailable page. It stores no footage, API responses, notes or account data in CacheStorage. The PC must be awake/reachable for ingestion, AI, viewing and alerts. Development on port 5174 deliberately does not register the production worker; test installation with the built interface on 8765 or the explicitly configured HTTPS origin.

Installed-app launchers can label initial or repeated launches cross-site, and service-worker fetches can present different navigation metadata. Porchlight allows GET requests to the two public HTML-shell paths `/` and `/index.html` without relying on a particular navigation mode/destination header combination. Host/proxy/HTTPS checks still apply; explicit frame/object/embed requests remain rejected and shell responses retain CSP frame denial and X-Frame-Options. This exception does not include API routes, media, service workers or state-changing requests; normal same-origin authentication and CSRF protection remain required after launch. Error responses use `Cache-Control: no-store` so rejected launch responses are not retained as cached documents.

Installation does not establish background phone push. The authenticated local inbox works; optional Web Push transport, encrypted subscription storage, permission/pairing and expiry handling are implemented. Optional encryption packages have passed native synthetic round-trip testing on the development PC after explicit approval; new installations still need their own approval and setup. Locked-phone/cellular tests remain separate owner gates. Follow [WEB_PUSH.md](WEB_PUSH.md) after the HTTPS origin is configured. Browser push uses the browser vendor's delivery service; private clip analysis stays on the PC. Phone delivery and phone access to a private clip are separate checks. Personal proxy, domain, certificate and VPN configuration stays outside this repository.

## First Android test without a tunnel

For a short owner-assisted test, Android's [ADB reverse port forwarding](https://developer.android.com/develop/ui/views/layout/webapps/access-local-server) can make the PC's existing loopback app available through a USB-connected phone. This is a proposed test route, not a measured Porchlight phone result. It requires Android platform-tools on the PC, a data-capable USB cable and explicit USB-debugging authorization on the phone. Platform-tools were not found on PATH during the 2026-10-08 review; no package was installed and no device was connected by this review.

After approving/installing platform-tools and authorizing this PC on the phone, use the Android tools in a local terminal:

```powershell
adb devices  # Confirm the intended phone locally; do not share device identifiers.
adb reverse tcp:8765 tcp:8765
# On the phone, open http://127.0.0.1:8765 in Chrome and sign in to Porchlight.
# When finished:
adb reverse --remove tcp:8765
```

If more than one device is attached, target the intended phone with ADB's `-s` option. Use the built interface on 8765; leave other applications' ports alone. This path keeps Porchlight bound to loopback and needs no LAN listener, firewall rule, DNS change or certificate trust. The browser sees a loopback origin, which is a [potentially trustworthy context](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts). Check actual install availability on the phone rather than assuming it from desktop viewport tests.

First verify sign-in, Activity filters and clip playback/audio, Live View unmute/fullscreen/Record/Snapshot/reconnect, page/modal sizing, Add to home screen and server-unavailable handling. Keep owner footage on the local device/browser and outside coding-tool screenshots. Unplugging or removing forwarding ends this access; it does not provide away-from-home or cellular access. Porchlight's push pairing deliberately requires its configured HTTPS origin, so USB testing does not establish push delivery or replace the later HTTPS tests.

For untethered home-Wi-Fi use before Cloudflare, configure a LAN-only HTTPS reverse proxy on this PC using the exact-origin boundary below. A private hostname must resolve to the PC from the phone, and its certificate must be trusted there. [Caddy's local HTTPS](https://caddyserver.com/docs/automatic-https) is a candidate, not an installed or tested dependency. Preparing that route requires explicit owner approval before installation, certificate trust or firewall changes; the current request only reviews it. A valid LAN hostname can use the existing `public_origin` setting without making the application internet-public. Do not expose Vite or Ollama, bypass browser certificate errors, or disable Host/Origin/CSRF checks for a phone preview.

## Explicit local reverse proxy mode

Default operation remains loopback-only. No tunnel, firewall rule, DNS record, software installation or certificate trust is created by Porchlight. Complete owner setup locally before configuring an external origin.

The backend can accept one exact HTTPS domain from a reverse proxy on the same PC. It still binds to `127.0.0.1:8765`; Ollama stays on loopback and must not be included in proxy routes. In a dedicated PowerShell session, after stopping the regular app:

```powershell
# Replace with your reviewed domain; the example is not a working tunnel.
$env:PORCHLIGHT_PUBLIC_ORIGIN = 'https://porchlight.example.com'
.\start.ps1
```

Route only that hostname to `http://127.0.0.1:8765`. The proxy must preserve the exact public Host and set `X-Forwarded-Proto: https` after terminating HTTPS. Cloudflare documents replacing this header with the visitor's protocol in its [HTTP headers reference](https://developers.cloudflare.com/fundamentals/reference/http-headers/#x-forwarded-proto). A mismatch or insecure public request is rejected. Wildcard hosts, arbitrary ports, remote network peers and forwarded client/host headers are not accepted. Uvicorn's general forwarded-header trust remains off. Public-host sessions use Secure/HttpOnly/SameSite=Strict cookies and HSTS. Owner bootstrap/claim endpoints remain local-only.

Use the built interface for remote access; the Vite dev server is not a remote service. Keep Porchlight authentication and CSRF checks enabled even if an additional tunnel access policy is configured. Do not configure shared caching of `/api/`, saved media or live routes; Porchlight marks these responses no-store. Local HTTP and public HTTPS have separate browser cookies and require separate sign-ins.

This mode has synthetic HTTP/proxy security evidence only. Actual Cloudflare Tunnel, external HTTPS, Android installation, Wi-Fi/cellular playback and background push are NOT RUN. Choose a stable private-access domain and review its access policy with the owner before exposing it. No setup has been applied to this PC.

To return to local-only operation, stop the app, remove `PORCHLIGHT_PUBLIC_ORIGIN` in that shell and restart. This removes acceptance of the external Host/Origin; it does not remove a separately managed tunnel or its configuration.
