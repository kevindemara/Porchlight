# Dependency notice review Â· 2026-10-07

This is a local package audit, not distribution clearance. No dependency was installed and no upstream source was copied for this review.

All 66 Python versions in `requirements.lock` match the installed environment. The npm lock contains 85 entries; 25 platform-specific optional packages are absent on this Windows machine. Those absent packages cannot be described as having locally verified notice files.

The initial audit found four installed frontend build dependencies with declared MIT metadata but no standalone licence/notice file in their installed package root or corresponding retained notice directory. Three upstream notices have since been retained, with exact-version package metadata checks and recorded SHA-256 digests:

| Package | Locked version | Current evidence |
|---|---|---|
| @redocly/openapi-core | 1.34.20 | Retained [MIT notice at published gitHead](https://github.com/Redocly/redocly-cli/blob/b563864727f1c7524021196d27bad4524f32e667/LICENSE.md); matching packages/core version metadata |
| @rolldown/binding-win32-x64-msvc | 1.2.12 | Retained [project MIT notice at exact release tag](https://github.com/rolldown/rolldown/blob/v1.2.12/LICENSE); matching parent package version and native binding MIT metadata. Full native redistribution review remains separate |
| change-case | 5.4.4 | Retained [MIT notice at exact release tag](https://github.com/blakeembrey/change-case/blob/change-case%405.4.4/LICENSE); matching published gitHead/version metadata |
| uri-js-replace | 1.0.1 | Unresolved: installed package and published gitHead tree contain no standalone notice; metadata alone is insufficient |

Downloaded notice text is preserved verbatim in the corresponding `notices/frontend/` directories. [NOTICE_SOURCES.json](NOTICE_SOURCES.json) records source URLs, version metadata paths and SHA-256 digests. No executable code was downloaded or installed. For uri-js-replace, npm publishes gitHead `38927505b51a74b53444dc723be10e0d2e53823c`; a direct GitHub tree query found no licence/notice path. Do not substitute a generic MIT template or another project's notice. Resolving that release gap needs authoritative upstream notice/permission or an approved dependency replacement.

Other discovered package notice files remain in `notices/`; this review did not reissue or remove any licence. The dependency inventory includes the lock graph, including platform entries not installed here. These retained notices do not establish public-distribution clearance.

FFmpeg and Ollama model weights remain outside the repository. Their packaging and weight licences need separate review before any redistribution. The owner selected MIT for Porchlight on 2026-10-20; the root LICENSE records that choice. The repository has private checkpoints; public distribution is still pending. The uri-js-replace published gitHead tree was rechecked on 2026-10-20 and still contains no standalone licence/notice. Do not bundle dependencies or model/native binaries as if this review cleared them. See [third-party intake](../THIRD_PARTY_NOTICES.md) and [release checklist](RELEASE_CHECKLIST.md).
