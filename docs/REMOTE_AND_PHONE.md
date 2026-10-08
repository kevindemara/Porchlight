# Browser installation and optional remote access

The production build has a manifest, original 192/512 icons and a service worker. Use the browser's Install app / Add to home screen menu when it is available. Installation support depends on the browser and secure origin. Service workers require HTTPS, with a localhost development exception. See [MDN's service worker guide](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers).

The worker handles offline navigation with an honest server-unavailable page. It stores no footage, API responses, notes or account data in CacheStorage. The PC must be awake/reachable for ingestion, AI, viewing and alerts. Development on port 5174 deliberately does not register the production worker; test installation with the built interface on 8765 or the explicitly configured HTTPS origin.

Installation does not establish background phone push. The authenticated local inbox works; optional Web Push transport, encrypted subscription storage, permission/pairing and expiry handling are implemented. Optional encryption packages await approval and native integration testing. Locked-phone/cellular tests remain NOT RUN. Follow [WEB_PUSH.md](WEB_PUSH.md) after the HTTPS origin is configured. Browser push would use the browser vendor's delivery service; private clip analysis stays on the PC. Phone delivery and phone access to a private clip are separate checks.

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
