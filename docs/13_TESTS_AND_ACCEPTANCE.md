# 13 · Test strategy and acceptance

## Evidence levels

1. **Static/package validation:** documents, schemas, example syntax and links. This package has only this level of validation.
2. **Automated application validation:** unit, integration and browser tests against controlled fixtures after Codex implements them.
3. **Real integration validation:** the owner's Windows runtime, Blink account, camera/module, local model and phone.

Passing one level is not passing the next. Keep test output private when it can contain device/account metadata. No real camera footage, credentials, tokens or screenshots in source control or external CI. CI uses synthetic fixtures and network mocks; explicit opt-in local tests use actual devices.

## Required automated suites

| Area | Required cases and expected behaviour |
|---|---|
| Authentication | First-run race, CSRF, bad Host/Origin, invalid password, session expiry/revocation, 2FA retry/expiry, redacted errors, vault failure; deny access rather than save plaintext |
| Blink contracts | Exact pinned API mapping, auth refresh, missing/unknown fields, duplicate camera names, rename, removed camera, unsupported controls, local manifests, prepared clip expiry |
| Discovery | Multiple pages; duplicate/reordered pages; overlapping cursors; several clips in one second; source-ID collision between accounts; backfill cancellation; deleted-upstream item |
| Downloads | 401/403/429/5xx; HTML instead of video; wrong/oversized content; redirect policy; interrupted transfer; corrupt file; expired signed URL; hash mismatch; atomic promotion/restart |
| Durable jobs | Crash before/after lease; lease expiry; two claimers; deduplication; retry exhaustion; restored DB; cancelled work; clock change; no parallel account login storms |
| AI contracts | Valid fixtures; malformed JSON; unknown keys; missing fields; extra-long text; invalid enum; invalid frame ID; prompt injection text in image; timeout/OOM; corrective retry limit |
| Semantic truthfulness | Single/duplicate still cannot establish motion; IR colour removed; colour lacks visible evidence; no package-placement claim from co-presence; no off-camera absolute negative |
| Rules | Entity-scoped category/colour/direction matching; unknown-field policy; overnight quiet hours; DST; cooldown; app snooze vs network arm state; backfill suppression |
| HTTP/media | Authentication on thumbnail/video/export; HEAD and Range; no path traversal; no arbitrary local-file read; no private-media service-worker cache; bounded import sizes |
| Notifications | Transactional outbox; duplicate worker/reanalysis; expired subscriptions; transient retry; permanent failure; stale alert expiry; redacted endpoints; no unauthenticated public topics |
| Search/digest | Parameterized filters; invalid time range; unknown camera; timezone date resolution; no generated SQL; counts from DB; invalid event IDs rejected; coverage gaps disclosed |
| Retention/restore | Ordinary expiry; pinned protection; reserve/budget; disk removed; race with active playback/download; crash recovery; source tombstone; restore without resend storm |
| UI | Empty/offline/partial data; keyboard focus; screen-reader labels; mobile playback; UTC/local dates; long names; stale snapshots; unverified capability messaging |

Use pytest for Python unit/integration tests and an appropriate current frontend test runner plus Playwright for browser journeys. Lock actual test versions. Test doubles must implement the same adapter contracts as production, not a parallel magic API.

## Contract example tests

Validate the supplied event, search and rule examples against their schemas. Also implement negative tests for every bound and unknown field. Schema validation must use a format checker where date/time formats matter.

Add semantic tests that intentionally pass JSON Schema but must still fail product validation: an IR vehicle labelled white; temporal action with one evidence frame; nonexistent frame ID; cross-entity colour matching; a push sentence claiming identity; a custom search end before start. The package validator does not claim to implement the application semantic validator.

## Real Blink acceptance gate

Complete a private copy of the hardware report. Record exact device/module types, available storage, actual entitlement state and how each was verified. Account age or the presence of a USB drive alone is insufficient proof.

For a subscription-free claim, obtain three new distinct clips plus one new clip after restarting the app, without an active paid/trial recording entitlement. Use owner-approved ordinary motion, not disarming or tampering with safety settings. Confirm automatic discovery, correct camera/time, complete playback, local persistence and no duplicate logical event. Confirm the official app still functions. Repeat separately for every recording provider claimed supported.

Cloud footage from a legacy entitlement can be a different legitimate no-plan path; document that entitlement rather than relabelling it USB storage. A paid/trial account can validate connectivity but cannot validate the no-plan claim. Where state is unavailable, record UNVERIFIED instead of guessing.

## Local vision evaluation

Create an owner-approved dataset outside the repo. A useful initial test target is at least 40 labelled clips spanning daylight vehicles, night/IR vehicles, pedestrians, animals, packages, weather/shadows, low contrast, occlusion and empty scenes; this is a proposed test size, not a statistical certification. Reserve a holdout subset before tuning prompts. Include single-frame and repeated-frame tests.

For each model/preset record exact model digest, quantization, runtime, frame policy, hardware, idle/busy PC conditions, time waiting, decode/inference/total latency, memory observations, schema failures, important-event misses, unsupported-claim rate and use of unknown. Label individual asserted facts against visible evidence; measure colour and temporal statements separately. Do not present schema-valid percentage as scene accuracy.

Hard deterministic safety gates: no invalid evidence reference accepted; no IR colour survives the semantic validator; no single-image temporal statement is rendered by the notification formatter; AI failure never deletes its source event. These are software test criteria, not a promise of zero visual hallucinations.

Before enabling selective suppression of unknown events, review the evaluation with the owner. Default conservative uncertainty handling should not silently discard activity the model could not interpret. Keep original clips available for checking descriptions.

## Phone acceptance

Record actual phone, OS, browser/application, origin, notification transport, network and permission state. Test foreground, closed page, locked screen, denied/revoked permission, PC asleep, PC resumed, phone Wi-Fi and phone cellular as relevant. A provider HTTP success is “accepted,” not “seen by the owner.” Measure clip-recorded → discovered → analysed → outbox accepted → observed display separately.

Verify tapping an alert opens the correct authenticated event and no private clip appears before login. Verify away-from-home access through the chosen private route; push itself is not that route. Where a platform cannot provide the intended behaviour, document it and disable the misleading promise.

## Reliability exercise

After critical tests pass, a proposed 24–48 hour owner-approved soak can expose routine idle/sleep/network issues; this is an implementation test duration, not work performed with this package. Do not increase polling frequency for the test. Review request counts, duplicates, event backlog, AI failures, data usage, temperature/resource impact and official-app coexistence.

Simulate failures locally: terminate worker during a transfer; restart Ollama during analysis; disconnect a test media directory; introduce a controlled 429 fixture; restore a backup into a fresh test profile. Never fill the owner's disk or deliberately rate-limit a real Blink account.

## Release acceptance record

Record command, environment, timestamp, exit code, test totals, failed/skipped tests and evidence path. “Not tested” is distinct from “failed” and from “not applicable.” A release must disclose any unverified no-plan, live-view or background-phone capability prominently in the UI and release notes.
