# Installed dependency inventory

Recorded 2026-10-06. Package metadata is an intake record; public distribution still requires the release review. Installed licence files are retained in `notices/`. The Windows lock includes development tools. FFmpeg and model weights are external and are not bundled.

Optional detector intake added 2026-10-07: `opencv-python-headless==4.14.0.94` (Apache-2.0) and `numpy==2.5.3` (BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0), installed only after specific owner approval. These are pinned separately in `requirements.faces.lock`; `record-dependencies.py` excludes them from the mandatory base lock. Exact model provenance, native-test scope, external weight location and advisory check are in [FACE_DETECTION.md](FACE_DETECTION.md). Wheel notices are retained under `notices/python/`; YuNet’s MIT notice is `notices/YUNET-LICENSE.txt`.

Notice follow-up, 2026-10-20: the uri-js-replace 1.0.1 row preserves its declared npm MIT metadata. The verified identical upstream code has a retained MIT-0 grant; see [notice review](NOTICE_REVIEW.md) and [NOTICE_SOURCES.json](NOTICE_SOURCES.json). Dependency versions are unchanged.

## Python

| Package | Exact version | Declared licence |
|---|---|---|
| aiofiles | 25.1.0 | Apache-2.0 |
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aiohttp | 3.14.4 | Apache-2.0 AND MIT |
| aiosignal | 1.4.0 | Apache 2.0 |
| alembic | 1.20.0 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| ast_serialize | 0.12.1 | MIT |
| attrs | 26.1.0 | MIT |
| blinkpy | 0.25.9 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | Unspecified |
| fastapi | 0.142.2 | MIT |
| frozenlist | 1.8.0 | Apache-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| librt | 0.16.0 | MIT |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| multidict | 6.9.1 | Apache License 2.0 |
| mypy | 2.4.0 | MIT |
| mypy_extensions | 1.1.0 | MIT |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pathspec | 1.1.1 | Unspecified |
| pluggy | 1.6.0 | MIT |
| portalocker | 4.4.0 | BSD-3-Clause |
| propcache | 0.5.4 | Apache-2.0 |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.5 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| pydantic_core | 2.46.5 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.1.1 | MIT |
| python-dateutil | 2.9.0.post0 | Dual License |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-slugify | 9.1.3 | MIT |
| pywin32 | 312 | PSF |
| referencing | 0.37.0 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| rpds-py | 2026.9.1 | MIT |
| ruff | 0.16.10 | MIT |
| setuptools | 84.0.0 | MIT |
| six | 1.17.0 | MIT |
| sortedcontainers | 2.4.0 | Apache 2.0 |
| SQLAlchemy | 2.1.3 | MIT |
| starlette | 1.7.0 | BSD-3-Clause |
| text-unidecode | 1.3 | Artistic License |
| types-jsonschema | 4.26.0.20261006 | Apache-2.0 |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.5 | Apache-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| yarl | 1.25.1 | Apache-2.0 |

## Frontend, including build/test dependencies

