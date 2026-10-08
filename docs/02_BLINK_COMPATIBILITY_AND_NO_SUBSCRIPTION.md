# 02 · Blink compatibility and the no-subscription gate

## The three separate questions

1. Can the camera create motion recordings under the owner's present hardware and entitlement?
2. Can the selected unofficial adapter discover and retrieve those recordings reliably?
3. Can the local application analyze them and notify the phone promptly enough for the owner?

Passing one is not proof of the others. This is the highest-risk integration work and must precede a large amount of UI polish.

## Hardware/entitlement decision tree

Blink's official documentation describes USB Local Storage on Sync Module 2, microSD Local Storage on XR, no Local Storage on Core, and distinct legacy-camera storage arrangements. It also distinguishes daily Clip Backup during a subscription/trial from Local Storage. Confirm the particular camera's compatibility using current device documentation. [B1](15_SOURCES_AND_VERSIONING.md#b1)

**A — Supported camera + Sync Module 2/XR + working removable storage + no active plan/trial.** Candidate for no-subscription operation. Verify a genuinely new motion clip appears in the official app's local list, then independently verify the provider can retrieve it.

**B — Core or a camera without an eligible recording source.** Do not claim app code solves missing storage. Discover whether an eligible existing module/account entitlement is available; otherwise report the hardware/storage blocker. Manual imports remain usable. Do not recommend buying a particular module until compatibility is established, and never buy anything automatically.

**C — Legacy camera/account storage.** Test the account's actual free cloud entitlement. Do not apply modern local-storage assumptions or promise indefinite grandfathered benefits. A runtime capability report should say what was observed, not classify all older accounts from memory.

**D — Active paid subscription or free trial.** The application may ingest legitimately available clips during development, but label no-plan compatibility UNVERIFIED. The owner decides whether/when to perform a separate no-plan test. A USB backup generated from cloud recordings during a trial does not demonstrate no-plan motion storage.

**E — Official local clips work but adapter access fails.** Classify as `local_recording_available / retrieval_unverified_or_failed`. Retain a manual-import fallback. Do not silently switch to a paid route, repeatedly hammer an endpoint, or call the release subscription-free ready.

## Local does not mean cloud-independent

The reviewed `blinkpy` documentation describes local-manifest and clip-request operations mediated through Blink's service. Its description of a local clip transfer includes upload/download through the service; treat that as an unofficial implementation observation, not a permanent vendor contract. [R1](15_SOURCES_AND_VERSIONING.md#r1)

Therefore the product promise is **local AI + local retained archive**, not “no footage ever passes through Blink” or “works without internet.” If the internet goes down, already archived files can still be viewed/analyzed locally. New Blink retrieval may stop.

## Required M1 proof, performed locally by the owner

Create a report from [16](16_HARDWARE_VALIDATION_REPORT_TEMPLATE.md). Record non-sensitive model/module identifiers, relevant firmware/library versions, storage mode, entitlement evidence, and UTC timestamps. Use pseudonymous camera labels in anything committed or shared.

Run these tests without changing account security or disabling the official system:

1. Authenticate through the local setup flow, complete a genuine 2FA challenge if required, and list networks/cameras.
2. Confirm the recording mode and entitlement independently. When the API does not expose trustworthy entitlement, accept explicit owner confirmation in setup and mark its provenance; do not infer “no subscription” from an empty cloud clip list.
3. Have the owner create a harmless motion event in front of a selected camera. Do not remotely trigger lights, sirens, disarming, or undocumented capture as part of discovery.
4. Identify the new clip using its event time/camera, retrieve it, check file integrity, and play it. A stale latest thumbnail is not a passing recording test.
5. Create several separated events within an observation window; confirm all discoverable clips, not only the newest, are imported once.
6. Restart Porchlight; retrieve a subsequent new event, keep prior events, and avoid duplicate notifications.
7. Simulate network loss and module-unavailable responses in fixtures. Perform real offline tests only when the owner chooses them.
8. Record event-capture time, discovery time, download completion, AI completion, and actual phone-display time. Event duration and upstream availability contribute to delay.

### Passing evidence

At least three independently created motion recordings after the no-plan state is established; one successful post-restart recording; matching timestamps/camera; playable downloaded files; no reliance on cached/trial-only clips; no repeated uncontrolled retries. Expand this with a normal-use soak before replacing daily reliance on another app.

This small compatibility test establishes a path, not a reliability guarantee. The release soak is defined in [13](13_TESTS_AND_ACCEPTANCE.md).

## Unsupported or ambiguous states

Persist reasons, not just booleans:

- `no_recording_source`: no current eligible source has been demonstrated.
- `entitlement_unknown`: cannot establish whether a plan/trial is enabling recording.
- `local_storage_not_ready`: removable media missing/full/unavailable or status unknown.
- `local_manifest_unavailable`: source exists but its manifest cannot be obtained.
- `clip_transfer_failed`: listed clip cannot be retrieved; allow bounded retry.
- `source_media_expired`: clip disappeared before retrieval; keep a metadata event with this explanation.
- `auth_action_required`: request a local sign-in/2FA action without login loops.
- `rate_limited`: honour provider retry information and back off.

Source failure must be visible in camera cards, integration diagnostics, and the event timeline. Do not replace an unavailable source with fabricated sample activity.

## Hardware writes and read-back

Do not probe capabilities by toggling arm/disarm or motion detection. Read advertised/state metadata and identify untested actions. When the owner explicitly uses a control, persist an intent record, send the supported command, then reconcile observed state. A command accepted upstream is not yet a confirmed new state.

Snapshot refresh is an on-demand operation with a warning when it wakes battery hardware. Device setup, Wi-Fi onboarding, firmware updates, account management, and unsupported settings stay in the official app. Keep a clear “Use Blink app for this setting” explanation rather than inventing deep-link schemes.

## No-subscription language in the finished UI

Use “No-plan recording verified on this setup” with a validation date and source mode only after the gate passes. Do not put a global guaranteed “No subscription needed for any Blink” claim in the onboarding screen. The only unconditional no-fee claim is about our own application design; hardware, electricity, internet, storage, and the chosen coding tool are separate costs.
