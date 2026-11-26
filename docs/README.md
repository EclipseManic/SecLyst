# Documentation

Seclyst is one platform with five analysis engines. These pages describe how it
is put together and how to run it.

| Page | What it covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, control plane, storage, and the security model |
| [ENGINES.md](ENGINES.md) | The five engines: what each does, where it runs, what it may contain |
| [OPERATIONS.md](OPERATIONS.md) | Running, configuring, troubleshooting, and maintaining an instance |
| [SOURCES.md](SOURCES.md) | Where the analysis data and provider integrations come from |
| [API.md](API.md) | The platform HTTP API: authentication, jobs, runs, artifacts, settings |
| [screenshots/](screenshots/) | Real captures of the running product and how to regenerate them |
| [internal/](internal/) | Historical design and delivery notes, not user documentation |

## Reading order

New to the project: the root [README](../README.md), then `ARCHITECTURE.md`, then
`ENGINES.md`.

Running it for real: `OPERATIONS.md`, and the configuration table in the root
README.

Integrating with it: `API.md`.

## Contributing to these docs

Documentation ships with the change that makes it necessary. If a page describes
behaviour that no longer exists, fixing that page is part of the fix.
