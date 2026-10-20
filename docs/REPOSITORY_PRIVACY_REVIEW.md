# Repository privacy review · 2026-10-20

The owner requested a source and history review before public release. The repository is still **private**. Personal HTTPS/DNS/router settings, desktop launch configuration, credentials, certificate keys, recordings, face templates, databases and detailed native reports belong outside the checkout.

## Scope and findings

After fetching all configured remotes/tags, the initial scan reviewed 508 tracked files and 607 unique blobs reachable from all local refs across five commits. It checked the working tree and historical content for private-key headers, common provider-token shapes, DPAPI blobs, credential literals, Windows profile paths and privately supplied personal hostname/network/email/runtime identifiers. The final staged working tree contains 514 files; it was rechecked before commit with no current-content matches and the same four historical path findings. See build status for the final run.

- No matching private keys, provider credentials, DPAPI blobs, personal domain, reviewed personal LAN addresses or personal email were detected.
- Binary paths were the known Porchlight brand/logomark/icon assets. No tracked camera video, audio, database, certificate or runtime archive was found.
- Four path matches occur in **two historical versions of BUILD_STATUS.md**. They are old local machine/tool paths, not credentials. Current tracked content no longer contains those matches. Deleting a current file does not remove its history.
- Markdown was scanned as content, not excluded wholesale. Public requirements, architecture, install guides, synthetic prompts, licence notices and engineering instructions are intentional repository documentation. README now describes the product rather than a personal PC configuration.

**Publication is not cleared while historical personal paths remain.** Choose reviewed history sanitization or a clean public-history release while preserving the private checkpoint. Rewriting published refs/tags is a separate destructive Git operation and has not been performed automatically. No secret rotation is indicated by these path-only findings; any subsequently discovered credential needs revocation as well as history cleanup.

## Repeat locally

Use `scripts/audit-repository.py --output <outside-checkout-report.json>`. Optionally supply `--private-patterns <outside-checkout-patterns.json>` containing category-to-regex mappings. The scanner prints only counts/categories and binary paths; its detailed report contains file/blob/line locations, never matching values. Reports still belong outside the repository.

This is a pattern-based review, not a promise that every secret format can be detected. Unreachable objects, remote-only refs not fetched, GitHub issues/discussions, release attachments, Actions artifacts/caches and collaborators' clones are outside this scan. Review any such publication surfaces separately. Commit author metadata is intentionally separate from file-content scanning; inspect it before publication if you do not want your configured Git author identity public.

The ignore rules protect common runtime/media/backup/key paths from accidental new additions; they cannot hide files already tracked or historical blobs. Review the staged diff before every push and avoid `git add -f` on private files. Keep the existing private checkpoints until the owner approves the publication plan.
