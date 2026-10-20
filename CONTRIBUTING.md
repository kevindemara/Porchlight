# Contributing to Porchlight

Start with README, AGENTS.md and the architecture/compatibility contracts in docs. Keep changes small, preserve local-only inference and use synthetic fixtures. Do not introduce a required subscription, cloud AI fallback or public Ollama access.

Run `test.ps1 -Browser` in the prepared Windows environment. Add regression coverage for behavioral changes. Distinguish fixture results from actual hardware evidence and update BUILD_STATUS.md honestly. Never disable security/tests to make a change pass.

Do not submit camera footage, face samples, database files, credentials, session cookies, certificate keys, private network settings or unredacted diagnostics. Report safe error codes and dependency/application versions. Dependencies and model/native redistribution need their own licence review; Porchlight contributions are made under the project's MIT licence.
