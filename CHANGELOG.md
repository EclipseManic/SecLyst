# Changelog

All notable changes to Seclyst are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-11-26

The first release. One local workbench, five analysis engines, one control plane.

### Added

- **Unified workbench.** A single React shell at `127.0.0.1:7000` with shared
  navigation, live engine health, an aggregated activity timeline, and a shared
  indicator clipboard across all five tools.
- **Five engines.** IOC Lookup, Malware Analyzer, Event Analyzer, Phishing
  Detector, and RuleForge, each served on its own loopback port and started by
  one supervisor.
- **Durable job kernel.** A SQLite WAL job queue with ordered events, worker
  leases, heartbeats, and recovery of interrupted jobs across restarts.
- **Provider broker.** Shared threat-intelligence access with a global rate
  policy, single-flight deduplication, response caching, and a circuit breaker,
  so VirusTotal calls from three engines do not compete for one quota.
- **Artifact store.** Uploads stream while hashing, one immutable object per
  SHA-256, with derivation edges and quarantine-safe downloads.
- **Authentication.** A first-run password gate with a persisted session, and a
  per-launch access token guarding every engine port.
- **Central settings.** Provider keys and engine configuration managed in one
  place, with OS keyring storage as an alternative to `.env`.
- **Email intake.** Mail-to-detection intake feeding the phishing pipeline.

### Changed

- The repository is presented as one product rather than five imported tools:
  a single dependency manifest, a single license, one set of documentation, and
  one CI pipeline.
- Engine documentation is consolidated into `docs/ENGINES.md`.
- Lint scope is declared in `pyproject.toml` so the platform code is gated
  instead of the copied engine internals.

### Security

- Every listener binds to loopback.
- Engine ports reject requests that do not carry the workspace access token.
- Active scanning, URL fetching, public submission, and webhooks are off by
  default.

[Unreleased]: https://github.com/EclipseManic/SecLyst/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EclipseManic/SecLyst/releases/tag/v0.1.0
