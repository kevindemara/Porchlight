# 08 · UI/UX specification

## Direction

A calm, polished consumer camera app, not a technical admin dashboard. Working title **Porchlight**. Use original UI, icons and styling. Do not reproduce Blink logos, proprietary graphics or identical screen layouts. Light and dark themes should both be intentional.

Suggested visual direction: neutral warm backgrounds, ink-coloured text, a restrained amber accent for activity, and a separate semantic colour system for warning/error/success. Use system/local fonts, consistent spacing, 12–16 px corner radii, subtle borders and minimal animation. Camera imagery is the focus. No giant hero banner, marketing page, distracting gradients, fake analytics or decorative charts.

Mobile bottom navigation: **Cameras · Live view · Library · Activity · Search · Settings**. Desktop uses a compact sidebar with the same destinations. The owner requested Live view as its own navigation tab and a library for explicit live captures. Diagnostics is accessible from Settings and a status indicator; it should not dominate normal monitoring.

## Setup wizard

Pages: Welcome/privacy boundary; local owner creation; storage location/space; Blink local sign-in and challenge; discovered cameras and recording source; no-plan verification status; Ollama local-model test; notification permissions; final readiness summary.

Allow safe independent steps when Blink login is incomplete. Demo mode has a persistent banner and separate data source. “Skip for now” cannot convert a failed compatibility check into success. Never show password/code fields in screenshots captured for cloud-based coding assistance.

Ollama model picker shows local vision support, digest/size when available, test outcome and workload preset. A text-only model is disabled for image analysis with an explanation. Any model download is explicit, with source and disk estimate. Never ask for an OpenAI or other paid API key.

## Cameras screen

Group by network, with observed Armed/Disarmed/Unknown state and a deliberate toggle. Each card has camera label, 16:9 preview, capture age, battery/status when available, latest event summary, and actions. Labels distinguish **Snapshot**, **Recorded clip**, and **Live**.

Cards never animate a still image to imply streaming. “Last checked” and “image captured” are different times. Camera cards focus on saved recordings; Live view is accessed from its own navigation tab.

## Live view screen

Use a compact heading, a labelled camera selector and an inline player. Opening the tab or selecting a camera never starts streaming automatically. Require **Start live view**; retain Stop, fullscreen, freshness overlays and bounded session controls. Show Record/Snapshot beside the main controls directly under the video and inside fullscreen. Record requires an explicit action and a visible recording indicator; stop/session cleanup finalizes it to Library. Snapshot captures the displayed fresh frame. Switching cameras or leaving the tab cleans up the current session, including a start request that completes after navigation. Unsupported cameras show a concise reason and a link to saved recordings; a disconnected account has a setup link. Keep all six navigation destinations usable on phones.

## Library screen

Show local live recordings and snapshots with protected video playback/image viewing, camera labels, save time, duration for videos and download actions. Distinguish recording/saving/ready/failed captures. Empty Library directs the owner to Live view; no automatic capture or AI analysis begins by visiting either page. Activity remains the separate archive of Blink recordings/manual imports.

A failed command stays visibly failed. An accepted command shows pending until read-back. Disarming should require confirmation in the UI; a snooze action must never disarm hardware. Avoid accidentally hiding this distinction inside an unlabeled icon.

## Activity screen

Newest-first, date-grouped cards ordered by recording time, falling back to discovery/import time when recording time is unknown. Use the same ordering for cursor pagination, with a stable ID tie-breaker. Include camera, capture time, duration, thumbnail, safe summary, object chips, favourite, and analysis status. Show a coverage-gap band if monitoring/retrieval was interrupted. Filters: cameras, date range, category, colour, favourites, imported versus camera source, pending/failed AI.

Virtualize long histories and use cursor pagination. Empty states distinguish “no matches,” “no clips imported yet,” “source unavailable,” and “AI still processing.” Do not call an unanalyzed clip unimportant.

## Event detail

Original clip player; timestamp and camera; AI-generated label; safe summary; evidence-frame strip in chronological order; uncertainty; model/prompt revision behind an advanced disclosure; notes/favourite; download and local delete.

Provide “Description is wrong” feedback with editable category/colour/action corrections. Keep raw model interpretation separate from user-corrected data. Reanalyze is explicit and shows queue progress. A deletion confirmation names which local files/derived records will be removed and states that Blink's copy is untouched.

Muted playback by default. Audio is not automatically transcribed or fed to AI. Exports indicate whether they are original or altered/masked. Avoid public share links in version one.

## Search screen

Start with a clear text box and filter controls. Example hints such as “vehicles yesterday” are search examples, not claims of recorded events. AI-assisted interpretation displays chips for camera/date/category/colour before search, with editable bounds and timezone. Invalid interpretation falls back to literal full-text search.

Search results link to event evidence. “No white cars found” should read as a result among indexed observations, not proof no white car passed. Unknown/unanalysed coverage should be visible.

## Rules and notifications

Natural-language-looking rule builder backed by a structured schema: “For [cameras], when [category], during [schedule], send [notification].” Advanced directions/colour filters show evidence requirements. Unknown events are not silently suppressed by default.

Separate three settings: recording/motion configuration on Blink; Porchlight AI analysis; Porchlight notification delivery. Quiet hours and snooze affect only the last unless explicitly stated otherwise. Test notification is labelled as a test.

Privacy-first lock-screen setting defaults to generic activity text. The owner can choose descriptive text. A notification click opens the authenticated event view, not an unprotected media URL. Display paired devices and a Revoke action.

## Settings and health

Sections: account/integration; camera names/grouping; AI model/workload; notifications; local storage/retention; backup/restore instructions; privacy/access; experimental features; diagnostics/about/licences.

Diagnostics has independent rows for Blink auth, inventory, clip listing, clip download, AI, worker, disk, and push. Show last success, current state, safe error, and action. Never render all-green health because `/health/live` responds.

## Accessibility and responsive acceptance

Test at 360, 390, 768 and 1440 px widths. Aim for at least 44 px touch targets, visible focus, readable labels, adequate contrast, keyboard-operable filters/dialogs, and reduced-motion respect. Status requires words/icons as well as colour. Use live regions sparingly for background completion; do not announce every poll.

Fullscreen/event dialogs return focus correctly and close with Escape. Confirmations have an obvious cancel action. No automatic live-view start, autoplay audio, endless spinner, or horizontal overflow on phones. Keep usable error/loading/offline states as polished as the success state.
