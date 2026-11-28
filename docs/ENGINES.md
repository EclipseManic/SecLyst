# Engines

Seclyst is one platform. The five analysis engines are internal components of
it, not separate products. They have no user interface of their own, no
independent release, and no separate install: the platform starts them, owns
their data directory, and serves every screen they appear on.

This page is the reference for what each engine does, where it runs, and what it
is allowed to contain.

## How an engine runs

`seclyst_backend/server.py` holds the supervisor. At startup it starts one child process
per engine:

| Engine | Id | Port variable | Default port | Data directory |
| --- | --- | --- | --- | --- |
| Malware Analyzer | `malware` | `SECLYST_MALWARE_PORT` | 7101 | `data/malware/` |
| IOC Lookup | `ioc` | `SECLYST_IOC_PORT` | 7102 | `data/ioc/` |
| Event Analyzer | `events` | `SECLYST_EVENTS_PORT` | 7103 | `data/events/` |
| Phishing Detector | `phishing` | `SECLYST_PHISHING_PORT` | 7104 | `data/phishing/` |
| RuleForge | `ruleforge` | `SECLYST_RULEFORGE_PORT` | 7105 | `data/ruleforge/` |

Each child is started as `python run.py` with `cwd=engines/<id>`, a private
environment, and a loopback port. The supervisor considers an engine online when
`GET /api/health` answers. Standard output goes to `data/logs/<id>.log`.

Every engine receives the same platform contract:

- **Access control.** Requests must carry the workspace access token in
  `X-SecLyst-Access` or the `seclyst_access` cookie. Without it the engine
  answers 403.
- **Job reporting.** When durable jobs are enabled, an engine registers its work
  with the control plane and reports progress, completion, and failure through
  `seclyst_backend/integration/client.py`.
- **Provider brokering.** When the provider broker is enabled, engine API keys
  are held by the platform and requests are proxied through it, so keys never
  live in engine configuration.
- **Platform-owned storage.** An engine writes only inside its data directory.
  Scan history, uploads, and caches are the platform's runtime data.

## What an engine may contain

An engine directory holds analysis code and its tests. Nothing else.

Allowed: Python modules, bundled reference data (rule packs, corpora), and the
engine's own test suite.

Not allowed: a README, a requirements file, a license, screenshots, a logo, a
configuration template, a second frontend, or its own `pyproject.toml` metadata
for a separate product. Those belong to the platform and live at the repository
root.

Two exceptions exist today and both are deliberate:

- `engines/<id>/run.py` is the entrypoint the supervisor spawns.
- `engines/ioc/pyproject.toml` carries the pytest configuration the IOC test
  suite needs when it runs from its own directory.

## Malware Analyzer

**Id** `malware` · **Code** `engines/malware/`

Static, threat-intelligence, sandbox, and YARA analysis of suspicious payloads.

- Executable and document structure: PE, ELF, Mach-O, Office, PDF, archives.
- Bundled YARA corpus plus import and capability flagging.
- Optional cloud enrichment through VirusTotal, Hybrid Analysis, Triage, and
  FileScan. Submission of unknown samples is off by default.
- Interactive process and indicator reporting in the platform UI.

Key libraries: `yara-python`, `pefile`, `lief`, `oletools`, `pyzipper`,
`pdfminer.six`, `androguard`.

Collection endpoint used by the dashboard: `GET /api/scans`.

## IOC Lookup

**Id** `ioc` · **Code** `engines/ioc/`

Multi-provider indicator enrichment and investigation.

- Correlates IPs, domains, hashes, URLs, wallets, phone numbers, and breached
  credentials.
- Consensus scoring across providers, with provider evidence kept alongside the
  verdict so an analyst can see what produced it.
- Relationship graph, structured exports, batch enrichment, and saved
  investigations.

Key libraries: `fastapi`, `sqlalchemy[asyncio]`, `alembic`, `aiosqlite`,
`beautifulsoup4`, `lxml`, `mmh3`, `redis`.

Database migrations live in `engines/ioc/alembic/` and run automatically when the
engine starts.

Collection endpoint used by the dashboard: `GET /api/recent`.

## Event Analyzer

**Id** `events` · **Code** `engines/events/`

Windows EVTX ingestion, search, indicator extraction, and Sigma hunting.

- Multi-file EVTX ingestion into a local SQLite index.
- Full-text search and structured filtering over parsed events.
- Sigma rule matching with ATT&CK technique tagging.
- Analyst notes, bookmarks, and report exports.

Key libraries: `evtx`, `PyYAML`, `flask`.

Collection endpoint used by the dashboard: `GET /api/investigations`.

## Phishing Detector

**Id** `phishing` · **Code** `engines/phishing/`

Email authentication, routing, content, and attachment forensics.

- Header forensics: SPF, DKIM, DMARC, ARC, and identity checks.
- Sender and lookalike-domain analysis, plus hop-by-hop routing inspection.
- URL and content analysis, including credential-harvesting patterns.
- Attachment analysis with text extraction, QR decoding, and OCR.
- Risk scoring and MITRE ATT&CK mapping.

Key libraries: `python-whois`, `pdfplumber`, `python-docx`, `pillow`, `pyzbar`,
`pytesseract`, `tldextract`, `oletools`.

Two of these need system packages on the host: `libzbar0` for `pyzbar` and
`tesseract-ocr` for `pytesseract`. Without them QR and OCR checks are skipped.

Collection endpoint used by the dashboard: `GET /api/scans?limit=20`.

## RuleForge

**Id** `ruleforge` · **Code** `engines/ruleforge/`

Cross-SIEM detection engineering with explicit translation refusals.

- Author, translate, tune, and test detection logic across supported SIEM
  dialects using a deterministic evaluation engine.
- Visual pipeline and condition editing.
- Three-valued sample evaluation, so an unknown field is never silently treated
  as false.
- Rule synthesis, linting, and version history.
- Refuses a translation it cannot make correctly instead of emitting a rule that
  looks valid and is not.

RuleForge is standard-library only. It deliberately has no third-party
dependencies so it can run inside a locked-down SOC where `pip install` is not
available. Adding a package for it is an architectural decision, not a
convenience.

Collection endpoint used by the dashboard: `GET /api/history?limit=20`.

## Adding or replacing an engine

1. Implement the engine under `engines/<id>/` with `run.py` as its entrypoint.
2. Serve `GET /api/health` and honour the access token header.
3. Add a `ToolSpec` to `seclyst_backend/server.py` with its port variable and default.
4. Add its entry to `TOOLS_REGISTRY` in `web/src/data/workspace.ts`.
5. Add its dependencies to the root `requirements.txt` under its own heading.
6. Document it on this page.

Do not add a README, a requirements file, or an interface inside the engine
directory. Those are platform files.

## Provenance

The five engines began as standalone tools and were brought in to build Seclyst.
The repository is licensed once, at the root, in [LICENSE](../LICENSE).

The IOC Lookup engine carried its own MIT license file, reading
`Copyright (c) 2026 Eclipsemanic`. That file was removed so there is one license
rather than two, and the copyright line is recorded here instead of being lost.
The other four engines were original work by the repository owner.

The screenshot folders the engines shipped with (`engines/malware/Images/`,
`engines/phishing/Images/`, `engines/events/Event_analyzer_Images/`) were removed
for the same reason: product screenshots belong to the platform and live in
[`docs/screenshots/`](screenshots/).
