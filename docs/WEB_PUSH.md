# Optional browser push

Porchlight implements browser pairing, DPAPI-protected VAPID keys and subscriptions, per-device delivery intents, expiry, retry limits, revocation and a service-worker notification handler. This is optional. The clip archive, local AI and inbox work without it.

Acceptance update, 2026-10-20: the owner reports passing Android locked-screen/closed-app alerts on Wi-Fi and cellular, thumbnails and tapping through to the matching recording. Earlier pending notes below describe the development stages; the owner's report supersedes those listed delivery checks for the tested setup. Other browsers/devices and unreported expiry/revocation cases remain unverified.

The four pinned Python encryption packages were installed with owner approval and tested on the development PC on 2026-10-08. A native encrypted-payload round trip passed without sending to an external provider; actual phone delivery remains a separate gate. Their public release metadata was reviewed on 2026-10-07: pywebpush 2.5.0 and py-vapid 1.9.4 are MPL-2.0, cryptography 50.0.2 is Apache-2.0 OR BSD-3-Clause, and http-ece 1.2.1 is MIT. They are dependency API reuse; no upstream implementation was copied. Exact pins are in `requirements.push.lock`. Existing core packages are constrained by `requirements.lock`. A new installation still requires an explicit owner action.

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
2. In **Settings → Notifications** at the PC's local address, choose **Create local push keys**. The private key stays in `secrets/push.dpapi`, protected for the current Windows user. Keys are bound to the configured HTTPS origin.
3. On the phone, open that exact HTTPS address and sign in. Optionally install it using **Install Porchlight** in Settings → Notifications or Chrome's **⋮ → Add to home screen**, then open the home-screen icon. In the same Settings section, give the browser a name and choose **Pair this browser**. Permission is requested only by this action. Installation alone does not pair the browser or enable alerts.
4. Choose **Send push test**. Check delivery history, then independently check the phone with its screen locked and the browser closed.
5. Add **Also send to paired browsers** to an enabled rule. To include descriptions, also select **Include validated AI description in alerts** and save the rule. Generic lock-screen text is the default for new installations.

A fresh recording produces an initial generic alert. When automatic local analysis finishes with a known matching observation, a descriptive rule updates that alert with the saved AI description, using the same recording ID and replacement tag. The update does not request another sound or vibration. Descriptive alerts use the same conservative saved-name formatting as Activity. When an automatic face scan finishes after analysis, one bounded, silent replacement can add the saved name within the original freshness window. An uncertain or multi-person match stays generic; manual rescans and historical work do not create alerts. A face replacement is skipped if that notification was dismissed. Failed or uncertain analysis retains generic text; historical retrieval and manual reanalysis remain silent. Alerts expire at the rule's maximum clip age, so an analysis finishing after that window does not send a late update. Descriptions may appear on the lock screen according to Android's notification settings.

Tapping either version opens that specific recording in Activity, focusing an existing Porchlight window or opening one. Authentication and access to the PC are still required; if signed out, sign in before the recording opens. Test alerts open the notification inbox because they have no recording attached.

The installed app requests a status-bar color matching the current page background. It follows Settings → Appearance, including system light/dark changes. Android/browser chrome remains platform-controlled; fully close and reopen the installed app after an appearance update to load the current page.

Initial supported endpoints are Chrome's `fcm.googleapis.com/fcm/send/…` and Firefox's `updates.push.services.mozilla.com/wpush/v1/…` or `/wpush/v2/…`. Other endpoints fail closed. Edge/WNS, Safari and other browsers are unverified. HTTPS, public DNS resolution, certificate validation and no redirects are enforced; environment HTTP proxies are ignored. Endpoint URLs and encryption keys are never returned by status/history APIs or placed in portable backups.

