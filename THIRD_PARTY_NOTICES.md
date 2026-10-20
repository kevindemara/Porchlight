# Third-party intake

Porchlight workflows and UI are independently implemented. Porchlight's original code and documentation use the owner-approved [MIT licence](LICENSE) (2026-10-20). Third-party components retain their own licences. Exact package versions and declared licences, including transitive development dependencies, are recorded in [docs/DEPENDENCY_INVENTORY.md](docs/DEPENDENCY_INVENTORY.md). Installed package licence/notice files are preserved in `notices/`.

The [local notice review](docs/NOTICE_REVIEW.md) initially found four installed frontend build packages without standalone retained notices. All four gaps are now resolved with retained upstream notices. For uri-js-replace 1.0.1, the verified byte-identical upstream source carries an MIT-0 grant; its older npm metadata declares MIT. The exact grant and source/installed-file comparison are recorded in the review and NOTICE_SOURCES.json. Absent platform optional packages and broader native redistribution review remain separate. The intake does not claim that every lock entry's notice was verified.

blinkpy 0.25.9 is used as an MIT-licensed Python dependency. React, Vite and the other frontend packages are linked through npm; their notices are retained. FastAPI, SQLAlchemy, Alembic and the other backend packages are linked through Python; their notices are retained. Lockfiles pin the tested dependency graph. Licence metadata is an intake aid, not completed public-distribution clearance.

FFmpeg 9.0.2 Gyan essentials is a separately installed GPL-3.0-or-later executable invoked through subprocess. Its verified package, licence and build configuration remain with the local installation. No FFmpeg binary or model weight is bundled in the repository.

Home Assistant LLM Vision, Frigate and Homebridge Blink Security informed product research only. No code from those applications, blinkbridge or BlinkMonitorProtocol has been copied. The original research ledger is [docs/04_REPOSITORY_RESEARCH_AND_LICENSES.md](docs/04_REPOSITORY_RESEARCH_AND_LICENSES.md).

The 2026-10-20 OSV query returned no known matches across 155 pinned core/npm/optional-push package versions. See [DEPENDENCY_AUDIT.json](docs/DEPENDENCY_AUDIT.json). This is a point-in-time advisory result; notice verification and future redistribution review remain separate.

## Optional Web Push dependencies

`pywebpush==2.5.0` and `py-vapid==1.9.4`: MPL-2.0; `cryptography==50.0.2`: Apache-2.0 OR BSD-3-Clause; `http-ece==1.2.1`: MIT. Public PyPI release metadata and upstream API documentation reviewed 2026-10-07. Used only through optional dependency APIs, with no source copied. The owner approved installation, and a native synthetic encryption round trip passed; actual Android notification delivery was also owner-confirmed. These packages remain optional for new installations. See `requirements.push.lock` and `docs/WEB_PUSH.md`. The lock and notices apply to these optional components separately from the core environment.
