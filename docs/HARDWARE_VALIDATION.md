# Local development evidence — 2026-10-06

This report contains public-safe hardware measurements, synthetic test results and owner-reported playback evidence. It does not include account IDs, credentials or real imagery. Paid-cloud evidence does not establish no-plan or Sync Module local retrieval compatibility.

## 2026-10-07 — automatic AI enabled by owner request

Stopped the owned development server cooperatively, acquired the exclusive profile lock and verified the existing `qwen3.8-27b-local:latest` alias through the current local-only runtime, vision metadata and stored matching-digest synthetic-image test. Enabled app-local automatic analysis with Balanced settings, preserving other settings and setting a new enablement timestamp so old recordings are not backfilled. No model download or global Ollama change was needed. Restarted the development interface on5174/backend8765; native liveness passed and sanitized state showed automatic AI enabled, the tested model selected and140 archived recordings at verification time. This confirms configuration/readiness; new-arrival scheduling is covered by generated cloud/local fixtures, and does not establish visual accuracy or new-module compatibility.

### Subsequent native automatic-arrival evidence

The next native-state check found144 archived events and four newly eligible automatic cloud jobs, all completed with persisted accepted analysis revisions. Each used the existing `qwen3.8-27b-local:latest` model and Balanced preset; all four original files remained present, and none was historical. Only validated category counts, frame counts, durations and safe job state were inspected. No private imagery, raw model text or identifying fields were sent to tooling.

| Automatic clip, in analysis order | Decode/inference/validation duration | Retained frames | Validated categories | Uncertainty flags |
|---|---|---|---|---|
| 1 |43.75 s|5|person|1|
| 2 |31.53 s|4|person, other, other|2|
| 3 |41.34 s|4|vehicle|1|
| 4 |50.02 s|6|person, vehicle|1|

These are automatic ingestion-to-analysis integration successes under the owner's current paid-cloud source. The durations exclude time waiting for Blink discovery and the AI queue. They do not validate model claims, object counts, no-plan retrieval, phone delivery or a labelled accuracy benchmark. The owner can compare each description/evidence strip with its locally saved original.

| Check | Observed result |
|---|---|
| GPU | NVIDIA RTX 5070 Ti, 16,303 MiB total; 12,427 MiB free at initial inspection |
| RAM / CPU | 31.6 GiB physical RAM; AMD Ryzen 9 7950X3D |
| Python / Node / npm | 3.12.10 / 24.19.0 / 11.17.0 |
| Native Ollama | Reachable on loopback port 11434; version 0.34.4 |
| Existing Qwen alias | `qwen3.8-27b-local:latest`; reported vision capability, Q4_K_M, local GGUF; digest `f68648ba1dcd2ae2dd0010f8aaa09439117098e34ac0a20845e93fe72f529c23` |
| Existing GPT-OSS aliases | Completion/tools/thinking capabilities; no reported vision support |
| Actual Ollama image inference | Generated PNG with red left half and blue right half; JSON-schema response correctly identified both colours; first/cold request 54.77 s |
| FFmpeg / ffprobe | Version 9.0.2 Gyan essentials; configured in the app's local tools folder; actual synthetic MP4 decode and playback exercised |
| Blink authentication/inventory | Owner completed login locally; one doorbell cached; inventory refreshed during the actual updated-app restart; credentials not supplied to tooling |
| Recording entitlement | **Paid plan**, owner-confirmed in this chat; not independently verified through a billing API |
| Sync Module | **Core**, identified from owner-provided packaging; firmware 19.20 is owner-reported and not used to infer storage capability |
| Cloud clips copied to PC | Owner confirmed import and playback; sanitized database inspection found 132 archived references/events, 132 completed downloads, no pending/failed transfers at that inspection |
| Running Ollama no-cloud policy | Owner approved the global opt-in configuration and restarted Ollama; `/api/status` subsequently confirmed literal `cloud.disabled=true` |
| Actual native generated-video pipeline | `scripts/smoke-local-ai.py` passed: image check 20.34 s; one-second generated clip analysis 33.89 s; one deduplicated frame, one accepted version; conservative unknown description for abstract colour blocks |
| New no-plan recording retrieval | **NOT VERIFIED** |
| Private-clip AI test | Existing Qwen analyzed five distinct frames from the newest archived camera clip. Initial output failed validation because it repeated action tags. After canonicalizing exact allowed-action repeats, the native read-only test passed in 47.92 s. The requested October 7 rerun through `scripts/probe-latest-ai.py` persisted one accepted Activity analysis in 52.38 s (52.50 s overall), with two entities and an uncertainty flag. The source clip was 10.002 s; distinct samples were at 0, 2, 4.001, 6.001 and 8.002 s. Runtime no-cloud policy passed; automatic AI stayed off. Visual accuracy still requires owner review. No imagery or raw model response was sent to coding tools. |
| Phone delivery / remote access | **NOT RUN** |
| Local live capture/library | Native generated-video checks passed for midstream capture, playable timestamp-normalized MP4, EOF/stop finalization, interrupted capture recovery, JPEG validation and protected media. Edge viewport checks exercised decoded-frame JPEGs and library playback with labelled capture API fixtures. Real camera capture/save and native Android/iOS behavior await owner testing; no private footage was inspected. |
| Actual live transport probe | After explicit owner approval of the exact self-signed relay certificate for Porchlight, the existing doorbell delivered an encoded video sample: 66,328 bytes, 5.44 s, receiving state. Probe exited successfully and cleaned up; no imagery was saved or displayed to coding tools. |
| Browser live decoding | Generated fragmented MP4 decoded in Edge at four viewport sizes; fresh-frame/stop/certificate UI passed. Actual camera playback **NOT RUN**. |

