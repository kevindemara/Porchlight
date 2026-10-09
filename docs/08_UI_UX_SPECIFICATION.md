# 08 · UI/UX specification

## Direction

A calm, polished consumer camera app, not a technical admin dashboard. Working title **Porchlight**. Use original UI, icons and styling. Do not reproduce Blink logos, proprietary graphics or identical screen layouts. Light and dark themes should both be intentional.

Suggested visual direction: neutral warm backgrounds, ink-coloured text, a restrained amber accent for activity, and a separate semantic colour system for warning/error/success. Use system/local fonts, consistent spacing, 12–16 px corner radii, subtle borders and minimal animation. Camera imagery is the focus. No giant hero banner, marketing page, distracting gradients, fake analytics or decorative charts.

Mobile bottom navigation and desktop sidebar: **Live View · Activity · Faces · Settings**, in that order. Activity holds Blink clips, manual imports and explicit live captures, with an **All / Recordings / Snapshots** selector and clear source labels. Live View includes **Manage cameras** for inventory, names, grouping and device controls. Diagnostics is accessible from Settings; it should not dominate normal monitoring. Older Cameras and Library bookmarks resolve to Live View camera management and Activity respectively.

The authenticated workspace has no separate top bar. Desktop Notifications and Sign out sit above the sidebar's Local workspace badge. On phones, compact 44 px actions sit beside the page title while the four primary destinations remain in bottom navigation. Do not duplicate the local status badge or add a tagline above camera content. Page headings start with their title, without a YOUR WORKSPACE eyebrow.

## Setup wizard

Pages: Welcome/privacy boundary; local owner creation; storage location/space; Blink local sign-in and challenge; discovered cameras and recording source; no-plan verification status; Ollama local-model test; notification permissions; final readiness summary.

Allow safe independent steps when Blink login is incomplete. Demo mode has a persistent banner and separate data source. “Skip for now” cannot convert a failed compatibility check into success. Never show password/code fields in screenshots captured for cloud-based coding assistance.

Ollama model picker shows local vision support, digest/size when available, test outcome and workload preset. A text-only model is disabled for image analysis with an explanation. Any model download is explicit, with source and disk estimate. Never ask for an OpenAI or other paid API key.

## Camera management in Live View

Group by network, with observed Armed/Disarmed/Unknown state and a deliberate toggle. Each card has camera label, 16:9 preview, capture age, battery/status when available, latest event summary, and actions. Labels distinguish **Snapshot**, **Recorded clip**, and **Live**.

Cards never animate a still image to imply streaming. “Last checked” and “image captured” are different times. Camera cards focus on saved recordings inside the Manage cameras disclosure. A compact **Network · Armed/Disarmed/Unknown** button sits beside Manage cameras and opens the selected network's controls in a modal. The full network explanation and arm/disarm controls stay inside that modal. Opening/closing it never changes Blink state or starts/stops the live session. Disarming requires deliberate confirmation and actual read-back. Escape/Close returns focus to the trigger; closing cancels an unsubmitted confirmation, while accepted commands remain durable and are checked on reopening.

## Live view screen

Start live playback muted. Enable accessible Unmute/Mute and volume controls when the encoded session supplies audio, including fullscreen; explain unavailable audio without blocking video. Record preserves available audio even while listening is muted. Saved clips use native controls and audible manual playback. No microphone or two-way talk controls are provided.

Use a compact heading, a labelled camera selector and an inline player. Opening the tab or selecting a camera never starts streaming automatically. Require **Start live view**; retain Stop, fullscreen, freshness overlays and bounded session controls. Show Record/Snapshot beside the main controls directly under the video and inside fullscreen. Record requires an explicit action and a visible recording indicator; stop/session cleanup finalizes it to Activity. Snapshot captures the displayed fresh frame. Switching cameras or leaving the tab cleans up the current session, including a start request that completes after navigation. Unsupported cameras show a concise reason and a link to saved recordings; a disconnected account has a setup link. Keep all four navigation destinations usable on phones.

The idle/ended player also offers a central orange play button using the same explicit start action and disabled/loading state as Start live view. Keep the lower Start live view button. Hide the central start button while a session connects or plays; stale frames within an active session are not a reason to create another session. The player heading shows the camera name without an Experimental live view eyebrow; compatibility limitations and actual session status remain visible.

## Live captures in Activity

Show local live recordings and snapshots alongside Blink recordings/manual imports, retaining their source and storage contracts. Expand a capture to load protected video playback/image viewing, download, favourite and confirmed deletion. Closed captures do not load players, and closing stops playback. Distinguish recording/saving/ready/failed captures. Media type, source, camera, date, literal metadata search and favourites filter both stores before global pagination. Observation/AI filters include captures only when they have matching evidence; current live captures have no AI observations. Visiting either page never starts capture or AI analysis.