Web Push uses browser-vendor infrastructure. Payloads are encrypted by the optional library; vendor routing/timing metadata remains external. The payload contains bounded text, an event ID, a replacement tag and expiry, with no image, clip, signed Blink URL or credentials. The worker opens only a same-origin authenticated route. With the optional thumbnail setting, it fetches only the same-origin authenticated notification-thumbnail route, with existing cookies, no redirects, a three-second deadline and a 512-KiB limit. It displays the JPEG from memory and never writes private content to an offline cache. Failed authentication, timeout, unavailable private access or missing media leaves a text-only alert. No image bytes or media access token travels through the push payload. [pywebpush API](https://github.com/web-push-libs/pywebpush#sending-data-using-webpush-one-call)

## Delivery evidence and limits

`transport_accepted` means the service accepted the request, **not** that the phone displayed it. Known retryable rejections use bounded delay and at most five attempts within the original expiry. Terminal endpoints are revoked. Interrupted or ambiguous sends become `delivery_unknown` and are not silently replayed. Reanalysis initiated manually does not produce alerts; historical backfill stays silent.

Pairing/revocation requires authenticated CSRF-protected API calls. Pairing must occur at the exact configured HTTPS origin; key creation is restricted to the local PC interface. The current first version permits up to eight active browsers. Revoke unused browsers from Notifications; browser permission may separately be removed through site settings.

Synthetic tests establish queue behavior and payload restrictions; the native adapter has also encrypted and decrypted a synthetic payload through the pinned libraries without network delivery. Provider acceptance, Android locked-screen display, Wi-Fi/cellular access, tap-to-open and private playback remain separate owner-assisted gates. No delivery to an actual browser-vendor endpoint has been attempted during unattended development.

## What the phone shows

The service worker requests a normal system notification titled **Porchlight activity**, with the Porchlight icon and default body **New camera activity. Open Porchlight to review the recording.** An enabled rule can explicitly include the validated AI description instead. No thumbnail or recording is sent in the push. **Include a recording thumbnail in phone alerts** is a separate rule setting, off by default; enabling it permits the phone to retrieve and display a private still, including on the lock screen. Notification images remain subject to Android/browser display and retention behavior. Android controls lock-screen visibility, notification sound and interruption behavior through the app/browser's notification settings.

Tapping an activity notification opens that recording in Activity; a push test opens the inbox. A new message does not require an open Porchlight tab, but browser/OS permission, delivery connectivity and background restrictions still apply. The PC must be awake to generate new alerts; the configured private-access connection must be available to load the app and play its recordings.

## Preview and replacement acceptance · 2026-10-08

Synthetic native/browser tests cover authenticated JPEG delivery, signed-out fallback, no offline caches, same-tag/same-topic name updates, duplicate suppression and dismissed-alert handling. Actual Android thumbnail layout and silent replacement remain owner-assisted checks. Generic notifications remain possible without a reachable PC; previews require a valid signed-in session and the configured private connection.


### Verifying description and preview updates

On the paired HTTPS phone, use Settings → Notifications → Refresh phone notifications. It confirms worker version `previews-v2` without changing browser permission or pairing. The app also checks for worker updates on launch and foreground return. Generate a fresh clip; previously expired alerts are not replayed.

Delivery history separates provider acceptance from an authenticated phone-worker receipt. The bounded receipt stores only worker version, description-present boolean, submission outcome and preview status. `submitted` means the browser notification API accepted the call; it does not prove Android rendered the image or the owner saw it. Missing receipts may mean an old worker, delayed delivery, no private reachability or an expired login. Preview `unauthorized`, `timeout`, `unreachable`, `invalid` and `display rejected` distinguish safe fallbacks. Receipts use the existing owner session/CSRF and are retained for at most the latest 30 deliveries; portable backups omit them. No additional subscription secret, image or description is reported.

Protected preview fetches have a ten-second deadline and the existing 512-KiB cap. Text is submitted immediately before fetching a preview; a successful preview quietly enriches the same tagged item if it remains present. A rejected image leaves the already-submitted description intact. Push handling is serialized and compares issued timestamps to avoid an older generic alert replacing a newer description. No offline media caches or public image URLs are added. Web Push requests high urgency for these freshness-limited activity alerts; browser/Android delivery timing remains platform-controlled ([RFC 8030 §5.3](https://www.rfc-editor.org/rfc/rfc8030.html#section-5.3)).

Archive, automatic analysis and face completion wake notification dispatch; fanout wakes push dispatch. Durable queues retain two-second fallback checks for restart/retry recovery. Face detection already runs independently alongside Qwen. Balanced analysis samples up to six frames; Light samples up to three smaller frames and may trade away action detail. Neither mode guarantees an alert latency or recognition accuracy.