The initial synthetic model call used the native Ollama `/api/chat` interface with schema format, `num_ctx=4096`, `num_predict=100`, temperature 0, streaming off and no tools. That initial call left global configuration and existing model storage untouched. This checks basic image input only; it does not measure temporal accuracy, camera-image quality or sustainable processing throughput. The artifact's reported size was 17,741,872,150 bytes, so practical speed/memory needs evaluation before a model choice becomes a release default.

The approved configuration step saved `disable_ollama_cloud=true` in the user's `.ollama/server.json`. Automatic approval review blocked the attempted server restart; the owner then restarted Ollama manually, and the running no-cloud policy was verified. Private analysis is available behind the local model test and owner opt-in; the owner's AI setting remains off until enabled in the app. No real Blink credentials, footage or unredacted account diagnostics were read by coding tools. Source examples and browser screenshots are synthetic. The owner supplied product-package photographs; their serial/barcode information was not copied into this report or source control.

The packaging lists Sync Module Core and 1440×1440 video/three AA batteries, consistent with Blink's second-generation doorbell bundle. [Blink's Core FAQ](https://support.blinkforhome.com/en_US/sync-module-core-faq) confirms no Local Storage or Clip Backup and a power-only USB-C port. [The second-generation doorbell FAQ](https://support.blinkforhome.com/en_GB/video-doorbell-gen-2-faq) identifies USB storage via Sync Module 2 or microSD via Sync Module XR as supported local-storage options. This establishes the documented hardware boundary; it does not establish unofficial adapter retrieval compatibility. With the current Core, Porchlight's implemented test path is paid-cloud clips copied to this PC.

## Further native analysis and search probes — 2026-10-07

Three explicit archived-clip probes with the selected Qwen model accepted validated output in 53.89, 42.17 and 25.08 seconds, retaining five, one and two frames respectively. Whole-frame deduplication was too insensitive to small local changes. The revised 48×48 signature also compares 4×4 tiles; an offset-two rerun retained four frames and completed analysis in 47.94 seconds (48.08 seconds overall). Its validated description reported a person, a black car and an object, with uncertainty and unknown movement. These are model claims awaiting owner visual review, not confirmed identities, accurate counts or an accuracy benchmark. No images or raw model prose were returned to coding tools; automatic AI stayed off.

A synthetic natural-language search probe initially missed the vehicle filter (6.03 seconds). After tightening the bounded filter prompt, the retest proposed vehicle/black/evening filters in 3.59 seconds. The owner must still review proposals before applying them; this small probe is not a search benchmark.

Native model tests used the existing installation and runtime local-only policy. No model was installed, relocated or unloaded. New-module no-plan clips, real camera command read-back, phone delivery and the labelled holdout benchmark remain NOT RUN.

## Workload probes and native launch · 2026-10-07

Before migration, a stopped backup verified 133 files / 176,563,555 bytes at schema0013, including file hashes and SQLite integrity. The wrapper initially read a nonexistent `passed` result key after successful verification; a read-only verification confirmed success without making a second backup.

Native newest-clip probe with `--workload light`: ANALYSIS_INVALID after 45.88 seconds. Its exact validation reason is unknown because safe reason classification was added afterward; no raw response was inspected. Native `--workload balanced`: accepted in 43.66 seconds analysis / 43.80 seconds overall, 5 frames, daylight_color. Validated summary: “A person approaches. A black car is visible.” Entities were person/approaching/toward_camera and black car/visible/unknown direction; a generic sampled-image uncertainty flag remained. Automatic AI was unchanged/off. These results do not prove visual truth or establish facial recognition.

Dev readiness initially timed out because a Windows venv launcher and its Python server have different PIDs. A fresh launch-ID handshake replaced that assumption; native dev then started on 5174 with backend8765. The directly owned synthetic native lifecycle test also proved cooperative stop with an open SSE connection and marker cleanup. No owner camera control, history start, retention, rule or task registration was performed. Real new-module/phone/40-clip holdout/soak acceptance remains NOT RUN.


## Light validation diagnostic · 2026-10-07

A further native newest-clip probe (`scripts/probe-latest-ai.py --model qwen3.8-27b-local:latest --workload light`) rejected output after45.77 s with allowlisted reason `subtype_mismatch`. The validator did not accept an object subtype inconsistent with its category. Automatic AI and persisted Balanced selection were unchanged; no raw response or imagery went to coding tools. This identifies a contract failure and is not evidence about the actual object's appearance or an accuracy measure. Balanced remains the selected preset; Light needs further prompt/model evaluation.

After adding explicit category/subtype mappings to vision prompt 1.1, the same scoped native command passed: three frames, daylight_colour, 36.83 seconds analysis / 36.95 seconds overall. Validated wording: “A person moves toward the camera. A black car is visible.” Observations were person (null subtype/colour, visible/moving, toward_camera) and vehicle (car/black, visible, unknown direction); sampled-image uncertainty remained. The running server verified `cloud.disabled=true`. Automatic AI stayed off and Balanced remained selected. This is one contract-success measurement, not a visual-accuracy score, a comparative performance benchmark or identity recognition. Earlier rejected runs remain evidence above.


## Second recent clip under prompt1.1 · 2026-10-07

The explicit native probe with `--workload balanced --offset 1` accepted a second recent owner recording: six frames, daylight colour,55.00 seconds analysis/55.11 seconds overall. Validated description: “A person moves away from the camera. A black car is visible. A white car is visible.” The person had visible/moving actions and away_from_camera direction; both cars were visible with unknown directions. Model uncertainty remained. Runtime local-only policy was true, automatic AI stayed off, and all132 source recordings remained. This adds one different-clip integration result, not a reviewed accuracy score, face identity or a 40-clip holdout. No private imagery or raw model text was sent to coding tools. The app restarted on5174/backend8765 afterward.


## Native automatic-sync recovery — 2026-10-07

The owner reported today's Blink clips missing locally. The active scan had no errors but its incremental cursor was past their timestamps. A stopped-profile serialized listing probe using the existing session found today's available recordings with a wider cutoff. After adding24-hour routine reconciliation and restarting, the actual background worker discovered, downloaded and validated four of today's clips, taking132 archived events to136. The next observed scheduled complete scan added another clip, taking the archive to137, with no pending/failed references. These are native paid-cloud retrieval results; no real imagery was viewed by coding tools. Automatic AI remained off; no camera/subscription setting changed. The generated-video delayed-visibility regression passed; native no-plan/phone/visual-accuracy gates remain pending.
