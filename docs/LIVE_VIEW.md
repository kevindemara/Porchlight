# Experimental live view

The owner requested streaming ahead of the original M7 schedule. Open **Live view** in the sidebar or phone navigation, choose a camera and select **Start live view**. Opening the tab or changing cameras does not start streaming automatically. Switching cameras or leaving Live view stops the current stream, including a start request that finishes after navigation. Live view depends on Blink's internet service and uses camera battery. There is one active player and a 90-second session cap. Owner-triggered local recordings, snapshots and listening to available camera audio are implemented; two-way talk and continuous NVR capture are not.

The owner requested removal of Porchlight's fixed one-minute precaution. A new session can start once the previous session finishes local cleanup; actual Blink throttling responses remain enforced. Cleanup allows up to three seconds for the command-done request and two seconds for the encoder to exit normally, with additional time if an active recording needs saving. This is not a guaranteed overall deadline or proof that Blink has released the camera. Blink's [Live View guide](https://support.blinkforhome.com/how-to-access-live-view?kb_language=en_US) documents session durations but does not specify a fixed reconnect interval. Its [10–60-second Retrigger Time](https://support.blinkforhome.com/en_GB/motion-detection/what-is-the-retrigger-time-is-this-configurable) applies to motion recordings.

Select **Fullscreen** at the top right of the live video to expand it. **Exit fullscreen** returns to the Live view page; **Stop live view** remains available in fullscreen. The same stream, freshness overlay and time limit continue during fullscreen. Unsupported or rejected fullscreen requests show a local explanation. Fullscreen was tested in desktop Edge at phone/tablet viewport sizes; actual Android/iOS browser support remains unverified.

**Play** is a playback fallback, shown only when an active session has loaded video that is paused (for example, when autoplay requires a user gesture). It resumes the current player without opening another Blink session and disappears while video is playing. **Start live view** remains the action for opening a new session.

Live playback starts muted. When the encoded stream includes audio, select **Unmute** and use the volume slider to listen; these controls also appear in fullscreen. A stream without audio continues playing video and explicitly reports that no audio track was supplied. The first available audio track is encoded locally as AAC-LC, mono, 16 kHz, at a configured 64 kbit/s. The protected media response declares the codecs observed in the encoder initialization header, so video-only streams remain playable. No microphone permission, new installation or remote audio processing is required. Audio is not transcribed or analyzed by AI.

Porchlight uses the pinned blinkpy API/protocol helpers with complete packet reads and verified TLS. Existing FFmpeg converts MPEG-TS into bounded H.264 fragmented MP4 through memory pipes. The browser uses MediaSource. Desktop Edge/Chrome are the tested engine family; phone viewport tests in Edge do not prove native iOS/Safari compatibility. No dependency, encoder download or service was added; existing FFmpeg/libx264 licensing is recorded with the separate installation. Binaries are not bundled.

LIVE requires advancing decoded timestamps and fresh server media. Frozen or ended video is covered. Stop, close, sign-out, account reconnect, expiry, backgrounding and lost heartbeats clean up the session. Bytes, backpressure and time are bounded; no automatic camera restarts. Upstream command completion is attempted on cleanup, but a network outage may prevent acknowledgement. Camera-state changes are not reported as confirmed without evidence.

Control routes require owner authentication and CSRF; status/media are restricted to the initiating browser session. Relay addresses, connection IDs, serials and protocol bodies stay in the backend. Live video is saved only after an explicit Record or Snapshot action and is not sent to AI. FFmpeg receives pipes or validated local files with network media protocols disabled; private stderr is discarded. Tests/screenshots use generated video.

## Recordings and snapshots

While fresh video is playing, select **Record** to save the received video and any available camera audio locally. Muting playback does not mute the saved recording. Select **Stop recording** to finish without ending live view. Ending the live session, switching cameras or navigating away also finishes any active recording. No footage preceding the action is retained: recording begins with the next complete encoded video segment. Very short attempts with no complete segment show a failure rather than a playable placeholder. The existing 90-second live-session and 32-MiB stream limits still apply.

Select **Snapshot** to save a JPEG of the displayed video frame. It is independent of recording; paused/stale video cannot be captured through these controls. The browser sends the JPEG only to the authenticated local app, which validates dimensions and decodes/re-encodes it to remove metadata. Maximum input is 2 MiB, 4096 pixels per edge and 4,194,304 pixels total; snapshots are limited to one per second.

Open **Activity** to play video, view images or download MP4/JPEG captures. Use All / Recordings / Snapshots and expand a saved capture. Entries are labelled local live recordings/snapshots, with the camera and local button/save time, not a claimed Blink camera timestamp. They share the timeline with cloud/Sync Module recordings and manual imports while preserving separate source and storage contracts. This does not establish subscription-free automatic recording compatibility.

Capture files are under the private data profile's `media/live-library/`; database migration `0005` tracks recording/saving/ready/failed state, dimensions, duration and hashes. Complete segments are flushed to a staging file only after Record. Finalization normalizes/remuxes and decodes the MP4 before marking it ready. Interrupted recording/snapshot finalization is recovered at startup. Failed captures remain visibly failed; partial files are retained outside source control. Capture routes and thumbnails require authentication, including Range/HEAD; state changes additionally require CSRF and live-session ownership. Disk reserve/archive budget checks apply before capture. Automatic AI, automatic deletion and capture sharing are not enabled.

The orange play button in the idle/ended player uses the same start action as **Start live view**, which remains below the video. Both share the busy state; the central button disappears during an active session, including while waiting for fresh frames. The camera name remains in the player heading without the Experimental live view label.

## Relay certificate review

The actual doorbell probe reached a Blink-selected relay whose certificate was self-signed. Verified TLS rejected it before any video arrived. Certificate inspection sends no protocol/authentication data. Only the SHA-256 fingerprint is presented for review; it is not independent authentication by a public certificate authority.

**Trust this certificate for Porchlight** explicitly stores the exact observed certificate in Porchlight's private profile, not Windows' certificate store. Connections retain TLS chain/time checks against the approved certificate and compare the exact fingerprint before sending protocol data. Changed or unapproved certificates require a new review. Public-CA certificates follow normal verification with Blink DNS identity checks. `AGENTS.md` requires approval/local action before trusting certificates; wanting live view does not implicitly approve this trust change.

Settings → Diagnostics → **Reset live relay trust** ends live view and revokes these approvals while preserving saved recordings. Retry after approval and cleanup of the previous session. No certificate is trusted automatically.

## Verification

On 2026-10-08, a bounded native probe of the owner's current Blink relay found AAC audio in local memory. No private media was saved or exposed to coding tools. A second encoder probe reported `audio_status=available`, 66,807 encoded bytes in 3.59 seconds and 0.06 seconds of cleanup. These establish track availability and encoding, not audible quality or real browser playback. Generated video plus a sine tone verifies retained, decodable, non-silent audio in saved MP4 captures. Browser fixtures verify muted startup, unmute/mute, volume, fullscreen controls and video-only fallback at desktop and phone widths. The owner still needs to listen on their actual browser/device. Previously saved video-only live recordings cannot regain missing audio; imported Blink clips retain their original audio, and manual archive/capture playback now uses normal audible browser controls.

On 2026-10-08, two owner-authorized short native reconnect probes each received fragmented MP4 in the first session but no video in the immediately following session. Measured local cleanup was 0.06 and 0.08 seconds without an active recording. Status-only diagnostics identified HTTP 404 from the same command-done endpoint used by blinkpy 0.25.9; no remote release acknowledgement was obtained. This does not establish a required Blink cooldown or guarantee immediate reconnect. Private imagery stayed in native memory and no footage was saved or passed to coding tools. Synthetic tests additionally verify serialized reconnect, cleanup after upstream EOF, old-consumer isolation and encoder output draining; browser fixtures do not establish hardware playback.

Tests cover relay rejection, fragmented packets, TLS chain/identity gates, credential-free certificate inspection, explicit CSRF-protected approval/revocation, session ownership, expiry, revocation, bounded encoding and cleanup. Native FFmpeg encodes generated MPEG-TS. Browser fixtures decode generated fragmented MP4, verify fresh-frame gating, certificate review and close cleanup. These are not camera-compatibility evidence.

The owner explicitly approved certificate fingerprint `b1bfa71ba445f0de14172a1382db19e8848f93b850eb78bd13fdabc1be7e2481` for Porchlight only. A subsequent native probe against the existing doorbell successfully received an encoded fragmented-MP4 sample: 66,328 bytes in 5.44 seconds, with state `receiving`. The probe exited successfully and cleaned up without saving imagery. This verifies the hardware relay/encoder path; actual camera playback in the owner's browser remains **NOT RUN**. Windows certificate trust was unchanged.

The short hardware probe uses the saved owner-authorized Blink session and emits only sanitized counts/timing/status. Stop the ordinary app first; the probe acquires the same profile lock:

```powershell
.\stop.ps1
.\.venv\Scripts\python.exe scripts\probe-live.py
.\start.ps1
```

It stops after an encoded video sample or a bounded failure, saves no imagery, and does not verify browser playback. Its `--approve-certificate <SHA-256>` option is an explicit trust action for an exact matching current review candidate; use only with owner approval. Otherwise trust stays unchanged. Live view remains experimental until the owner verifies current pictures and cleanup locally.

Primary references: [blinkpy releases](https://github.com/fronzbot/blinkpy/releases), [upstream partial-read report](https://github.com/fronzbot/blinkpy/issues/1299), [MediaSource appendBuffer](https://developer.mozilla.org/en-US/docs/Web/API/SourceBuffer/appendBuffer).
