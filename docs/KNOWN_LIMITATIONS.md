# Known limitations · 2026-10-20

Porchlight is a Windows development preview. Its original code/documentation are MIT licensed. The repository remains private pending the publication checks; this page supersedes the earlier October 7 limitations.

| Area | Evidence | Remaining boundary |
|---|---|---|
| Cloud archive | Real owner-confirmed paid-cloud imports, playback and recovery after manual retry; durable pagination and deduplication tests | New automatic cooldown recovery has synthetic tests; needs deployment and real outage/soak observation. Blink availability and polling add latency. |
| Sync Module storage | XR+ storage flags and a valid empty manifest were observed | No actual local recording transfer or fresh no-plan retrieval proved. Card backups during a plan differ from direct local clips. Do not cancel a plan for testing. |
| AI | Native local vision inference and owner daytime/nighttime review completed | No labelled accuracy benchmark. Sampled frames can miss activity; schema validation is not visual truth. Door-action refinements need measured comparison. |
| Faces | Owner-reviewed local SFace profiles and possible name suggestions | Uncertain matches stay unnamed. Thresholds are not calibrated identity guarantees; no demographic or criminal-intent inference. |
| Live viewing | Owner confirmed phone Live View over direct cellular HTTPS | Bounded, experimental and capability-gated. Audio requires a usable supplied track. Broader Record/Snapshot/reconnect hardware acceptance remains incomplete. No two-way talk or continuous recording. |
| Phone | Owner confirmed Android home-screen use, actual push text/name updates, a thumbnail and direct cellular access without the private VPN | Not a guarantee for every browser/OS. Test locked-screen Wi-Fi/cellular delivery, session expiry, revocation and exact-recording taps as a matrix. Thumbnail timing and display vary. |
| Operations | Persistent queue, backup/restore tests and redacted diagnostics | Fresh owner archive backup/restore, clean dependency install, 24–48-hour soak, sleep/resume and real network-loss acceptance remain open. |
| Distribution | MIT selected; pinned dependencies and retained notices; current advisory query | One upstream development-dependency notice remains unresolved; history contains old machine-specific paths. No executable/model redistribution clearance implied. |

AI is optional. Without it, available recordings, source/camera/time metadata, measured duration, playback, notes and generic alerts remain usable. No action or person is invented from missing AI output. Historical imports remain silent and do not trigger automatic analysis or activity alerts.

New Blink retrieval and live viewing require Blink's internet services. Archived files can still be viewed locally during an upstream outage. Cloud downloads accept validated relative REST locators only; external/signed locators and redirects fail closed. Unknown hardware/entitlement stays unknown.

The PC must remain awake and reachable. Home-screen installation does not move the backend to the phone. Standard Web Push uses browser-vendor infrastructure; private image/video fetches still require authenticated PC access. Quiet updates target an existing notification and cannot force Android to display an image or recreate a dismissed face alert.

All inference stays local; models and FFmpeg are not bundled. Optional AI/face/push installation and network changes require explicit local choices. Two-way talk, native Android packaging and broader platform support remain future work. See [release checklist](RELEASE_CHECKLIST.md) and [build status](../BUILD_STATUS.md).
