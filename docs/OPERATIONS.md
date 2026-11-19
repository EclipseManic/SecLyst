# SecLyst Operations And Recovery

## Runtime

Start with `.venv/Scripts/python run.py` on Windows or `.venv/bin/python run.py` elsewhere. The FastAPI control plane migrates `runtime/seclyst.db`, recovers expired job leases as interrupted, starts the five loopback engines, and shuts them down with the parent process.

## Recovery

- Browser navigation never owns a job; reopen Runs to recover progress.
- Expired worker leases become `interrupted` and remain retryable.
- Database backups are created before schema upgrades under `runtime/backups/`.
- Set `SECLYST_DURABLE_JOBS=false` to roll back engine reporting.
- Set `SECLYST_PROVIDER_BROKER=false` to restore standalone provider access.
- Restore the newest database backup only while SecLyst is stopped.

## Credentials

Use `python -m seclyst credentials set <provider>`. Secrets are stored through the operating-system keyring with environment fallback and are never returned to browser clients.

## Storage

Artifacts are immutable objects under `runtime/artifacts/sha256/`. Referenced artifacts cannot be deleted. Provider cache metadata and request audits live in the platform database; runtime data is excluded from Git.

## Verification

Run `python scripts/verify.py` for the full standalone gate. CI runs the same platform, engine, frontend, browser, dependency-audit, migration, and launcher checks without live provider credentials.