A failed command stays visibly failed. An accepted command shows pending until read-back. Disarming should require confirmation in the UI; a snooze action must never disarm hardware. Avoid accidentally hiding this distinction inside an unlabeled icon.

## Activity screen

Newest-first, date-grouped cards ordered by recording time (save time for explicit live captures), falling back to discovery/import time when recording time is unknown. Use the same ordering for cursor pagination, with stable ID and source tie-breakers. Include camera, capture time, duration, thumbnail, safe summary, object chips, favourite, and analysis status. Show a coverage-gap band if monitoring/retrieval was interrupted. Filters: cameras, date range, category, colour, favourites, imported versus camera versus live-capture source, pending/failed AI.

Virtualize long histories and use cursor pagination. Empty states distinguish “no matches,” “no clips imported yet,” “source unavailable,” and “AI still processing.” Do not call an unanalyzed clip unimportant.

## Event detail

Original clip player; timestamp and camera; AI-generated label; safe summary; evidence-frame strip in chronological order; uncertainty; model/prompt revision behind an advanced disclosure; notes/favourite; download and local delete.

Provide “Description is wrong” feedback with editable category/colour/action corrections. Keep raw model interpretation separate from user-corrected data. Reanalyze is explicit and shows queue progress. A deletion confirmation names which local files/derived records will be removed and states that Blink's copy is untouched.

Muted playback by default. Audio is not automatically transcribed or fed to AI. Exports indicate whether they are original or altered/masked. Avoid public share links in version one.

## AI-assisted search in Activity

Keep text search and Favourites visible above the recordings. A compact toolbar opens Filters, AI search, Saved views or Daily digest one panel at a time. Selected tools expose expanded state and keyboard focus; hidden panels retain drafts. Removable chips keep every active filter visible when the panels are closed. Editing one field preserves the other accepted filters. Clear filters resets advanced filters while preserving literal text and Favourites; Clear all resets the full selection. Former `#search` bookmarks resolve to Activity with saved-view and recording parameters preserved. New saved-view links use `#activity`. Example hints such as “vehicles yesterday” are search examples, not claims of recorded events. AI-assisted interpretation displays chips for camera/date/category/colour before search, with editable bounds and timezone. Invalid interpretation falls back to literal full-text search.

Search results link to event evidence. “No white cars found” should read as a result among indexed observations, not proof no white car passed. Unknown/unanalysed coverage should be visible.

## Rules and notifications

The bell opens the notification inbox with read/unread, test and snooze controls. Push pairing, device management and rule editing live in Settings → Notifications. The inbox has a clear Notification settings shortcut; Settings links back to the inbox.

Natural-language-looking rule builder backed by a structured schema: “For [cameras], when [category], during [schedule], send [notification].” Advanced directions/colour filters show evidence requirements. Unknown events are not silently suppressed by default.

Separate three settings: recording/motion configuration on Blink; Porchlight AI analysis; Porchlight notification delivery. Quiet hours and snooze affect only the last unless explicitly stated otherwise. Test notification is labelled as a test.

Privacy-first lock-screen setting defaults to generic activity text. The owner can choose descriptive text. A notification click opens the authenticated event view, not an unprotected media URL. Display paired devices and a Revoke action.

## Settings and health

Sections: **Cameras & recording, AI, Storage, Notifications, Appearance, Diagnostics**. Only the selected section is visible; settings drafts remain when switching sections. Links to a specific section survive reload. The setup guide is a small action above the section navigation, labeled Review setup when cameras are connected. Save settings applies the entitlement, AI, storage and appearance draft together; connection, sync, rules and push controls retain their explicit actions.

Diagnostics has independent rows for Blink auth, inventory, clip listing, clip download, AI, worker, disk, and push. Show last success, current state, safe error, and action. Never render all-green health because `/health/live` responds.

## Accessibility and responsive acceptance

Test at 360, 390, 768 and 1440 px widths. Aim for at least 44 px touch targets, visible focus, readable labels, adequate contrast, keyboard-operable filters/dialogs, and reduced-motion respect. Status requires words/icons as well as colour. Use live regions sparingly for background completion; do not announce every poll.

Fullscreen/event dialogs return focus correctly and close with Escape. Confirmations have an obvious cancel action. No automatic live-view start, autoplay audio, endless spinner, or horizontal overflow on phones. Keep usable error/loading/offline states as polished as the success state.
