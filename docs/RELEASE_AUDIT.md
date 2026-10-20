# Release evidence review · 2026-10-20

This review supersedes the October 7 release summary. Porchlight is a runnable Windows development preview, with real owner-confirmed paid-cloud archiving, local AI review, Android push and direct cellular HTTPS Live View. It is not yet accepted as a generally reliable subscription-free release. The repository remains private.

## Evidence and publication gates

| Boundary | Evidence now available | Remaining work |
|---|---|---|
| Durable archive | Real fresh paid-cloud imports and post-restart use; 12 additional clips recovered after a manual retry. Synthetic pagination, lease, deduplication, Retry-After and account/source isolation checks | Deploy the new automatic recovery behavior and observe a real temporary outage plus the soak. Old expired sources cannot be recovered. |
| Optional AI | Native local inference; owner completed daytime/nighttime Qwen and face-match review | Quantified holdout and action/frame-selection comparison; no general accuracy claim. AI-disabled collection must stay functional. |
| Phone | Native synthetic push encryption round trip; owner confirmed home-screen reopening, actual push descriptions/name/thumbnail delivery and direct cellular HTTPS Live View | Complete a recorded Wi-Fi/cellular × locked/closed-app acceptance matrix, tap-to-recording, permission/session expiry and preview timing. |
| HTTPS operations | Owner-managed direct HTTPS worked on cellular; managed certificate issuance and reuse were verified | Observe future timed renewal and changing public-IP handling. Personal DNS/router/certificate/connector files remain outside Git. Generic setup guides are included. |
| Local storage/no plan | XR+ present; official local list and adapter manifest were empty under an active paid plan | Genuinely new playable local clips, transfer/playback, restart and verified eligible no-plan evidence. No subscription change is required or authorized by this review. |
| Installation | Bootstrap preflight and existing-environment copied-source tests | Install locked dependencies in a fresh environment, ideally a second Windows PC, using only the public instructions. Do not label a copied venv a clean install. |
| Licensing | Owner approved MIT; root licence, package metadata, GitHub footer credit and third-party ledger updated | Resolve uri-js-replace 1.0.1's missing upstream notice or replace the dependency through a tested change. Review any future bundled binaries/weights separately. |
| Privacy | Working files and 607 reachable historical blobs scanned locally at the start of this review; only brand/icon binaries found | Two historical BUILD_STATUS versions contain machine-specific paths (four matches). Sanitize history or choose a clean public-history publication plan before changing visibility. The scan is pattern-based, not a guarantee. |
| Reliability | Existing backup/restore and worker isolation fixtures | A fresh private archive backup/restore and a 24–48-hour soak with sleep/resume, network loss and storage pressure. |

The current OSV query returned **no known advisory matches across 155 exact package versions** on 2026-10-20, including optional push pins. See [DEPENDENCY_AUDIT.json](DEPENDENCY_AUDIT.json). This is a dated advisory result; package notices and security review are separate. All media used by automated checks are synthetic. Coding tools did not open real recordings or export private account data.

## Reproduce software and privacy checks

```powershell
.\setup.ps1 -Check
.\test.ps1 -Browser
.\.venv\Scripts\python.exe scripts/audit-repository.py --output C:\PrivateReviews\porchlight-source-review.json
.\.venv\Scripts\python.exe scripts/audit-dependencies.py --online --include-push-candidates
```

Create the review directory outside the checkout first. The repository audit reports locations/categories without matched values and returns nonzero when manual triage is needed. Supply `--private-patterns` with an external JSON category-to-regex file to check personal identifiers. Fetch refs before reviewing history. Do not commit that private input or detailed report. See [privacy scope](REPOSITORY_PRIVACY_REVIEW.md).

Exact final commands and test totals for the current change are recorded in [BUILD_STATUS.md](../BUILD_STATUS.md). Tests prove code behavior in synthetic profiles; owner observations establish only the specific real integration described. No repository visibility change is part of this work.
