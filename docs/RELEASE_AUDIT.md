# Release evidence review · 2026-10-20

This review supersedes the October 7 release summary. Porchlight is a runnable Windows development preview, with real owner-confirmed paid-cloud archiving, local AI review, Android push and direct cellular HTTPS Live View. It is not yet accepted as a generally reliable subscription-free release. The owner authorized public visibility and the first development-preview release on 2026-10-20.

Owner acceptance update, 2026-10-20: the owner reports completing all four requested checks: fresh archive backup/isolated restore with recordings, notes and settings; a 24–48-hour soak with automatic recovery, sleep/resume and network interruptions; locked-screen/closed-app Wi-Fi/cellular alerts, thumbnails and tap-to-recording; and new-user Windows installation including script restrictions. This is owner-reported acceptance, not newly executed automated evidence. Exact duration, logs, versions and timing measurements were not supplied. It supersedes the corresponding pending items in the table below for the tested setup. No-plan storage retrieval, broader device/browser coverage, session expiry/revocation, and hosted CI remain separate boundaries. The owner subsequently gave explicit publication approval on 2026-10-20.

## Evidence and publication gates

| Boundary | Evidence now available | Remaining work |
|---|---|---|
| Durable archive | Real fresh paid-cloud imports and post-restart use; recovery fixtures; owner-reported automatic recovery and soak acceptance | Old expired sources cannot be recovered. Broader storage-pressure and unavailable-volume checks need separate evidence. |
| Optional AI | Native local inference; owner completed daytime/nighttime Qwen and face-match review | Quantified holdout and action/frame-selection comparison; no general accuracy claim. AI-disabled collection must stay functional. |
| Phone | Native synthetic encryption checks; owner-confirmed home-screen use, descriptions/names/thumbnails, cellular Live View and listed Wi-Fi/cellular × locked/closed-app recording-tap checks | Broader devices/browsers, permission/session expiry and revocation need separate evidence. No delivery-time guarantee. |
| HTTPS operations | Owner-managed direct HTTPS worked on cellular; managed certificate issuance and reuse were verified | Observe future timed renewal and changing public-IP handling. Personal DNS/router/certificate/connector files remain outside Git. Generic setup guides are included. |
| Local storage/no plan | XR+ present; official local list and adapter manifest were empty under an active paid plan | Genuinely new playable local clips, transfer/playback, restart and verified eligible no-plan evidence. No subscription change is required or authorized by this review. |
| Installation | Real fresh source/dependencies, isolated profile/tools and synthetic playback/restart passed; owner additionally reports completing new-user Windows setup including script restrictions | A permitted script workflow remains required; no signed packaged installer. Hosted runner remains blocked by GitHub account billing/spending limits. Other Windows environments are not certified. |
| Licensing | Owner approved MIT; root licence, package metadata, GitHub footer credit and third-party ledger updated | The missing notice is now resolved: the retained upstream MIT-0 grant covers verified unchanged source and all installed dist files. Review future bundled binaries/weights and other platforms separately. |
| Privacy | Working files and 607 reachable historical blobs scanned locally at the start of this review; only brand/icon binaries found | Owner-authorized history rewrite removed all four paths from two BUILD_STATUS blobs, preserving the latest tree and all checkpoint tag names. Published refs and a fresh clone are rechecked. GitHub caches/other clones remain outside local erasure guarantees; the scan is pattern-based. |
| Reliability | Existing backup/restore and worker isolation fixtures; owner reports fresh archive restore and a 24–48-hour soak with sleep/resume, network interruptions and automatic recovery | Detailed measurements were not supplied. Storage pressure, unavailable volumes and other unreported fault cases remain separate. |

The current OSV query returned **no known advisory matches across 155 exact package versions** on 2026-10-20, including optional push pins. See [DEPENDENCY_AUDIT.json](DEPENDENCY_AUDIT.json). This is a dated advisory result; package notices and security review are separate. All media used by automated checks are synthetic. Coding tools did not open real recordings or export private account data.

## Reproduce software and privacy checks

```powershell
.\setup.ps1 -Check
.\test.ps1 -Browser
.\.venv\Scripts\python.exe scripts/audit-repository.py --output C:\PrivateReviews\porchlight-source-review.json
.\.venv\Scripts\python.exe scripts/audit-dependencies.py --online --include-push-candidates
```

Create the review directory outside the checkout first. The repository audit reports locations/categories without matched values and returns nonzero when manual triage is needed. Supply `--private-patterns` with an external JSON category-to-regex file to check personal identifiers. Fetch refs before reviewing history. Do not commit that private input or detailed report. See [privacy scope](REPOSITORY_PRIVACY_REVIEW.md).

Exact final commands and test totals are recorded in [BUILD_STATUS.md](../BUILD_STATUS.md). Tests prove code behavior in synthetic profiles; owner observations establish only the specific real integration described. The first public preview is explicitly owner-authorized; no private runtime or network settings are published.
