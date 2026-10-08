# 01 · Feature matrix and scope

Statuses below are **planned scope**, not implemented/verified claims. “Core” means build it; “conditional” means show it only after an actual provider capability test. Sources for the research observations are in [15](15_SOURCES_AND_VERSIONING.md).

| Feature | Scope | Implementation and caveat |
|---|---|---|
| Camera cards, grouping, custom local names | Core | Inventory through provider; own metadata stored locally |
| Cached snapshot with capture age | Core/conditional | Never imply a cached image is current; no frequent wakeups |
| Network arm/disarm | Conditional core | Manual action, pending state, read-back confirmation |
| Per-camera motion enable/disable | Conditional core | Separate from network arming and notification snooze |
| Battery, network status, temperature | Conditional core | Nullable metrics with source timestamp; no invented percentages |
| Cloud clip history | Conditional core | Only when the account legitimately exposes it |
| Sync Module local clip history | Conditional core | Separate manifest/retrieval implementation; real no-plan test |
| Manual MP4/JPEG import | Core | Useful development/fallback path, explicitly not live camera integration |
| Local timeline and playback | Core | Native media routes with authorization and Range support |
| Favourite, note, export, delete local copy | Core | No upstream deletion by default; dedup tombstones prevent reimport |
| AI person/vehicle/animal/package descriptions | Core | Vision-capable Ollama model plus evidence checks |
| Vehicle colour | Conditional AI | Only visible colour imagery; monochrome/IR yields unknown |
| Direction, approach, departure, passing | Conditional AI | Requires distinct timestamped frames and adequate evidence |
| Package delivery/removal | Later refinement | Require visible before/after action; distinguish package merely present |
| Full-text and typed filtered search | Core | SQLite FTS and deterministic filters |
| Natural-language event search | Core after basic search | Model proposes a bounded query, never executable SQL |
| Daily digest | Core after event analysis | Grounded in saved event IDs, with coverage-gap notice |
| Notification rules and snooze | Core | Deterministic application rules; preserves event history |
| Background Android alerts | Core release path | Implement and test Web Push or self-hosted ntfy transport |
| Privacy-first generic lock-screen text | Core | User can opt in to descriptive text; no public thumbnail URLs |
| Multi-camera related-event grouping | Later | Time-based association only; no claim of same person's identity |
| AI activity zones | Later | Exact zone rules need validated detector/tracker or explicit conservative crop policy |
| Camera's built-in motion zones/sensitivity | Conditional later | Only if current adapter exposes tested controls |
| Experimental live video | M7 | On demand, short session, measured start/stop, explicit stream status |
| Listen-in audio | M7 conditional | Only verified format/camera support; disabled by default |
| Two-way audio | Deferred/unverified | Do not create a nonfunctional microphone control |
| Continuous Blink recording | Not promised | Not achieved by replaying clips or endlessly renewing sessions |
| RTSP export of downloaded clips | Optional later | Must say recorded replay, not live; not needed for MVP |
| Self-managed backup/restore | Core release path | Database-consistent and includes media/derived files |
| Automatic source clip deletion | Excluded by default | Local retention must never become camera/cloud deletion |
| Face/identity recognition | Excluded | Not needed to describe what happened |
| Local face detection | Optional owner-approved extension | YuNet sampled counts/timestamps/size/sharpness; no identities. See [setup and evidence](FACE_DETECTION.md) |

## What we are borrowing conceptually

`blinkpy`: authenticated account/camera operations, cloud/local-storage access, and an isolated provider adapter. [R1–R4](15_SOURCES_AND_VERSIONING.md#r1)

Home Assistant: capability-aware controls and observable integration health, without installing its complete runtime. Its stock Blink integration's documented limitations are not a blanket limit on every possible Blink library. [R8](15_SOURCES_AND_VERSIONING.md#r8)

LLM Vision: event-oriented visual summaries and human-review timelines, independently implemented in our application. [R7](15_SOURCES_AND_VERSIONING.md#r7)

Frigate: distinction between object detection, event review, and generative descriptions. A Blink clip workflow should not be presented as Frigate's continuous live detection pipeline. [R9](15_SOURCES_AND_VERSIONING.md#r9)

Homebridge Blink Security: lessons about session lifecycle and conditional live-view capabilities. Study documented behaviour; no default code transplantation. [R5](15_SOURCES_AND_VERSIONING.md#r5)

`blinkbridge`: confirms a clips-to-stream interoperability idea, but replaying clips is unnecessary for our direct clip-analysis path. [R6](15_SOURCES_AND_VERSIONING.md#r6)

## Product toggles and honest labels

The camera capability object distinguishes `unknown`, `supported`, `unsupported`, `temporarily_unavailable`, and `needs_reauth`, with evidence time and reason. Runtime availability is not the same thing as long-term support.

Examples: “Local clip retrieval not yet tested”; “Live view unavailable for this camera”; “Recording from 2:14 p.m. — not live”; “AI analysis pending”; “No clips found in the last successful sync; coverage may be incomplete.”

Do not show “person detection enabled on camera” when Porchlight merely analyzes recordings afterwards. Likewise, an app-only schedule or privacy mask is not a setting written to Blink hardware.
