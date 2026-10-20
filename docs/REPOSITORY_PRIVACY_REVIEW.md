# Repository privacy review - updated 2026-10-20

The repository remains **private**. The owner authorized removal of the previously identified machine paths from Git history. That cleanup is now applied to published main and all three existing checkpoint tags, with verified backup and fresh-clone checks.

## Completed history cleanup

- The original review found four local tool-path references in two old BUILD_STATUS.md blobs. No matching credentials, keys, DPAPI blobs or privately supplied personal hostname/LAN/email/runtime identifiers were detected.
- A full original Git bundle was preserved outside the checkout. A separate bare restoration from that bundle reproduced the original main commit and passed Git fsck; the backup was never pushed.
- Seven commits were rebuilt with only those four path references replaced by a generic placeholder. Author/committer metadata, messages, ancestry structure and tag annotations were preserved. All three checkpoint tag names remain; their objects and target commit IDs changed.
- Every old/new commit tree was compared: only the affected BUILD_STATUS.md versions changed. The latest tree was byte-identical before and after the rewrite, so application code and runtime configuration were unchanged.
- The four published refs (main and three annotated tags) were updated atomically with explicit force-with-lease expectations. The active checkout was aligned without replacing working files. Old local reflogs were expired and unreachable original objects pruned only after backup verification; Git fsck passed.
- A **fresh clone from GitHub** contained 514 tracked files and 638 reachable historical blobs, with **zero findings** for all checked patterns. The staged notice/documentation follow-up contains 515 files; its local review also returned zero findings before commit.

Before cleanup, author metadata used one GitHub noreply identity. GitHub inspection found no pull requests, forks or releases. The earlier failed hosted-check record remains an account-infrastructure observation, not installation evidence.

## Scope and remaining limits

The local scanner covers tracked working content and all objects reachable through local refs after fetching. Markdown was inspected as content: public specifications, installation guides, synthetic prompts, engineering status and licence notices are intentional project documentation. Known binaries are brand/logomark/icon assets; camera recordings, databases, vaults, backups, certificate keys and personal network configuration stay outside Git.

Rewriting refs does not prove deletion of GitHub's cached objects or copies in someone else's clone. [GitHub documents those limits](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). The removed items were paths, not credentials; no secret rotation is indicated by these findings. Other existing clones should be replaced with a fresh clone before contributing. Do not merge or push the old history, including the quarantined private backup.

This is a pattern-based review, not a guarantee for unknown secret formats. GitHub caches, uninspected account surfaces and other users' copies are outside local erasure guarantees. New credentials discovered later require revocation as well as cleanup.

## Repeat locally

Run `scripts/audit-repository.py --output <outside-checkout-report.json>`. Optional `--private-patterns <outside-checkout-patterns.json>` accepts category-to-regex mappings. Counts/categories and file/blob/line locations are reported without matched values. Keep private pattern inputs and detailed reports outside the checkout.

Ignore rules prevent common accidental additions; they cannot hide tracked or historical content. Review staged diffs, avoid forcing ignored private files into Git, and repeat the review before publication. Remaining clean-install, reliability and device gates are in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
