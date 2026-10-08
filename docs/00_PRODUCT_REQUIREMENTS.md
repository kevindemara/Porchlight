# 00 · Product requirements

## Product thesis

Make a personally hosted camera application that explains recorded events in useful language, keeps the owner in control of data, and makes everyday review faster. Recreate the useful *workflows* of a consumer camera app, not Blink's branding or a promise of identical hardware access.

Primary user: eventide team, Canada, Windows desktop with existing Ollama; Android is the first phone target. One household and one Blink account initially, with multiple networks/modules/cameras inside that account. Persist UTC timestamps and display `America/Toronto` by default, including daylight-saving transitions. Do not equate an account's region with its timezone.

## Product outcomes

**Understand:** Given a newly available clip, view a brief supported description, key frames, timestamp, camera, and original recording. An illustrative target is “A white car moves left to right.” The system must avoid unsupported additions such as exact make/model, intention, or a claim about what happened outside the captured interval.

**Find:** Filter by camera, time, category, colour when visible, favourites, notes, and analysis state. Search “cars yesterday afternoon” using a bounded, typed query; always show the exact filters applied. Natural-language search covers stored observations, not unrecorded reality.

**Act:** Review the clip, favourite it, download an original or clearly labelled derivative, snooze Porchlight notifications, and perform supported manual camera/network controls. The AI itself cannot change the security system.

**Trust:** Know when the system last contacted Blink, when a camera's snapshot was taken, whether clips are stale or missing, whether AI is queued, and whether an alert was accepted by its delivery transport. “Nothing found” must not imply nothing happened.

**Own:** Run without required paid services. Choose retention based on local space, export data, back up locally, and stop using the app without losing access to standard MP4 files.

## Core user stories and acceptance

| ID | Story | Acceptance |
|---|---|---|
| U01 | Connect the owner's Blink account safely | Local auth/2FA flow; secrets absent from browser storage/logs |
| U02 | Know whether no-plan recording works | Compatibility report with a real newly captured clip or an explicit blocker |
| U03 | See all camera events | Enumerates bursts and pages, survives restarts, no latest-clip-only shortcuts |
| U04 | Understand activity locally | Local vision model produces validated observations with original evidence |
| U05 | Find an old event | Saved filters and reproducible typed search; unknowns remain accessible |
| U06 | Receive useful phone alerts | Opt-in transport, quiet hours, test delivery, background/locked-phone validation |
| U07 | Avoid losing footage to AI failure | Download and playback continue when Ollama is offline |
| U08 | Manage space | Dry-run retention, favourite protection, low-space warning, no source deletion |
| U09 | Keep working after reboot | Documented startup mode and durable recovery; no fabricated catch-up events |
| U10 | See feature limitations | Unsupported controls explain why, without broken buttons or false success |

## Scope boundaries

MVP means M0–M6 with at least one verified accessible recording source. A release may be “import-only” when Blink compatibility is blocked, but it must not be called the completed subscription-free Blink integration.

Live viewing is a separately tested enhancement. Two-way talk, always-on capture, RTSP/ONVIF camera support, household role management, and an Android native shell are later items. The backend and provider boundary should allow these without forcing them into the first build.

## Explicit non-goals

No facial recognition, persistent identity tracking, person re-identification across cameras, licence-plate database, audio transcription by default, or inference about protected/sensitive traits. No automatic police contact, lock actuation, siren activation, or AI-controlled disarming. No password sharing service, multi-tenant SaaS, marketplace, or billing system.

No paid-feature bypass. The app can independently analyze files that the owner can legitimately retrieve, but cannot make an unsupported camera store events that its hardware/service does not expose. Blink's documented no-cost and recording features remain the starting boundary, not an API guarantee. [B1–B2](15_SOURCES_AND_VERSIONING.md#b1)

## Quality targets, not claims

Design for 1–10 cameras and a modest household event volume; measure actual load rather than assume a security-NVR workload. Keep interaction responsive while downloads or inference run. Report discovery delay, queue delay, inference duration, and notification delivery separately. Do not promise an arbitrary number of seconds from physical motion to phone alert before measurement.

All release-critical flows must remain usable at 360 px phone width and by keyboard. Use clear focus states, readable text, non-colour-only status indicators, reduced-motion support, and labelled controls. Keep the app useful even with AI disabled.
