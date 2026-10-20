# Known limitations · 2026-10-20

Porchlight is a Windows development preview. Its original code/documentation are MIT licensed. The owner authorized the first public development preview on 2026-10-20; this page supersedes the earlier October 7 limitations.

Owner acceptance update, 2026-10-20: the owner reports completing a fresh archive backup/isolated restore, a 24–48-hour soak covering automatic sync recovery, sleep/resume and network interruptions, locked-screen/closed-app Wi-Fi/cellular phone alerts with thumbnails and recording taps, and a new-user Windows installation test including script restrictions. No detailed logs, exact soak duration or measurements were provided to coding tools. These results supersede the corresponding pending checks below for the tested setup; they do not establish other-device compatibility, session-expiry/revocation behavior, storage-pressure handling or subscription-free retrieval.

| Area | Evidence | Remaining boundary |
|---|---|---|
| Cloud archive | Real owner-confirmed paid-cloud imports/playback; durable pagination/deduplication tests; owner-reported automatic recovery/soak acceptance | Blink availability, polling and bounded retry backoff add latency. Expired source clips cannot be recovered. |
| Sync Module storage | XR+ storage flags and a valid empty manifest were observed | No actual local recording transfer or fresh no-plan retrieval proved. Card backups during a plan differ from direct local clips. Do not cancel a plan for testing. |
| AI | Native local vision inference and owner daytime/nighttime review completed | No labelled accuracy benchmark. Sampled frames can miss activity; schema validation is not visual truth. Door-action refinements need measured comparison. |
| Faces | Owner-reviewed local SFace profiles and possible name suggestions | Uncertain matches stay unnamed. Thresholds are not calibrated identity guarantees; no demographic or criminal-intent inference. |
| Live viewing | Owner confirmed phone Live View over direct cellular HTTPS | Bounded, experimental and capability-gated. Audio requires a usable supplied track. Broader Record/Snapshot/reconnect hardware acceptance remains incomplete. No two-way talk or continuous recording. |
| Phone | Owner confirmed Android home-screen use, push text/name updates, thumbnails and direct cellular access; listed locked-screen/closed-app Wi-Fi/cellular and recording-tap checks reported complete | Other browsers/devices, session expiry and revocation need separate evidence. Thumbnail timing and display vary. |
| Operations | Persistent queue, synthetic checks and redacted diagnostics; same-PC clean dependencies/playback/restart verified; fresh archive restore, new-user install and soak reported complete by the owner | Script policy remains a prerequisite; no signed packaged installer. Storage pressure, unavailable-volume handling and broader environments need separate evidence. |
| Distribution | MIT selected; pinned dependencies and retained notices; current advisory query | The identified notice gap and reachable-history machine paths are resolved. Other platform/native/model distribution reviews remain separate; no executable/model redistribution clearance is implied. |

AI is optional. Without it, available recordings, source/camera/time metadata, measured duration, playback, notes and generic alerts remain usable. No action or person is invented from missing AI output. Historical imports remain silent and do not trigger automatic analysis or activity alerts.

New Blink retrieval and live viewing require Blink's internet services. Archived files can still be viewed locally during an upstream outage. Cloud downloads accept validated relative REST locators only; external/signed locators and redirects fail closed. Unknown hardware/entitlement stays unknown.

The PC must remain awake and reachable. Home-screen installation does not move the backend to the phone. Standard Web Push uses browser-vendor infrastructure; private image/video fetches still require authenticated PC access. Quiet updates target an existing notification and cannot force Android to display an image or recreate a dismissed face alert.

All inference stays local; models and FFmpeg are not bundled. Optional AI/face/push installation and network changes require explicit local choices. Two-way talk, native Android packaging and broader platform support remain future work. See [release checklist](RELEASE_CHECKLIST.md) and [build status](../BUILD_STATUS.md).
