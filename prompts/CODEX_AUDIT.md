# Audit before release

```text
Audit the implemented Porchlight app against AGENTS.md and docs/00 through docs/16. Inspect actual code, locked dependencies, tests, runtime configuration and BUILD_STATUS.md, not only previous summaries. Do not mark a feature complete without evidence.

Prioritize: leaked credentials/signed URLs/private media; improper first-run/session/CSRF/Host/Origin security; arbitrary file/URL access; accidental cloud-backed Ollama models; fake no-plan support; cloud-only helper mistakenly used for local storage; lost clips/pagination gaps; duplicate jobs/alerts; unsafe retention/restore; misleading LIVE labels; inferred IR colours or single-frame movement; untested background phone delivery; unreviewed GPL/unlicensed copying.

Run safe automated tests. Do not run destructive controls on the real Blink system, fill the owner's disk, trigger an API load test, change global Ollama settings, or upload footage to remote CI. Real-device tests requiring the owner must remain explicitly pending.

Fix confirmed problems in focused patches with regression tests. Report findings ordered by impact with file/line references, evidence and remaining risk. Update BUILD_STATUS.md and the version/licence ledger. Separate package checks, mock tests and actual hardware verification. Produce exact commands to launch and verify the release, with honest supported/unsupported capabilities.
```
