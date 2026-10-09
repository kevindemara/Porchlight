# Archive, cleanup and recovery

Activity sorts by recording time, with discovery time clearly marked when recording time is unknown. Filters include camera, source, analysis state, category, colour, direction, date interval, daypart and favourites. AI category/colour/direction filters use the latest accepted revision and match one entity. Ordinary text search uses literal substring matching in descriptions and notes and works without Ollama. Three-or-more-character searches use SQLite FTS5 trigram indexing; shorter queries preserve literal matching. User input does not become SQL or FTS operators. Natural-language search proposes bounded filters locally; review the resolved timezone/date interval before Apply. Daily digest counts cover saved recordings, with explicit analysis and retrieval coverage limits.

Recording details show the neutral AI description, uncertainty, structured observations and sampled moments. Your description preserves the original AI revision. Camera names/groups are local metadata. Delete requires confirmation and removes local notes, analyses and pending notifications with the event. Shared bytes remain until their last reference is removed. Minimal source tombstones prevent automated re-download of locally deleted Blink clips. Blink copies and exported files remain separate.

Live captures appear alongside archived clips in Activity with distinct source labels. Use All / Recordings / Snapshots to filter the whole timeline. Expand a finished capture to play/view it, mark it favourite, download it or explicitly delete it. Their storage contracts remain separate, and capturing does not enable AI automatically.

## Optional local cleanup

Cleanup starts **off**. Settings → Storage → Local archive shows the age policy, archive budget and free-space reserve. Save settings applies budget/reserve changes. Preview local cleanup lists the eligible recording/capture counts, estimated reclaimed original bytes, favourites and active work. Choose Cancel, a one-time deletion or deletion plus automatic cleanup. The preview expires after five minutes, is single-use and must still match the archive/settings when applied.

Age uses the recording timestamp when available, discovery time otherwise, and saved time for Library captures. Favourites and running analysis/capture work are protected. The automatic worker processes at most 100 events and 100 captures per minute. It only runs after a confirmed policy. Pause it before changing the age policy. Restored backups always disable cleanup.

Budget pressure pauses saving; it does not automatically delete recent clips or favourites. Reserve and budget checks cover catalogued Activity originals and Library captures. Derived thumbnails and incomplete scratch files also occupy disk, so catalogued sizes are not a filesystem-wide measurement. Windows playback handles can defer physical deletion; the journal retries after handles close. No route deletes cloud or camera copies.

## Local backup and restore

Stop Porchlight first. Choose local destinations outside the repository, active profile, OneDrive and network shares. These scripts do not register services or overwrite an existing profile.

```powershell
.\stop.ps1
.\backup.ps1 -Destination 'C:\PorchlightBackups\2026-10-07'
.\start.ps1

# Verify and preview a restore; destination must not exist.
.\restore.ps1 -Backup 'C:\PorchlightBackups\2026-10-07' -Destination 'C:\PorchlightRestored'
# Explicitly create the reviewed new destination.
.\restore.ps1 -Backup 'C:\PorchlightBackups\2026-10-07' -Destination 'C:\PorchlightRestored' -Apply
```

Backups contain a consistent SQLite snapshot, notes, accepted analyses, referenced original MP4/JPEG assets and completed Library captures, with a file/checksum manifest. They contain private personal data and are not additionally encrypted by Porchlight. Credentials, browser sessions, push keys/subscriptions/delivery state, live relay trust, pending camera commands, local manifest/transfer protocol intents, tools and models are excluded. Incomplete capture files are excluded. Thumbnail caches regenerate locally.

Restore checks hashes, path containment, schema, foreign keys and database integrity before creating a new profile. It preserves the local login password hash; sign in with that profile's username/password. It pauses sync, queued jobs, notification rules, automatic AI and cleanup. Reconnect Blink and review all settings before resuming. Previous notifications are not replayed. Failed staging can be inspected manually; it does not replace the existing archive.

To inspect the restored workspace, stop the regular app and use a separate PowerShell session:

```powershell
$env:PORCHLIGHT_DATA_ROOT = 'C:\PorchlightRestored'
.\start.ps1
```

Run only one app per profile. To return to the original profile, stop the restored app and remove the override in that shell before starting. Keep the backup until playback, annotations and expected counts have been checked.

## Historical provenance and ephemeral evidence

On restore, Blink-origin events are labelled historical, all discovery/history scans are disabled, queued automation is paused and the bounded UI invalidation log is cleared. Restored footage cannot create fresh-alert storms. Manual imports retain their original provenance. Schema0014–0016 are migrated normally under the profile lock; old backup schemas are supported before migration.

Evidence-strip JPEGs are generated on request, checksum-verified and never persisted, so they add no archive/backup/cleanup storage. Older analyses still offer sampled moments when their extraction version cannot recreate an exact image. Original and accepted metadata remain the backup source of truth. Activity object chips use owner labels when supplied, otherwise the latest accepted analysis. Owner corrections preserve all AI revisions and survive backup/restore.


## Correcting object observations

Open a recording and select **Description is wrong · correct object labels**. Edit the whole set of objects: category/type, colour, action and direction. Use Unknown when unsure. **Save object labels** updates the archive's filters/chips/digest and searchable label wording. It does not mark an unanalyzed recording as analyzed or send a new alert. Removing all objects saves an explicit empty set; **Use original AI labels** clears the override. The original AI description, revision and evidence remain available. A conflict from another view requires reloading the labels before saving. Notes and the separate free-text description stay editable.

Large loaded histories use measured visible rows rather than mounting every card. Load more still uses recording-time cursors. Tab/Shift+Tab reaches offscreen recordings; closing a detail view returns focus. Reviewing an older row preserves loaded pages. New imports/filter changes start a new listing as expected.
