# 16 · Hardware validation report template

**STATUS: NOT RUN. This document is a blank template, not evidence of working hardware.** Create a private completed copy outside source control; add only a redacted summary to the repository. Never include account email, serial numbers, auth codes, session tokens, signed clip URLs, private footage or unredacted device screenshots.

## Environment

Test date/time/timezone: NOT RECORDED  
Application commit / package versions: NOT RECORDED  
Windows version / CPU / RAM / GPU / reported VRAM: NOT RECORDED  
Ollama version / selected model tag / digest / quantization: NOT RECORDED  
Local-only verification method: NOT RUN  
FFmpeg/ffprobe version and distribution licence: NOT RECORDED  
App origin / transport mode (redacted where needed): NOT RECORDED  
Archive volume type and free space, not a private path: NOT RECORDED

## Blink recording source

Camera model(s), nonidentifying labels: UNKNOWN  
Sync Module model: UNKNOWN  
Removable storage type / status: UNKNOWN  
Recording source: UNKNOWN (cloud / local-storage / import)  
Paid/trial entitlement state: UNKNOWN  
Legacy entitlement, when relevant: UNKNOWN  
Entitlement evidence: NOT RECORDED (API observation / owner check in official app / other)  
Pinned adapter version and operation map: NOT RECORDED  
No-plan readiness: UNVERIFIED

Official compatibility alone is not a successful unofficial-API test. A source whose entitlement cannot be established remains unverified. Do not cancel a plan or change armed state merely to complete this report.

## Capability results per camera

| Capability | State (verified / unsupported / unknown / failed) | Evidence and limitation |
|---|---|---|
| Inventory / stable identity | unknown | NOT RUN |
| Last snapshot / real timestamp | unknown | NOT RUN |
| Fresh cloud recording retrieval | unknown | NOT RUN |
| Fresh local-storage retrieval | unknown | NOT RUN |
| Network arm state read | unknown | NOT RUN |
| Owner-approved control and readback | unknown | NOT RUN |
| Motion enable/disable | unknown | NOT RUN |
| True live playback | unknown | NOT RUN; experimental |
| Listen audio / two-way talk | unknown | NOT RUN; not presumed supported |

## New-clip gate

| Clip | Entitlement state at capture | Automatic discovery | Download/playback | Correct source/camera/time | Duplicate count |
|---|---|---|---|---|---|
| New clip 1 | UNKNOWN | NOT RUN | NOT RUN | NOT RUN | NOT MEASURED |
| New clip 2 | UNKNOWN | NOT RUN | NOT RUN | NOT RUN | NOT MEASURED |
| New clip 3 | UNKNOWN | NOT RUN | NOT RUN | NOT RUN | NOT MEASURED |
| New clip 4 after app restart | UNKNOWN | NOT RUN | NOT RUN | NOT RUN | NOT MEASURED |

Official app coexistence: NOT RUN  
No active paid/trial source verified during these tests: NOT RUN  
Conclusion: UNVERIFIED / BLOCKED / VERIFIED — select only from evidence.

## Analysis quality and resource report

Dataset size / holdout count / permitted private evidence location: NOT RECORDED  
Model/prompt/schema versions and effective parameters: NOT RECORDED  
Daylight colour precision / night-colour suppression / temporal claims: NOT MEASURED  
Important-event misses / unsupported claims / unknown rate: NOT MEASURED  
Queue wait / decode / inference / total latency, median and range: NOT MEASURED  
Normal-workload GPU/memory observations: NOT MEASURED  
Ollama offline recovery / raw clip preservation: NOT RUN

## Phone delivery and operations

Phone/OS/browser/provider: NOT RECORDED  
Foreground / closed page / locked screen: NOT RUN  
Wi-Fi delivery / cellular delivery: NOT RUN  
Tap-to-open authentication / away-from-home reachability: NOT RUN  
Observed end-to-end delay and missed/duplicate notifications: NOT MEASURED  
Sleep/resume recovery / token refresh / network retry: NOT RUN  
Retention / favourite protection / backup restore: NOT RUN

## Final scope declaration

Release classification: NOT ESTABLISHED  
Known unsupported features: NOT RECORDED  
Outstanding tests and owner actions: NOT RECORDED  
Redacted evidence references: NONE  
Reviewer and review date: NOT RECORDED
