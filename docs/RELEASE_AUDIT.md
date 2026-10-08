# Release evidence review · 2026-10-07

Porchlight is a runnable local development build with owner-confirmed paid-cloud playback and native local AI integration. It is not yet an accepted subscription-free, background-phone or hardware-verified live release. This review applies the acceptance gates in [13](13_TESTS_AND_ACCEPTANCE.md) and the audit prompt; it does not certify every possible security or device behavior.

## Findings and remaining gates, ordered by release impact

1. **Subscription-free retrieval remains unverified.** The current owner account has a paid plan and Sync Module Core. Successful cloud imports cannot validate the proposed new module's no-plan local-storage path. Eligible hardware, owner-confirmed entitlement, three fresh clips and another after restart are required. The independent local adapter and capability guards have fixture coverage. See [compatibility](02_BLINK_COMPATIBILITY_AND_NO_SUBSCRIPTION.md).
2. **Background phone delivery remains unverified.** Web Push application behavior is tested through controlled seams, but the optional encryption packages are not installed. Its native round-trip test is skipped. HTTPS reachability, actual Android pairing, closed/locked-screen display, revoked permission, Wi-Fi/cellular and authenticated notification tap need separate owner actions. Do not describe provider acceptance as observed phone delivery. See [phone setup](WEB_PUSH.md).
3. **AI integration is demonstrated; scene accuracy is not.** After the owner enabled automatic AI, four newly retrieved cloud clips completed native Balanced analysis in31.53–50.02 seconds, with4–6 frames, accepted revisions and preserved originals. Prior manual Balanced/Light probes remain separate evidence. Only validated neutral fields and timing were inspected by coding tools. Neither these results nor schema validation establish visual truth. Owner review, the proposed labelled holdout, missed-event/unsupported-claim measurements and busy/idle GPU comparison remain pending. Earlier rejected Light output is retained in the evidence log; its later one-clip success does not erase that failure. See [hardware evidence](HARDWARE_VALIDATION.md).
4. **Fresh installation and redistribution are incomplete.** A copied-source test proves that runtime modules, migrations, schemas, prompts and built assets work independently of the original source location, using the existing interpreter and installed dependencies. It does not install from lockfiles into a clean environment or prove another PC's prerequisites. Read-only bootstrap preflight is separately tested. Three missing exact-version notices were recovered; `uri-js-replace` 1.0.1 lacks an authoritative retained notice. The distribution licence and any model/native packaging review remain owner decisions. See [notice review](NOTICE_REVIEW.md).
5. **Hardware and operational acceptance remain bounded.** Real relay/encoder delivery was measured with the exact approved Porchlight certificate pin. Generated browser fixtures do not prove actual camera browser playback, Record/Snapshot or reconnection. Actual controls, removable-storage failure, startup sign-in, sleep/resume, token/network loss and the proposed 24–48-hour soak remain unrun. No owner camera write, startup registration, tunnel or global setting change was performed during this review.
6. **A clock-correction restart defect was confirmed and fixed.** Recovery previously changed running jobs to queued while retaining an availability timestamp that could lie in the future after a backward clock correction. Interrupted recording and unaccepted AI jobs now clamp availability to the new current time. Accepted AI results remain completed; unrelated queued backoff is retained. Focused tests first failed in both backward-clock cases, then passed for simulated ±one-hour changes, repeated claiming and deferred provider work. The fix is in `ingestion/recordings.py:65` and `ai/pipeline.py:57`. These simulations do not certify real Windows sleep/resume or clock adjustments while the application is stopped for an extended period; durable queued deadlines remain UTC.

## Reviewed boundaries and evidence

| Boundary | Concrete implementation / tests | Limit of evidence |
|---|---|---|
| Host, Origin, remote setup, CSRF and sessions | `app.py:139` BoundaryMiddleware, `app.py:394` session cookie; security/remote/native source-checkout tests | Actual external HTTPS proxy not configured |
| Private playback and offline behavior | Authenticated original/thumbnail/HEAD/Range routes; `apps/web/public/sw.js` fetch handler; catalog/import/PWA/browser tests | Phone playback variants require owner testing |
| Local AI and safe evidence | `ai/ollama.py:78` runtime cloud policy; `ai/observations.py:21` frozen prompt/schema digest; analysis/Ollama/evidence tests | Schema, neutral formatting and frame hashes are not scene accuracy |
| Durable archive and source partition | `ingestion/recordings.py`, `ingestion/history.py`; recordings/history/local-storage tests | New module, no-plan retrieval and real outage soak remain unverified |
| Conflicting review/edit actions | Rule revisions0017, owner-label revisions0016; simultaneous update and four-viewport native API journeys | No owner rules were created for testing |
| Keyboard and accessible names | Six-page Skip to content route/filter preservation and exposed-control names at four widths; long-history modal focus restoration | Bounded browser checks; actual assistive-technology and complete WCAG review are not established |
| Recovery and source relocation | `test_native_lifecycle.py`, `test_source_checkout.py`, clock-change cases in recordings/analysis tests | Existing installed runtime, generated MP4 and isolated synthetic profiles only |
| Licence/advisory intake | Locked inventory, retained notices and provenance hashes; prior point-in-time OSV/npm results | Not legal clearance or a perpetual vulnerability guarantee |

All test media and test credentials are synthetic. Native AI input, archive data and backups remain outside the repository; no real imagery, raw model output or tokens were sent to coding tools. Nothing was pushed or deployed externally. See [build status](../BUILD_STATUS.md) for exact commands, totals, failed/skipped checks and the [implementation ledger](IMPLEMENTATION_AUDIT.md) for the original milestone scope.

## Reproduce the software checks

```powershell
Set-Location -LiteralPath C:\Projects\Porchlight
.\bootstrap.ps1 -Check
.\test.ps1 -Browser
```

Do not run bootstrap installation, optional push installation or task registration merely to recheck an existing environment. `test.ps1` uses the existing runtime; native decoder and copied-source cases run against temporary profiles.

The current development app is served at `http://127.0.0.1:5174`, with backend 8765. For a built-only launch, first stop the existing owner backend cooperatively, close its dev terminal, then use:

```powershell
.\start.ps1
# Open http://127.0.0.1:8765
```

Private release requires the remaining acceptance actions in [the runbook](RELEASE_CHECKLIST.md). Keep unverified capabilities visibly limited and retain private repository status when the owner approves the first push.
