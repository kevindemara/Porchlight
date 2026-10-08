# Optional browser push

Porchlight implements browser pairing, DPAPI-protected VAPID keys and subscriptions, per-device delivery intents, expiry, retry limits, revocation and a service-worker notification handler. This is optional. The clip archive, local AI and inbox work without it.

The Python encryption dependency has **not been installed or tested on this PC yet**. Its public release metadata was reviewed on 2026-10-07: pywebpush 2.5.0 and py-vapid 1.9.4 are MPL-2.0, cryptography 50.0.2 is Apache-2.0 OR BSD-3-Clause, and http-ece 1.2.1 is MIT. They are dependency API reuse; no upstream implementation was copied. Exact candidates are in `requirements.push.lock`. Existing core packages are constrained by `requirements.lock`.

Review the preview:

```powershell
.\scripts\enable-webpush.ps1
```

After explicit approval, installation is local to the existing Porchlight virtual environment:

```powershell
.\scripts\enable-webpush.ps1 -Install
```

Restart Porchlight afterwards. This command does not create keys, expose the app, change firewall/certificate settings, pair a device or send an alert. Test the actual encryption adapter before claiming this dependency ready.

## Pairing flow

1. Complete local owner setup and configure the exact HTTPS origin described in [Remote and phone access](REMOTE_AND_PHONE.md). The proxy and phone reachability are owner-managed.
2. In the PC's local Notifications page, choose **Create local push keys**. The private key stays in `secrets/push.dpapi`, protected for the current Windows user. Keys are bound to the configured HTTPS origin.
3. On the phone, open that exact HTTPS address and sign in. In Notifications, give the browser a name and choose **Pair this browser**. Permission is requested only by this action.
4. Choose **Send push test**. Check delivery history, then independently check the phone with its screen locked and the browser closed.
5. Add **Also send to paired browsers** to an enabled rule. Generic lock-screen text is the default; descriptive text is a separate explicit rule setting.

Initial supported endpoints are Chrome's `fcm.googleapis.com/fcm/send/…` and Firefox's `updates.push.services.mozilla.com/wpush/v1/…` or `/wpush/v2/…`. Other endpoints fail closed. Edge/WNS, Safari and other browsers are unverified. HTTPS, public DNS resolution, certificate validation and no redirects are enforced; environment HTTP proxies are ignored. Endpoint URLs and encryption keys are never returned by status/history APIs or placed in portable backups.

Web Push uses browser-vendor infrastructure. Payloads are encrypted by the optional library; vendor routing/timing metadata remains external. The payload contains bounded text, an event ID, a replacement tag and expiry, with no image, clip, signed Blink URL or credentials. The worker opens only a same-origin authenticated route. It never downloads or caches media. [pywebpush API](https://github.com/web-push-libs/pywebpush#sending-data-using-webpush-one-call)

## Delivery evidence and limits

`transport_accepted` means the service accepted the request, **not** that the phone displayed it. Known retryable rejections use bounded delay and at most five attempts within the original expiry. Terminal endpoints are revoked. Interrupted or ambiguous sends become `delivery_unknown` and are not silently replayed. Reanalysis initiated manually does not produce alerts; historical backfill stays silent.

Pairing/revocation requires authenticated CSRF-protected API calls. Pairing must occur at the exact configured HTTPS origin; key creation is restricted to the local PC interface. The current first version permits up to eight active browsers. Revoke unused browsers from Notifications; browser permission may separately be removed through site settings.

Synthetic tests establish queue behavior and payload restrictions. Real encryption, provider acceptance, Android locked-screen display, Wi-Fi/cellular access, tap-to-open and private playback remain separate owner-assisted gates. No delivery to an actual browser-vendor endpoint has been attempted during unattended development.