| Package | Exact version | Declared licence |
|---|---|---|
| @babel/code-frame | 7.29.7 | MIT |
| @babel/helper-validator-identifier | 7.29.7 | MIT |
| @oxc-project/types | 0.152.0 | MIT |
| @playwright/test | 1.63.0 | Apache-2.0 |
| @redocly/ajv | 8.11.2 | MIT |
| @redocly/config | 0.22.0 | MIT |
| @redocly/openapi-core | 1.34.20 | MIT |
| @rolldown/binding-android-arm-eabi | 1.2.12 | MIT |
| @rolldown/binding-android-arm64 | 1.2.12 | MIT |
| @rolldown/binding-darwin-arm64 | 1.2.12 | MIT |
| @rolldown/binding-darwin-x64 | 1.2.12 | MIT |
| @rolldown/binding-freebsd-x64 | 1.2.12 | MIT |
| @rolldown/binding-linux-arm-gnueabihf | 1.2.12 | MIT |
| @rolldown/binding-linux-arm64-gnu | 1.2.12 | MIT |
| @rolldown/binding-linux-arm64-musl | 1.2.12 | MIT |
| @rolldown/binding-linux-ppc64-gnu | 1.2.12 | MIT |
| @rolldown/binding-linux-s390x-gnu | 1.2.12 | MIT |
| @rolldown/binding-linux-x64-gnu | 1.2.12 | MIT |
| @rolldown/binding-linux-x64-musl | 1.2.12 | MIT |
| @rolldown/binding-openharmony-arm64 | 1.2.12 | MIT |
| @rolldown/binding-win32-arm64-msvc | 1.2.12 | MIT |
| @rolldown/binding-win32-x64-msvc | 1.2.12 | MIT |
| @rolldown/pluginutils | 1.0.1 | MIT |
| @types/node | 26.6.4 | MIT |
| @types/react | 19.3.0 | MIT |
| @types/react-dom | 19.3.0 | MIT |
| @vitejs/plugin-react | 6.1.2 | MIT |
| agent-base | 7.1.4 | MIT |
| ansi-colors | 4.1.3 | MIT |
| argparse | 2.0.1 | Python-2.0 |
| balanced-match | 1.0.2 | MIT |
| brace-expansion | 2.1.7 | MIT |
| change-case | 5.4.4 | MIT |
| colorette | 1.4.0 | MIT |
| csstype | 3.2.3 | MIT |
| debug | 4.4.3 | MIT |
| detect-libc | 2.1.2 | Apache-2.0 |
| fast-deep-equal | 3.1.3 | MIT |
| fdir | 6.5.0 | MIT |
| fsevents | 2.3.3 | MIT |
| https-proxy-agent | 7.0.6 | MIT |
| index-to-position | 1.2.0 | MIT |
| js-levenshtein | 1.1.6 | MIT |
| js-tokens | 4.0.0 | MIT |
| js-yaml | 4.3.2 | MIT |
| json-schema-traverse | 1.0.0 | MIT |
| lightningcss | 1.33.0 | MPL-2.0 |
| lightningcss-android-arm64 | 1.33.0 | MPL-2.0 |
| lightningcss-darwin-arm64 | 1.33.0 | MPL-2.0 |
| lightningcss-darwin-x64 | 1.33.0 | MPL-2.0 |
| lightningcss-freebsd-x64 | 1.33.0 | MPL-2.0 |
| lightningcss-linux-arm-gnueabihf | 1.33.0 | MPL-2.0 |
| lightningcss-linux-arm64-gnu | 1.33.0 | MPL-2.0 |
| lightningcss-linux-arm64-musl | 1.33.0 | MPL-2.0 |
| lightningcss-linux-x64-gnu | 1.33.0 | MPL-2.0 |
| lightningcss-linux-x64-musl | 1.33.0 | MPL-2.0 |
| lightningcss-win32-arm64-msvc | 1.33.0 | MPL-2.0 |
| lightningcss-win32-x64-msvc | 1.33.0 | MPL-2.0 |
| lucide-react | 1.52.0 | ISC |
| minimatch | 5.1.9 | ISC |
| ms | 2.1.3 | MIT |
| nanoid | 3.3.20 | MIT |
| openapi-typescript | 7.13.0 | MIT |
| parse-json | 8.3.0 | MIT |
| picocolors | 1.1.1 | ISC |
| picomatch | 4.0.7 | MIT |
| playwright | 1.63.0 | Apache-2.0 |
| playwright-core | 1.63.0 | Apache-2.0 |
| pluralize | 8.0.0 | MIT |
| postcss | 8.5.29 | MIT |
| react | 19.3.0 | MIT |
| react-dom | 19.3.0 | MIT |
| require-from-string | 2.0.2 | MIT |
| rolldown | 1.2.12 | MIT |
| scheduler | 0.28.0 | MIT |
| source-map-js | 1.2.2 | BSD-3-Clause |
| supports-color | 10.2.2 | MIT |
| tinyglobby | 0.2.17 | MIT |
| type-fest | 4.41.0 | (MIT OR CC0-1.0) |
| typescript | 5.9.3 | Apache-2.0 |
| undici-types | 8.9.0 | MIT |
| uri-js-replace | 1.0.1 | MIT |
| vite | 8.3.3 | MIT |
| yaml-ast-parser | 0.0.43 | Apache-2.0 |
| yargs-parser | 21.1.1 | ISC |
