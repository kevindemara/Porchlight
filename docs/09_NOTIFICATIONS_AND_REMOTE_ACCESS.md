# 09 · Notifications and remote access

## Three distinct layers

**In-app updates:** SSE and a notification tray while the UI is connected. This is not background phone push.

**Background phone notifications:** an actual Web Push/VAPID or self-hosted ntfy transport. These have permissions, connectivity and OS constraints. Use Android as the initial delivery-test target, confirm the actual phone in setup, and test it locked/backgrounded.

**Remote viewing:** the phone must reach the authenticated Porchlight server to load private clips. Receiving a push notification does not automatically make a home-only server reachable.

## Default and recommended progression

Start with in-app notifications and explicit browser permission prompts. For an integrated PWA experience, implement opt-in Web Push with owned VAPID keys. It uses browser-vendor delivery infrastructure; that is an external notification relay, not cloud AI. Do not pretend it is fully self-hosted. No paid notification-service SDK is required by this design.

Web Push uses a service worker and a subscription endpoint/encryption material; protect those as sensitive data. A service worker can handle a push when the page is not open. [N1](15_SOURCES_AND_VERSIONING.md#n1) Mobile service-worker registration requires a trusted secure context. A plain `http://192.168.x.x` address is not equivalent to the PC's localhost development exception. [N2](15_SOURCES_AND_VERSIONING.md#n2)

Keep Web Push disabled until the user has a stable trusted HTTPS origin and has opted in. Do not weaken browser security or disable certificate verification to make the test pass.

## Web Push implementation

Create VAPID keys locally and store the private key in the vault. Register devices only from an authenticated same-origin session with CSRF protection. Encrypt stored endpoints/keys, redact from logs, and validate endpoint scheme/host against supported push providers. Reject loopback/private/link-local/metadata endpoints, unsafe redirects and arbitrary destinations to avoid SSRF.

Payload contains an event ID, notification tag, bounded safe title/body, and an authenticated app route. Default to generic text; descriptive text is an explicit privacy setting. Include enough text in the push payload to display without fetching the home server. Do not include signed Blink URLs, account data, raw frame content, or a public thumbnail URL. Disable external notification images by default.

The service worker displays the push notification and opens/focuses the app on click. It must not fetch or cache private video recordings in the background. The separately opted-in thumbnail setting permits one bounded authenticated JPEG fetch per alert, with text-only fallback; no public media endpoint or offline media cache is added. Vendor infrastructure can observe routing/timing metadata; properly encrypted payload delivery does not mean zero third-party metadata exposure.

Handle expired endpoints (for example terminal gone responses), revocation, permission changes and key rotation. Keep per-device test status. An HTTP success from the transport means `transport_accepted`, not proof that the user saw a lock-screen notification.

## Alternative: self-hosted ntfy for Android

Provide this as an optional transport, not a mandatory second app/runtime. Run an authenticated ntfy server on an owner-controlled host and pair the Android ntfy app. Restrict read/write access to the specific topic; unguessable topic names alone are not authorization. The owner chooses whether to run this optional component through an existing container/WSL/Linux environment.

ntfy documents that self-hosted Android subscriptions do not use its main-host Firebase route, and supports a persistent foreground-service delivery approach. Device background settings still need testing. [N3](15_SOURCES_AND_VERSIONING.md#n3) Keep the server reachable over trusted LAN/VPN/TLS; never make a public unauthenticated topic containing camera events. Follow its current auth configuration. [N4](15_SOURCES_AND_VERSIONING.md#n4)

This can avoid a browser-vendor push route for Android, but it is not automatically internet-reachable from cellular and its background service has a visible notification/battery tradeoff. Do not promise identical iPhone behaviour; iOS is outside the initial validation target.

## Rule evaluation and deduplication

Use `schemas/notification-rule.schema.json`. A rule selects cameras/categories, optional supported colour/direction, timezone-aware schedule, channels, cooldown and unknown-event policy. Backend code evaluates rules; models never execute notification actions themselves.

The implemented builder supports multiple choices within every camera/category/colour/direction group. Leaving a group empty means all its values; categories, colours and directions still must describe the same observed entity. “All” buttons clear that group's restriction only. A saved camera that has disappeared from inventory stays selected and is explicitly labelled unavailable until the owner changes it. Editing these choices does not enable the rule, AI or phone permission.

Each rule has an integer revision. Edits, enable/pause and deletion must supply the revision actually reviewed by that browser. Stale requests return a conflict without changing the rule. Background refresh keeps unsaved drafts separate and identifies newer or removed rules; the owner can explicitly reload/discard a draft or review the latest rule before confirming deletion. No conflict causes automatic retry, alerts or inference.

Unknown classification defaults to generic notification rather than silent suppression. Advanced AI-only filtering requires an explicit choice with a warning about false negatives. Retain the raw event regardless of notification outcome.

Use a stable idempotency key for event + rule + device + notification kind. Initial generic and later AI-updated messages share an appropriate replacement tag when supported. Never resend every historical event after a restart or reanalysis. Backfill older than the configured freshness window is silent by default.

Quiet hours affect notifications, not camera arming/recording. Define intervals that cross midnight and daylight-saving boundaries using IANA timezone data. An optional daily digest is scheduled once per local date and lists coverage gaps. Ordinary vehicle detection is not an emergency alert.

## Remote access boundary

First validate localhost, then trusted home-network HTTPS. For access away from home, prefer an owner-managed private VPN and authenticated HTTPS rather than publicly exposing the API. The setup wizard should explain that the owner must configure reachability; do not auto-modify the router, firewall, VPN or certificates.

A private VPN may require a reachable gateway or a separately chosen relay under the user's network conditions. Do not assume a free public tunnel, static IP, DNS name, or a free-tier service is available forever. No relay is required for local operation. The design must remain usable without signing up for a hosted service.

The app API can be reachable through an explicitly trusted reverse proxy, but Ollama stays on loopback. Rate-limit login and private media access. Only trust proxy headers from configured proxies; do not trust arbitrary X-Forwarded headers.

## Phone validation matrix

Test foreground, background, locked screen, battery saver, Wi-Fi, cellular with the configured remote path, server restart, permission revoked, endpoint expired and camera/AI outage. Record separately: provider accepted, phone displayed, tap opened app, and authenticated video loaded. Keep failed attempts visible; do not label all four passed from one result.

If the PC is off/asleep, it cannot create new Porchlight analyses or send newly generated alerts. The original Blink app may still behave independently. Keep the official app during validation and clearly disclose the local server dependency.
