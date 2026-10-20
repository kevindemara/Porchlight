# Direct home HTTPS

This optional route connects a phone directly to the home PC through an authenticated HTTPS proxy. The phone needs no VPN or tunnel app. Local desktop use still needs no domain or provider account. Recordings, the database and AI stay on the PC; the PC must remain awake and reachable. Blink still requires its own Internet service.

This guide is not an installer or authorization to open ports. Complete each explicit local approval yourself. Real cellular playback is a separate acceptance check, not a consequence of saving a hostname.

## 1. Check eligibility before changing anything

- Sign in to the router locally. Compare its **WAN IPv4** with an externally observed IPv4; keep both private. A matching public address is the usual candidate. A WAN address in RFC1918 space or `100.64.0.0/10` indicates upstream NAT that needs investigation. An outbound public address alone does not rule out CGNAT. See [RFC6598](https://www.rfc-editor.org/rfc/rfc6598).
- Confirm the ISP permits incoming TCP 443 and the router supports a scoped forward. Public IPv4 eligibility does not establish that the port works. IPv6-only access requires its own firewall and phone-network tests; do not publish an untested AAAA record.
- Reserve a stable **LAN address for this PC** in the router. Do not alter another device's lease, enable DMZ, enable router remote administration or turn off the firewall.
- Confirm the local owner exists, the password is strong/unique, current backups work and localhost playback is healthy. Keep the unofficial camera compatibility limitations visible.

If the connection cannot receive incoming traffic, use one of the [phone alternatives](PHONE_SETUP.md). A dynamic public IP needs a reviewed dynamic-DNS updater, or a manual DNS update whenever it changes; a fixed LAN reservation does not make the public IP static.

The LAN address identifies the PC (for example, `192.168.1.50`); TCP port `443` identifies its HTTPS listener. Any suitable unused address in the actual LAN subnet can be reserved for the PC. Changing the external port does not fix a forward that targets the wrong address.

## 2. Keep one exact hostname

Choose a stable address such as `https://porchlight.example.com`. Configure only this exact HTTPS origin through the existing preview-first helper:

```powershell
.\scripts\configure-phone.ps1 -Origin 'https://porchlight.example.com'
# Review, then explicitly save the origin (this does not open any port):
.\scripts\configure-phone.ps1 -Origin 'https://porchlight.example.com' -Apply
```

Restart the existing Porchlight instance using its normal data profile/launcher if its origin changed. Personal launchers may supply `PORCHLIGHT_PUBLIC_ORIGIN`, which takes precedence. Do not start a second instance or replace the owner's data root. The backend remains on **127.0.0.1:8765**; never publish 8765, the Vite server or Ollama 11434.

Using the same origin when changing transport avoids a hostname migration for the installed app and push subscription. It does not guarantee a phone has a valid login, worker or notification permission. Changing origin requires a new sign-in and push pairing, and potentially reinstalling its home-screen icon.

## 3. Prepare a dedicated HTTPS proxy

An existing approved Caddy installation can serve only this hostname and forward to Porchlight's loopback backend. Otherwise explicitly install Caddy from its [official source](https://caddyserver.com/docs/install); do not bundle an unreviewed binary. Keep the real Caddyfile, certificates, keys and process state outside Git in your Windows user folder.

Example Caddyfile; replace the hostname, private LAN address and storage path with your own writable local folder outside Git:

```caddyfile
{
    admin off
    persist_config off
    auto_https disable_redirects
    skip_install_trust
    storage file_system C:/PorchlightHttps/caddy-data
    servers {
        protocols h1 h2
        strict_sni_host on
    }
}

https://porchlight.example.com {
    bind 192.168.1.50
    tls {
        issuer acme https://acme-v02.api.letsencrypt.org/directory {
            disable_http_challenge
        }
    }
    reverse_proxy 127.0.0.1:8765 {
        flush_interval -1
    }
}
```

The example uses only Let's Encrypt with the TLS-ALPN challenge on TCP 443, disables the unused HTTP challenge and HTTP redirects, and does not advertise HTTP/3 or open UDP. It does not install a local root certificate. Restrict certificate storage to the owner and required system account; it contains account credentials and private keys and must persist across proxy restarts. Caddy preserves the request Host and supplies the HTTPS proxy metadata. Keep Porchlight's exact Host/Origin, loopback proxy, authentication, CSRF, Secure cookies and protected media checks enabled. Do not add shared media/API caching or a wildcard proxy route. See [proxy boundaries](REMOTE_AND_PHONE.md).

Validate with `caddy validate --config C:\path\to\Caddyfile --adapter caddyfile` before starting your dedicated proxy. Validation is not an external reachability test. Start only your own instance with `caddy run --config C:\path\to\Caddyfile --adapter caddyfile`; if port 443 already belongs to another project, stop and review the conflict rather than killing it. Use owned process records for background launch/stop, and approve service/task registration separately.

Keep firewall/hosts administration separate from runtime launch: start the app and proxy under the normal Windows user, not from the elevated configuration shell. An elevated proxy can prevent a normal desktop launcher from verifying or stopping it. Do not weaken process ownership checks to work around this.

The example lets Caddy obtain and renew public certificates. Its [automatic HTTPS](https://caddyserver.com/docs/automatic-https) must complete a challenge; the TLS-ALPN challenge needs incoming TCP 443. Port 80 need not be forwarded for that challenge. DNS-01 is another option with separate, narrowly scoped DNS credentials. Accept the selected certificate authority's agreement explicitly when required. Never bypass a certificate warning or install a self-signed certificate just to make this route appear verified.

If reusing manually supplied certificates, they are **not automatically renewed** merely because Caddy serves them. Record expiry and configure a verified renewal method before relying on unattended long-term access. Keep the existing valid certificate until a replacement is actually issued and served.

For a transition from manual certificates, back up the existing proxy configuration and certificate first. Validate the managed configuration, then restart only the owned proxy under its normal user. Confirm a publicly trusted handshake, the expected hostname, a valid expiry and that the certificate served matches the managed certificate in the dedicated storage. Restore the prior proxy configuration if issuance fails; do not bypass certificate validation or repeatedly force issuance. A successful initial issuance and configured automation are not evidence that a future renewal has already occurred. Caddy handles renewal while the proxy is running and checks its stored certificates when started again; the PC still needs working Internet/DNS and the approved incoming challenge route. No extra renewal task or Windows service is required for this mode. See [automatic HTTPS](https://caddyserver.com/docs/automatic-https) and [ACME issuer options](https://caddyserver.com/docs/caddyfile/directives/tls#issuers).

## 4. Review and enable the exact network changes

After reviewing the finished app/proxy configuration, explicitly approve these changes:

1. In DNS, set only the chosen hostname's **A record** to the current public WAN IPv4. For Cloudflare DNS, use **DNS only**, not the orange-cloud HTTP proxy. Remove/update a stale AAAA record only after reviewing it; do not change the whole zone or nameservers.
2. In the router, forward **TCP WAN 443 → this PC's reserved LAN address, TCP 443**. Do not forward other ports, enable UPnP broadly or use DMZ. Check that the chosen port is not already assigned to another project.
3. If Windows requires an inbound rule, create a named rule restricted to the dedicated Caddy executable, the PC's LAN address, TCP 443 and the applicable network profile. Do not create a Python/backend/Ollama rule or disable the firewall. Applying a rule requires an explicit local admin action.

On Rogers Xfinity gateways, forwarding may be managed only in the phone app: **WiFi → View WiFi equipment → Advanced Settings → Port Forwarding → Add Port Forward → intended PC → Manual Setup → TCP 443**. Inspect the final values before saving. The [official guide](https://www.rogers.com/support/internet/use-port-forwarding-with-rogers-xfinity) is authoritative if the UI changes. Other routers have different procedures.

After router or adapter changes, verify the PC's assigned LAN address again. It must agree with the proxy binding, scoped firewall rule, any local hostname mapping and router forward. A process can remain running while listening on an address the PC no longer has. Confirm a stable router DHCP reservation before relying on unattended access; do not change another project's network settings to repair Porchlight.

If the router rejects an address as reserved for another device, preserve that reservation. Match the intended device to the PC's active adapter privately; names alone can be stale or duplicated. Verify a reservation after reloading the router page: clicking Save or seeing a progress indicator is not proof it persisted. A stale displayed forwarding address also does not prove traffic is failing; test the actual cellular path before making further changes. Renewing a specific adapter's DHCP lease can briefly interrupt other applications' network connections and requires owner coordination. Do not factory-reset a shared router or replace existing reservations as a setup shortcut.

A manually assigned Windows IPv4 address also needs protection from DHCP allocation. If a reservation cannot be retained, an owner-reviewed alternative is to keep that static address outside the router's automatic DHCP pool. Inspect all listed clients, including offline entries, before changing the pool: devices outside a reduced range may receive different addresses when their leases renew, potentially affecting their forwards or other services. This is a shared-network change requiring a concrete review and approval, not an automatic setup shortcut. Preserve gateway, subnet, IPv6, lease duration and unrelated forwarding settings; reload the router page to verify the saved range and recheck the PC and HTTPS afterward. Do not call a static address exclusive merely because a ping received no response.

For a private tunnel backup on the **same hostname**, prepare its independent LAN resolution before changing public DNS; otherwise the connector may try the public WAN path instead of the private destination. Follow [Cloudflare backup](CLOUDFLARE_BACKUP.md). Do not overwrite or delete a working tunnel while setting up direct access.

## 5. Verify the actual phone path

Turn WiFi **and phone VPN/WARP off**. Open the exact HTTPS address in Chrome on cellular. Check:

- Trusted HTTPS, sign-in, close/reopen, navigation and the installed home-screen app.
- Protected recording/thumbnail playback, seek/Range requests and audio.
- A fresh bounded Live View session, stop/reconnect, Record and Snapshot on supported cameras.
- A locked-screen push test, description/thumbnail behavior and tap-to-recording.
- Backend/proxy restart, a later public-IP/DNS change, certificate renewal and return to home WiFi. Some routers lack NAT loopback; home WiFi may need LAN DNS resolution even when cellular works.

Do not send private footage, keys, cookies or raw router diagnostics to support/coding tools. Keep real results outside Git. Anonymous media must remain denied, and server/private-route outages must not be called successful monitoring. A native Android wrapper would still require this same reachable backend.

## Rollback

Remove only the dedicated router forward and dedicated firewall rule after confirming their ownership. Revert only the reviewed DNS record to its saved value. Keep the app/recordings and other projects intact. To use the preserved private backup, follow its explicit enable/test procedure; removing the public forward does not itself start a tunnel or connect the phone VPN. For fully local-only use, disable the optional origin with `scripts/configure-phone.ps1 -Disable -Apply`, remove any launcher's explicit origin override, and restart the same Porchlight instance.
