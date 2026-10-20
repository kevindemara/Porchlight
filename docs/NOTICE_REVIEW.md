# Dependency notice review - updated 2026-10-20

The four previously missing frontend notices are now retained. This resolves the specific notice gap identified in the source-release review; it does not clear arbitrary future binary/model redistribution or uninstalled platform packages.

The original review covered 66 Python versions in requirements.lock and 85 npm lock entries. Twenty-five platform-specific optional packages were absent on this Windows machine, so their installed notices were not locally verified. No dependency was installed or upgraded for this follow-up.

| Package | Locked version | Retained evidence |
|---|---|---|
| @redocly/openapi-core | 1.34.20 | MIT notice at published gitHead; matching package version metadata |
| @rolldown/binding-win32-x64-msvc | 1.2.12 | Project MIT notice at exact release; matching parent/binding metadata |
| change-case | 5.4.4 | MIT notice at exact release; matching published gitHead/version |
| uri-js-replace | 1.0.1 | Authoritative upstream MIT-0 notice for byte-identical code; see verification below |

## uri-js-replace resolution

The published 1.0.1 package declares MIT, but its published gitHead `38927505b51a74b53444dc723be10e0d2e53823c` has no standalone licence file. Checking only that commit missed the maintainer's later [merged licence addition](https://github.com/andreinwald/uri-js-replace/pull/5).

The authoritative [LICENSE at commit a34c9a5](https://github.com/andreinwald/uri-js-replace/blob/a34c9a5b7a317b6039b2b3cf9d024ee8e418d281/LICENSE) grants **MIT No Attribution (MIT-0)** and identifies Copyright 2025 andreinwald. Its exact 905 bytes are retained verbatim at [notices/frontend/uri-js-replace/LICENSE](../notices/frontend/uri-js-replace/LICENSE), SHA-256 `5caace045044f8e3dd302d2a6789b9824c1dec992a3e94cc8f75f5c81bad699e`.

Verification on 2026-10-20:

- The [upstream comparison](https://github.com/andreinwald/uri-js-replace/compare/38927505b51a74b53444dc723be10e0d2e53823c...a34c9a5b7a317b6039b2b3cf9d024ee8e418d281) changes only LICENSE, README.md and package.json.
- All **12 source/distribution Git blobs** under src/ and dist/ are identical between the published commit and the licensed commit.
- All **eight installed dist files** match their upstream Git blob IDs byte-for-byte. Individual SHA-256 hashes, sizes and Git IDs are recorded in [NOTICE_SOURCES.json](NOTICE_SOURCES.json).
- The retained grant applies to that verified unchanged code. This record distinguishes the package's older MIT metadata from the verified upstream MIT-0 grant; it does not pretend the original npm archive contained this notice.

No generic licence template was substituted, no code was copied into Porchlight, and no package/version/lockfile changed. Other packages keep their own notices. FFmpeg executables and model weights remain outside the repository and need separate review if bundled later. Porchlight original code/documentation use the owner-selected [MIT licence](../LICENSE).
