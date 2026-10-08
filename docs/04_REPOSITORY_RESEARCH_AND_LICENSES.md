# 04 · Repository research and licence boundaries

Reviewed on 2026-10-06 from public primary documentation/source. This is an engineering intake ledger, not a legal clearance opinion. No third-party repository source code is bundled in this package. Verify the licence at the exact version before code reuse or distribution, including dependencies and model weights.

## Reuse plan

| Project | Observed licence/status | What to take | Decision |
|---|---|---|---|
| `fronzbot/blinkpy` | MIT shown in repository | Owner auth, inventory, controls, cloud/local clip operations | Primary dependency behind an adapter |
| `valentinfrlch/ha-llmvision` | Apache-2.0 shown in repository | Product ideas for visual event summaries, review and notification workflows | Implement standalone workflows; HA integration not a dependency |
| `blakeblackshear/frigate` | MIT in reviewed core licence | Event review and generative-summary design ideas | No Frigate runtime needed for direct Blink clip analysis |
| `BitWise-0x/homebridge-blink-security` | GPL v3 text in reviewed LICENSE | Live-session lifecycle and capability documentation | Research only by default; do not transplant implementation |
| `roger-/blinkbridge` | No licence file visible in reviewed root | Clips-to-stream interoperability concept | Do not copy code without a verified licence/permission |
| Home Assistant Blink integration | Documentation reference | Health/capability UX and integration cautions | No full HA deployment required |
| `MattTW/BlinkMonitorProtocol` | Not independently audited in this package | Historical reverse-engineering reference | Non-authoritative; no unverified endpoints or code reuse |

Sources: [R1](15_SOURCES_AND_VERSIONING.md#r1), [R5–R10](15_SOURCES_AND_VERSIONING.md#r5).

## Why not merge the applications?

Their runtimes, storage models, UI frameworks, and auth lifecycles differ. A “mega-fork” introduces duplicated polling and credentials, multiple processes and databases, unnecessary stream reconstruction, and licence ambiguity. Our architecture uses one supported library integration and independently implements a coherent product.

`blinkbridge` synthesizes a stream from downloaded clips, holding a still frame between events. That is not a true live feed and is not needed to send a clip's frames to Ollama. [R6](15_SOURCES_AND_VERSIONING.md#r6)

Homebridge's current documentation includes cloud-polled motion and live-view handling. Those claims are useful evidence for a later proof, but they do not establish that every camera works in our implementation. [R5](15_SOURCES_AND_VERSIONING.md#r5)

## Dependency intake checklist

For each reused dependency, record repository/package name, purpose, exact release/commit, licence identifier, licence source URL, copied versus linked versus subprocess use, transitive licences, security advisories checked, and date verified. Commit the lockfiles and a dependency report. Preserve required notices in distribution. Do not claim permission solely because a repository is public.

Do not add a permissive licence to the whole product while silently incorporating differently licensed code. Leave the product's distribution licence as a deliberate owner decision. For a personal private build, keep the inventory anyway so future release decisions are not based on guesswork.

FFmpeg builds can differ in licensing depending on enabled components. Record `ffmpeg -version` and `ffmpeg -buildconf`; do not bundle an arbitrary binary without reviewing its build/licence. Prefer an existing installed binary for development. [T4](15_SOURCES_AND_VERSIONING.md#t4)

A future object detector needs separate review of **both** its implementation and its model weights. Do not automatically add an AGPL/commercial detector framework or assume a model file inherits a surrounding library's licence. The first version does not require a separate detector.

An optional, owner-approved face **detector** was added on 2026-10-07 using OpenCV YuNet; no SFace recognizer, identity embedding or enrollment is included. Exact weight provenance, optional package pins, retained wheel/model notices and advisory intake are recorded in [FACE_DETECTION.md](FACE_DETECTION.md). Model weights remain outside source. This does not clear the whole product for distribution.

## Upstream baseline and validation

Research displayed `blinkpy` release `v0.25.9`. Reviewed release notes include authentication and live-view endpoint fixes in the 0.25 series. These show why version pinning and an isolated adapter matter; they are not evidence of compatibility with this user's camera. [R2](15_SOURCES_AND_VERSIONING.md#r2)

At M0/M1, inspect the current stable release and its code. Prefer a released version. If a required fix exists only on a branch, document the issue, pin an exact commit, add regression fixtures, and mark the dependency exception. Never use floating `dev`, `main`, or `latest` references in a reproducible release.

When a repository's capabilities, licence, or supported model list changes after this package, current verified evidence wins. Update the source ledger rather than silently rewriting product guarantees.
