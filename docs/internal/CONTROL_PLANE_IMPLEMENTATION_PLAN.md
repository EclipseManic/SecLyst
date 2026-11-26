# SecLyst Control Plane And Workbench Implementation Plan

Status: implemented through Phase 9

Baseline repository: `EclipseManic/SecLyst`

Baseline commit: `0367103` (`Initial SecLyst security workbench`)

This plan is the implementation contract for making SecLyst a reliable local security-analysis platform. It deliberately puts runtime reliability, background work, provider coordination, caching, and recovery ahead of the new evidence-to-detection Workbench.

## 1. Goals

SecLyst must provide these guarantees:

1. Switching tools never loses a tool's current page or active progress.
2. Long-running work belongs to a durable backend job, not a browser frame.
3. Browser refresh and temporary disconnection do not lose jobs or events.
4. A SecLyst restart recovers, resumes, or explicitly marks interrupted work.
5. Shared providers such as VirusTotal have one credential, queue, quota, cache, and circuit breaker across all engines.
6. Identical concurrent requests execute once and serve multiple consumers.
7. Cache freshness and provenance are visible; provider errors are never cached as valid results.
8. Partial provider failure produces a partial result rather than erasing successful work.
9. All active work is visible in a global task center.
10. The five original interfaces remain usable and visually independent.
11. The later Workbench builds on the same jobs, artifacts, evidence, and provider services rather than creating a second runtime.

## 2. Non-Goals For The Runtime Foundation

- Multi-user collaboration, RBAC, tenancy, or remote network access.
- Enterprise SOAR remediation.
- Automatic quarantine, account disablement, firewall changes, or SIEM deployment.
- Kubernetes, Redis, Celery, RabbitMQ, or PostgreSQL in the first local release.
- Replacing the five original interfaces.
- Full STIX, CASE, OCSF, or CACAO implementations.
- AI-generated conclusions without evidence references.

## 3. Confirmed Baseline Problems

### 3.1 Frame Lifecycle

`apps/web/src/App.tsx` renders a `ToolFrame` only when its tool route is active. Navigating away unmounts the iframe and destroys its JavaScript context, DOM, route, scroll position, subscriptions, and in-memory scan ID.

The `<main>` element is also keyed by page and tab, which guarantees remounting on navigation.

### 3.2 Malware Lifecycle

`engines/malware/run.py` uses:

- In-memory `_scan_state`.
- In-memory `_scan_event_buffer`.
- In-memory cancellation IDs.
- Background threads.
- Socket.IO rooms for progress.

Completed scan reports are persisted, but live execution and event replay are not durable across an engine restart.

### 3.3 Phishing Lifecycle

`engines/phishing/run.py` stores active tasks in an in-memory `_tasks` dictionary and performs work in thread pools. A process restart loses active progress and task state.

### 3.4 IOC Lifecycle

IOC Lookup already has task IDs, SSE, caching, rate-limit metadata, retry-after parsing, provider execution states, batch progress, and persistent lookup history. These capabilities are isolated inside IOC Lookup and do not coordinate with Malware or Phishing provider traffic.

### 3.5 Event Lifecycle

Event Analyzer persists investigations and exposes progress, but its ingestion lifecycle is not represented in a platform-wide job model and is invisible outside the tool.

### 3.6 RuleForge Lifecycle

Most RuleForge operations are fast and synchronous. Dataset evaluation and corpus-scale work need platform jobs only when invoked from a SecLyst workflow.

### 3.7 Provider Isolation

Malware, IOC, and Phishing can call overlapping external providers independently. Separate rate limiters and caches cannot prevent one tool from consuming quota needed by another tool or prevent duplicate simultaneous requests.

### 3.8 Secret Scope

The current supervisor starts children from a copy of the complete process environment. This exposes every configured provider secret to every engine process. The platform process must instead own secrets and pass children only allowlisted non-secret settings plus an internal control token.

## 4. Locked Architectural Decisions

### 4.1 Platform Backend

Use FastAPI as the SecLyst control-plane API and static application server.

Reasons:

- Existing project dependencies already include FastAPI, Pydantic, SQLAlchemy, Alembic, HTTPX, and SSE-compatible primitives.
- Typed request and response contracts.
- Streaming uploads.
- Lifespan hooks for supervisor and worker startup.
- OpenAPI for engine and frontend contract tests.

### 4.2 Database

Use a separate platform database at `runtime/seclyst.db`.

Configuration:

- SQLite WAL mode.
- Foreign keys enabled.
- Busy timeout of at least 5 seconds.
- Short write transactions.
- SQLAlchemy 2.x models.
- Root-level Alembic migrations separate from IOC Lookup's migrations.

Engine databases remain independent.

### 4.3 Queue

Use a durable SQLite queue with bounded in-process workers.

Do not add Redis or Celery until there is a concrete multi-host requirement.

Workers claim jobs using a transaction, owner ID, lease expiry, and heartbeat. A process restart can detect expired leases.

### 4.4 Identifiers And Time

- UUID4 string IDs for jobs, runs, artifacts, provider calls, and detections.
- UTC timestamps only.
- Integer autoincrement IDs only for ordered event journal entries.
- Every JSON document carries a `schema_version`.

### 4.5 Engine Compatibility

Copied engines retain standalone operation.

When `SECLYST_CONTROL_URL` and `SECLYST_ENGINE_TOKEN` are present, an engine registers jobs and emits events to the control plane. When absent, the tool uses its current standalone behavior.

This is a concrete compatibility requirement because each original UI must remain directly runnable.

### 4.6 Provider Access

The platform process owns provider credentials and shared policies. Engines call named broker operations through an authenticated loopback-only internal API.

The broker never accepts arbitrary URLs from an engine.

### 4.7 Frontend State

Jobs and results are server truth. Browser storage may retain presentation preferences and the last viewed route, but never authoritative job state.

## 5. Target Package Layout

```text
Seclyst/
├── seclyst/
│   ├── app.py
│   ├── config.py
│   ├── lifespan.py
│   ├── supervisor.py
│   ├── database/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   ├── api/
│   │   ├── jobs.py
│   │   ├── providers.py
│   │   ├── artifacts.py
│   │   ├── runs.py
│   │   ├── detections.py
│   │   ├── system.py
│   │   └── internal.py
│   ├── jobs/
│   │   ├── states.py
│   │   ├── service.py
│   │   ├── queue.py
│   │   ├── worker.py
│   │   ├── events.py
│   │   └── recovery.py
│   ├── providers/
│   │   ├── broker.py
│   │   ├── policies.py
│   │   ├── credentials.py
│   │   ├── scheduler.py
│   │   ├── singleflight.py
│   │   ├── circuit_breaker.py
│   │   └── adapters/
│   ├── cache/
│   │   ├── keys.py
│   │   ├── policies.py
│   │   └── store.py
│   ├── artifacts/
│   │   ├── store.py
│   │   ├── validation.py
│   │   └── retention.py
│   ├── engines/
│   │   ├── client.py
│   │   ├── contracts.py
│   │   └── adapters/
│   ├── workflows/
│   │   ├── planner.py
│   │   ├── executor.py
│   │   └── recipes.py
│   └── exports/
├── migrations/
│   ├── env.py
│   └── versions/
├── recipes/
├── apps/web/src/features/
└── engines/
```

`seclyst/server.py` becomes a compatibility wrapper around `seclyst.app` and `seclyst.supervisor` until the migration is complete.

## 6. Job State Machine

### 6.1 States

```text
queued
running
waiting_provider
waiting_rate_limit
awaiting_approval
cancelling
partial
completed
failed
cancelled
interrupted
```

### 6.2 Allowed Transitions

```text
queued -> running | cancelled
running -> waiting_provider | waiting_rate_limit | awaiting_approval
running -> partial | completed | failed | cancelling | interrupted
waiting_provider -> queued | failed | cancelled
waiting_rate_limit -> queued | failed | cancelled
awaiting_approval -> queued | cancelled
cancelling -> cancelled | failed
interrupted -> queued | failed | cancelled
failed -> queued                         # explicit retry
partial -> queued                        # explicit missing-step retry
completed -> terminal
cancelled -> terminal
```

Invalid transitions return HTTP 409 and do not mutate the job.

### 6.3 Error Codes

```text
invalid_input
unsupported_artifact
engine_unavailable
engine_crashed
provider_no_credential
provider_rate_limited
provider_quota_exhausted
provider_unavailable
provider_timeout
provider_invalid_response
artifact_limit_exceeded
archive_limit_exceeded
job_timeout
cancelled
internal_error
```

`not_found` is a valid provider result, not an error.

## 7. Platform Database Schema

### 7.1 `jobs`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | text | primary key UUID |
| `tool_id` | text | indexed |
| `operation` | text | indexed |
| `status` | text | checked state enum, indexed |
| `priority_class` | text | interactive, workflow, batch |
| `priority` | integer | scheduling value |
| `client_request_id` | text | unique when supplied |
| `dedupe_key` | text | indexed |
| `configuration_hash` | text | cache and reproducibility |
| `engine_version` | text | nullable until assigned |
| `progress` | integer | 0 through 100 |
| `stage` | text | current stage |
| `attempt` | integer | default 0 |
| `max_attempts` | integer | default policy value |
| `cancel_requested` | boolean | default false |
| `result_ref` | text | nullable |
| `error_code` | text | nullable |
| `error_message` | text | nullable, sanitized |
| `lease_owner` | text | nullable |
| `lease_expires_at` | datetime | nullable, indexed |
| `heartbeat_at` | datetime | nullable |
| `created_at` | datetime | indexed |
| `queued_at` | datetime | nullable |
| `started_at` | datetime | nullable |
| `finished_at` | datetime | nullable |
| `row_version` | integer | optimistic concurrency |

Create a partial unique index on `dedupe_key` for active states so identical concurrent jobs become consumers of one execution.

### 7.2 `job_inputs`

```text
job_id, position, input_type, value_ref, sha256, metadata_json
```

### 7.3 `job_outputs`

```text
job_id, name, output_type, value_ref, sha256, metadata_json
```

### 7.4 `job_events`

| Column | Type | Rule |
| --- | --- | --- |
| `event_id` | integer | primary key autoincrement, SSE ID |
| `job_id` | text | foreign key, indexed |
| `job_sequence` | integer | unique with job ID |
| `event_type` | text | state, progress, provider, result, log |
| `stage` | text | nullable |
| `progress` | integer | nullable |
| `message` | text | sanitized analyst-facing text |
| `payload_json` | text | bounded metadata only |
| `created_at` | datetime | indexed |

SSE `id` uses `event_id`. Reconnection accepts `Last-Event-ID` and replays later events.

### 7.5 `job_consumers`

```text
job_id, consumer_type, consumer_id, requested_at
```

This records multiple tools or workflows waiting on a single-flight execution.

### 7.6 `artifacts`

```text
id, sha256, size_bytes, media_type, original_name, storage_path,
quarantined, created_at, last_accessed_at, retention_class
```

`sha256` is unique. Artifact bytes are stored under `runtime/artifacts/sha256/` and never inside SQLite.

### 7.7 `artifact_edges`

```text
parent_artifact_id, child_artifact_id, relationship, producing_job_id, metadata_json
```

Examples: `contains`, `extracted_from`, `decoded_from`, `generated_from`.

### 7.8 `result_objects`

```text
id, schema_name, schema_version, storage_ref, sha256, created_at
```

Large raw results are immutable files under `runtime/results/`; the database stores references and integrity hashes.

### 7.9 `cache_entries`

```text
cache_key, namespace, status, value_ref, value_sha256,
producer, producer_version, created_at, expires_at, stale_until,
last_accessed_at, hit_count, metadata_json
```

Statuses: `fresh`, `stale`, `expired`, `invalidated`.

### 7.10 Provider Tables

`provider_accounts`:

```text
id, provider, alias, secret_ref, plan_name, enabled,
last_success_at, last_failure_at, metadata_json
```

`provider_policies`:

```text
provider, operation, requests_per_second, requests_per_minute,
requests_per_day, max_concurrency, timeout_seconds, max_safe_retries,
positive_ttl_seconds, negative_ttl_seconds, stale_seconds,
submission_requires_approval
```

`provider_rate_state`:

```text
account_id, operation, tokens, window counters, cooldown_until,
quota_exhausted_until, updated_at
```

`provider_requests`:

```text
id, request_key, provider, operation, account_id, status,
input_hash, started_at, finished_at, retry_after,
http_status, cache_entry_key, error_code
```

Create a partial unique index on active `request_key` values for provider single-flight behavior.

`provider_consumers`:

```text
provider_request_id, job_id, job_step_id, attached_at
```

### 7.11 Engine Tables

`engine_instances`:

```text
tool_id, pid, base_url, status, engine_version, process_started_at,
last_health_at, last_error
```

`engine_jobs`:

```text
platform_job_id, tool_id, engine_job_id, status, last_sync_at
```

### 7.12 Later Workbench Tables

Add only after the runtime foundation is stable:

```text
runs
run_steps
evidence_refs
entities
relationships
findings
decisions
detection_candidates
detection_versions
validations
```

## 8. Public API Contracts

All new public endpoints use `/api/v1`.

### 8.1 Create Job

`POST /api/v1/jobs`

```json
{
  "tool": "malware",
  "operation": "scan",
  "inputs": [{"type": "artifact", "ref": "artifact-id"}],
  "parameters": {"online": true, "offline": true},
  "priority_class": "interactive",
  "client_request_id": "optional-idempotency-token",
  "force_refresh": false
}
```

Response: HTTP 202.

```json
{
  "id": "job-id",
  "status": "queued",
  "deduplicated": false,
  "attached_to_job_id": null,
  "created_at": "UTC timestamp"
}
```

When an identical job is active, the response attaches the caller as a consumer and returns the active job ID.

### 8.2 Job Status

`GET /api/v1/jobs/{job_id}`

Returns status, progress, stage, timestamps, retryability, cache metadata, provider waits, result availability, and sanitized error details.

### 8.3 Job Events

`GET /api/v1/jobs/{job_id}/events`

SSE headers:

```text
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

The endpoint replays persisted events after `Last-Event-ID`, then streams new events and periodic heartbeats.

### 8.4 Job Actions

```text
POST /api/v1/jobs/{id}/cancel
POST /api/v1/jobs/{id}/retry
GET  /api/v1/jobs/{id}/result
GET  /api/v1/jobs?status=&tool=&operation=&limit=&cursor=
```

### 8.5 Artifacts

```text
POST   /api/v1/artifacts
GET    /api/v1/artifacts/{id}
GET    /api/v1/artifacts/{id}/relationships
DELETE /api/v1/artifacts/{id}
```

Uploads stream to a temporary file while hashing and enforcing limits. A successful commit atomically moves the file into content-addressed storage.

### 8.6 Provider Status

```text
GET  /api/v1/providers
GET  /api/v1/providers/{provider}
POST /api/v1/providers/{provider}/test
POST /api/v1/providers/{provider}/refresh
```

Responses never expose credential values.

### 8.7 Error Envelope

```json
{
  "error": {
    "code": "provider_rate_limited",
    "message": "VirusTotal lookup is waiting for quota.",
    "retryable": true,
    "retry_after_seconds": 47,
    "correlation_id": "request-id",
    "details": {}
  }
}
```

## 9. Internal Engine API

Internal endpoints use `/internal/v1`, bind only to loopback, and require `X-SecLyst-Engine-Token`.

```text
POST /internal/v1/jobs/register
POST /internal/v1/jobs/{id}/events
POST /internal/v1/jobs/{id}/complete
POST /internal/v1/jobs/{id}/fail
POST /internal/v1/jobs/{id}/heartbeat
POST /internal/v1/providers/request
GET  /internal/v1/providers/requests/{id}
POST /internal/v1/providers/requests/{id}/cancel
```

The supervisor generates a distinct random token per engine instance and passes only that engine's token and control URL through its environment.

The platform validates that the token's tool identity matches the submitted `tool_id`.

## 10. Engine Job Integration Rules

Every long-running engine route accepts optional `X-SecLyst-Job-ID`.

- If supplied by an orchestrated workflow, the engine emits events against that job.
- If absent but control-plane settings exist, the engine registers a platform job and uses the returned ID.
- If the control plane is absent, the engine retains standalone behavior.

The public engine response preserves its current shape and adds `platform_job_id` when applicable.

## 11. Provider Broker Contract

### 11.1 Named Operations

The broker accepts only registered operations such as:

```text
virustotal.file_report
virustotal.url_report
virustotal.domain_report
urlscan.search
urlscan.submit
hybrid_analysis.hash_lookup
hybrid_analysis.submit
filescan.hash_lookup
filescan.submit
```

Arbitrary URL forwarding is forbidden.

### 11.2 Request

```json
{
  "provider": "virustotal",
  "operation": "file_report",
  "subject_type": "sha256",
  "subject": "normalized value",
  "options": {},
  "consumer_job_id": "job-id",
  "priority_class": "interactive",
  "force_refresh": false
}
```

### 11.3 Response States

```text
success
not_found
no_credential
waiting_rate_limit
quota_exhausted
unavailable
timeout
invalid_request
provider_error
cancelled
```

### 11.4 Scheduling

- Token bucket per provider account and operation.
- Semaphore per provider account.
- Interactive, workflow, and batch queues.
- Queue aging prevents starvation.
- `Retry-After` and quota headers set cooldowns.
- Safe lookups use bounded exponential backoff with jitter.
- Submission operations never auto-retry after an ambiguous response.
- A circuit breaker opens after policy-defined consecutive failures and admits periodic probes.

### 11.5 Single-Flight

Request key:

```text
provider + operation + normalized subject + canonical options + account scope
```

An active matching request gains another consumer rather than another provider call.

## 12. Cache Policy

### 12.1 Namespaces

```text
analysis.local
provider.response
event.query
ruleforge.render
ruleforge.evaluate
normalization.result
```

### 12.2 Keys

Local analysis:

```text
operation + artifact SHA-256 + engine version + configuration hash + ruleset version
```

Provider response:

```text
provider + operation + normalized subject + canonical options + account scope
```

Event query:

```text
dataset hash + query or rule hash + normalizer version
```

RuleForge:

```text
IR hash + target dialect + adapter version + field mapping version
```

### 12.3 Freshness Rules

- Deterministic local analysis has no time expiry; version-key changes invalidate it.
- Provider TTLs are configured per provider and operation.
- Negative `not_found` results use a shorter TTL than positive results.
- Provider errors, timeouts, and rate limits are never cached as data.
- Stale entries may be displayed as stale while a background refresh runs.
- Force refresh bypasses lookup but keeps prior provenance.
- Every response includes cache source, creation time, age, expiry, and producer version.

### 12.4 Storage

Small normalized values may remain in SQLite. Large provider payloads are immutable files under `runtime/cache/objects/`; metadata and hashes remain in SQLite.

## 13. Credential Plan

Create `seclyst/providers/credentials.py` with backends:

1. Operating-system keyring backend.
2. Environment variable fallback.
3. Explicit disabled backend for tests.

Add CLI commands:

```text
python -m seclyst credentials set virustotal
python -m seclyst credentials status
python -m seclyst credentials remove virustotal
```

The CLI reads secrets without echo. The web UI initially shows configured state and health only; it does not display stored values.

After provider migration, the supervisor must stop passing the complete parent environment to engines. Each child receives an allowlist containing ports, data paths, frame ancestors, control URL, engine token, and tool-specific non-secret flags.

## 14. Resource Pools

```text
local_light        small parsing and normalization
local_cpu          malware analysis and expensive transforms
local_io           file extraction and reports
event_ingest       EVTX parsing and indexing
external_lookup    non-submission provider calls
external_submit    explicitly approved submissions
```

Configuration belongs in `config/seclyst.toml`, not secrets.

Limits include:

- Worker count per pool.
- Maximum active jobs.
- Maximum artifact size.
- Archive expansion size and ratio.
- Maximum child artifacts and pipeline depth.
- Per-job deadline.
- Temporary storage quota.
- Retention period.

## 15. Frontend File Plan

### 15.1 Phase-One Tool Persistence

Add:

```text
apps/web/src/features/tools/ToolDock.tsx
apps/web/src/features/tools/tool-session-store.ts
apps/web/src/features/tools/frame-protocol.ts
apps/web/src/features/jobs/JobCenter.tsx
apps/web/src/features/jobs/JobBadge.tsx
apps/web/src/features/jobs/useJobEvents.ts
apps/web/src/lib/jobs-client.ts
```

Modify `apps/web/src/App.tsx`:

- Remove the keyed remount behavior from the tool region.
- Render `ToolDock` once outside route-specific shell screens.
- Mount a tool iframe on first visit and retain it afterward.
- Toggle inactive frames with visibility, pointer events, tab index, and ARIA state rather than unmounting.
- Preserve each tool's deep link independently.
- Replace the current activity popover with the durable `JobCenter`.
- Add per-tool active-job badges to the rail.

Modify `ToolFrame.tsx`:

- Accept `active`, `mounted`, and session route props.
- Never change `src` merely because another tool becomes active.
- Add strict postMessage origin helpers.
- Expose an explicit unload action for memory recovery.

Memory policy:

- Do not load all five frames at startup.
- Retain all visited frames by default.
- Show memory release controls in Settings.
- Job continuity must not depend on keeping the frame alive.

### 15.2 Frame Protocol

Message envelope:

```json
{
  "protocol": "seclyst-tool/v1",
  "tool": "malware",
  "type": "job.started",
  "payload": {},
  "message_id": "uuid"
}
```

Tool-to-shell messages:

```text
tool.ready
route.changed
job.started
job.updated
job.completed
result.opened
unsaved.changed
```

Shell-to-tool messages:

```text
navigate
focus.job
focus.result
theme.changed
```

Unknown protocol versions and origins are ignored.

### 15.3 Original UI Integration Files

Modify only lifecycle and bridge behavior in:

```text
engines/malware/ui/app.js
engines/ioc/ui/src/App.tsx
engines/ioc/ui/src/hooks/useLookup.ts
engines/events/app/static/app.js
engines/phishing/templates/index.html
engines/ruleforge/web/static/js/main.js
```

Each UI must:

- Restore active jobs on startup.
- Reconnect to event streams using a job ID.
- Route to an active or completed result.
- Emit bridge messages.
- Display waiting-rate-limit and partial states distinctly.

Visual analysis screens remain unchanged.

### 15.4 Later Workbench UI

After the control plane passes all reliability gates:

```text
apps/web/src/features/workbench/
apps/web/src/features/runs/
apps/web/src/features/evidence/
apps/web/src/features/detections/
```

Delete `DashboardLive.tsx` and replace `Landing.tsx` only in that later phase.

## 16. Engine File Plan

### 16.1 Shared Engine Client

Add a small importable client package under `seclyst/engines/client.py`. The supervisor adds the SecLyst repository root to child `PYTHONPATH` only in SecLyst mode.

The client supports register, event, heartbeat, complete, fail, and provider request calls with bounded timeouts. Control-plane unavailability cannot crash standalone engine analysis; it produces a local warning and preserves engine behavior.

### 16.2 Malware

Modify:

```text
engines/malware/run.py
engines/malware/modules/Malware_Analyzer.py
engines/malware/ui/app.js
```

Changes:

- Use the platform job ID as scan ID in SecLyst mode.
- Persist each stage event before Socket.IO emission.
- Persist cancel requests.
- Restore status from the control plane after reconnect.
- Publish final result reference before completion.
- Migrate VirusTotal first, then Hybrid Analysis and FileScan, to broker operations.
- Keep current endpoints and Socket.IO events for UI compatibility.

### 16.3 Phishing

Modify:

```text
engines/phishing/run.py
engines/phishing/core/pipeline.py
engines/phishing/core/apis.py
engines/phishing/templates/index.html
```

Changes:

- Replace `_tasks` as authoritative state with platform jobs.
- Emit one durable event per pipeline stage transition.
- Record partial provider failures without failing successful local stages.
- Register extracted attachments as child artifacts.
- Migrate VirusTotal and URLScan calls to the broker.
- Restore active tasks and results after reload.

### 16.4 IOC

Modify:

```text
engines/ioc/app/backend/main.py
engines/ioc/app/backend/pipeline.py
engines/ioc/app/backend/cache.py
engines/ioc/app/backend/adapters/base.py
engines/ioc/app/backend/adapters/virus_total.py
engines/ioc/ui/src/hooks/useLookup.ts
```

Changes:

- Map IOC tasks and batches to platform jobs.
- Keep existing execution-state semantics.
- Reuse IOC normalization, `Retry-After`, health, and TTL concepts as broker test vectors.
- Migrate shared providers to the broker incrementally.
- Preserve IOC-specific providers inside IOC until a second engine needs them.
- Keep current SSE endpoints during migration; the UI later consumes platform job events.

### 16.5 Event Analyzer

Modify:

```text
engines/events/app/api.py
engines/events/app/ingest.py
engines/events/app/static/app.js
```

Changes:

- Map investigation ingestion to platform jobs.
- Emit durable ingest checkpoints and counts.
- Preserve investigation ID as engine mapping.
- Add cancellation checkpoints between files and batches.
- Expose supplied-rule execution as a platform operation for later detection validation.

### 16.6 RuleForge

Modify later:

```text
engines/ruleforge/web/api.py
engines/ruleforge/web/static/js/main.js
```

Changes:

- Wrap large dataset evaluation in platform jobs.
- Persist render and validation provenance when initiated by a workflow.
- Keep ordinary Studio render and validation synchronous.

## 17. Migration And Startup

Add root Alembic configuration and `migrations/`.

Startup order:

1. Load non-secret configuration.
2. Resolve platform credential backend.
3. Create `runtime/backups/` and back up an existing platform SQLite database before schema upgrades.
4. Run Alembic upgrade to head.
5. Generate per-engine internal tokens.
6. Start the FastAPI control plane.
7. Start engine processes with allowlisted environments.
8. Start worker pools and recovery scan.
9. Mark expired leases interrupted and queue safe resumptions.
10. Serve the shell.

Rollback restores the pre-migration database backup and the prior Git commit. Engine databases are not modified by platform migrations.

## 18. Feature Flags During Migration

```text
SECLYST_KEEPALIVE_FRAMES=1
SECLYST_DURABLE_JOBS=0
SECLYST_PROVIDER_BROKER=0
SECLYST_ARTIFACT_STORE=0
SECLYST_WORKBENCH=0
```

Flags exist only for staged migration and rollback. Remove a flag after its phase is stable and the old path is deleted.

## 19. Test Plan

### 19.1 Job Unit Tests

- Every allowed transition succeeds.
- Every invalid transition returns conflict.
- Client request ID is idempotent.
- Active dedupe attaches consumers.
- Cancellation is idempotent.
- Event sequence is monotonic.
- Lease expiry marks a job interrupted.
- Safe retry increments attempts without changing inputs.

### 19.2 Queue Concurrency Tests

- Multiple workers claim a job once.
- SQLite busy retries stay bounded.
- Heartbeats extend only the owning lease.
- An expired worker cannot complete a reclaimed job.
- Priority aging prevents batch starvation.

### 19.3 Provider Tests

- Twenty identical concurrent VT lookups produce one upstream request.
- Different tools share the same provider budget.
- HTTP 429 honors numeric and HTTP-date `Retry-After`.
- Quota exhaustion waits until policy reset.
- Circuit breaker opens, probes, and closes correctly.
- Provider timeout is not `not_found`.
- Errors are not cached as successful data.
- Submission is never automatically retried after ambiguous failure.
- Disabled credentials return `no_credential` without a network request.

Use local fake provider servers. CI must not use real provider keys.

### 19.4 Cache Tests

- Canonical IOC forms share keys.
- Configuration and version changes invalidate local analysis.
- Negative cache expires earlier than positive cache.
- Stale-while-refresh returns visible stale metadata.
- Force refresh preserves old provenance.
- Corrupted object hashes are rejected.

### 19.5 Engine Contract Tests

- Standalone mode still works without control-plane variables.
- SecLyst mode registers and updates a platform job.
- Engine token identity is enforced.
- Engine crash produces an interrupted job.
- Reconnect retrieves active job and prior events.
- Existing public API response fields remain compatible during migration.

### 19.6 Frontend Tests

- Switching tools does not recreate a visited iframe.
- Each tool preserves its internal route.
- A hidden frame is not keyboard-focusable.
- Tool rail badges reflect server jobs.
- Job Center replays missed SSE events.
- Browser refresh restores active jobs.
- Clicking a job opens the correct tool and result.
- An iframe can be explicitly unloaded without cancelling its job.
- Invalid postMessage origins are ignored.

### 19.7 End-To-End Reliability Tests

- Start a Malware scan, switch through all tools, return, and observe continuous progress.
- Start a Phishing analysis, reload the shell, and recover progress.
- Restart SecLyst during a safe lookup and recover it.
- Request the same hash from Malware and IOC and observe one VT request.
- Exhaust a fake provider quota and observe waiting rather than failure.
- Cancel a job and verify no orphan process or temporary file remains.
- Complete partially when one provider is down.
- Preserve all five original tool interfaces and existing suites.

## 20. Observability

Use structured JSON logs with:

```text
timestamp
level
component
job_id
provider_request_id
correlation_id
duration_ms
```

Never log API keys, full provider authorization headers, artifact contents, email bodies, or raw passwords.

Expose local metrics through `/api/v1/system/metrics`:

```text
jobs by state
queue depth by pool
provider calls and cache hits
rate-limit waits
circuit state
engine health
artifact bytes
temporary bytes
```

These are operational facts, not a Command Center product dashboard.

## 21. Security Controls

- Loopback-only listeners.
- Random per-engine internal tokens.
- Constant-time token comparison.
- Strict origin checks for frame messages.
- Artifact MIME sniffing and extension-independent validation.
- Archive file-count, depth, ratio, and expanded-size limits.
- No executable artifact rendering inline.
- No arbitrary provider URL proxying.
- Server-side credentials only.
- Explicit approval for public submission, URL fetch, or active scanning.
- Bounded event and error payloads.
- Sanitized analyst-facing messages.
- Audit events for credentials, submissions, cancellation, deletion, and export.

## 22. Phased Execution And Commit Boundaries

### Phase 0: Plan And Baseline

Files:

```text
docs/CONTROL_PLANE_IMPLEMENTATION_PLAN.md
```

Commit: `docs: define SecLyst control-plane implementation plan`

Gate: plan approved; baseline CI green.

Rollback: documentation-only revert.

### Phase 1: Tool Session Persistence

Files:

```text
apps/web/src/App.tsx
apps/web/src/ui/ToolFrame.tsx
apps/web/src/features/tools/*
apps/web/src/features/jobs/JobCenter.tsx
```

Commit: `fix(web): preserve tool sessions across navigation`

Gate:

- Iframes retain DOM identity across switches.
- Existing browser tests pass.
- Hidden frames meet accessibility checks.
- No backend behavior changes.

Rollback: feature flag off or commit revert.

### Phase 2: Durable Job Kernel

Files:

```text
seclyst/database/*
seclyst/jobs/*
seclyst/api/jobs.py
seclyst/api/internal.py
migrations/*
tests/jobs/*
```

Commit: `feat(control-plane): add durable jobs and event journal`

Gate:

- State, lease, queue, SSE replay, crash, and concurrency tests pass.
- No engine uses the new path yet.

Rollback: feature flag off; restore database backup if required.

### Phase 3: Malware And Phishing Jobs

Commit A: `feat(malware): publish durable SecLyst scan jobs`

Commit B: `feat(phishing): persist pipeline jobs and progress`

Gate after each commit:

- Standalone suite passes.
- Tool UI resumes a job after shell refresh.
- Engine restart produces explicit interruption.
- No provider migration yet.

Rollback: remove control URL from engine environment and revert the engine commit.

### Phase 4: Shared Provider Broker

Commit A: `feat(providers): add broker scheduling and shared cache`

Commit B: `feat(providers): route VirusTotal through shared broker`

Commit C: `feat(providers): migrate URLScan and sandbox lookups`

Gate:

- Single-flight and quota tests pass.
- Malware, IOC, and Phishing share VT budget.
- No real provider calls in CI.
- Standalone direct-provider mode still passes.

Rollback: provider broker flag off; engine fallback direct path remains until the phase is stable.

### Phase 5: IOC, Event, And RuleForge Jobs

Commit A: `feat(ioc): map lookup and batch work to platform jobs`

Commit B: `feat(events): publish durable ingestion jobs`

Commit C: `feat(ruleforge): persist workflow validation jobs`

Gate: every long-running operation is visible in Job Center and survives shell navigation.

### Phase 6: Artifact Store And Resource Controls

Commit: `feat(storage): add content-addressed artifacts and retention`

Gate:

- Duplicate uploads reuse bytes.
- Archive safety tests pass.
- Cancellation removes temporary state.
- Retention cannot delete referenced artifacts.

### Phase 7: Workbench Information Architecture

Commit A: `feat(web): add Workbench and Runs`

Commit B: `feat(web): add Detection Lab`

Commit C: `refactor(web): remove Overview and Command Center`

Gate: runtime jobs remain unchanged and original tool routes still work.

### Phase 8: Email-To-Detection Workflow

Commit A: `feat(workflows): add email-to-detection recipe`

Commit B: `feat(evidence): add provenance graph and decisions`

Commit C: `feat(detections): add validation package export`

Gate: one email flows through Phishing, Malware, IOC, optional Event data, and RuleForge without manual result transfer.

### Phase 9: Hardening And Removal

Commit A: `test: add control-plane failure and recovery coverage`

Commit B: `refactor: remove migrated in-memory job paths`

Commit C: `docs: document operations, privacy, and recovery`

Gate: full clean-setup, engine, browser, audit, restart, and recovery suites pass.

## 23. Phase Completion Rules

A phase is complete only when:

1. Its migrations and API schemas are documented.
2. New unit and integration tests pass.
3. All affected original engine suites pass.
4. Browser regression tests pass.
5. Dependency audits pass.
6. The worktree contains no unintended generated files or secrets.
7. The phase has one or more focused commits matching the boundaries above.
8. The remote branch contains the verified commits.

Do not combine unrelated phases into one commit or bypass a failed gate.

## 24. Final Acceptance Criteria

- A running scan survives navigation across all five tools.
- Reloading the browser restores current progress and result context.
- A platform restart recovers or explicitly interrupts jobs without silent loss.
- Two tools requesting the same provider operation share one call.
- Provider 429 responses create a visible wait with retry timing.
- One tool cannot exhaust all provider concurrency.
- Identical artifacts and deterministic analyses are deduplicated safely.
- Cache age, source, and producer version are visible.
- Partial provider failure preserves successful findings.
- Cancellation leaves no orphan process, lease, temporary file, or provider consumer.
- Provider secrets remain only in the platform credential backend.
- Original interfaces and standalone launch modes continue to work.
- Overview and Command Center are removed only after Workbench, Runs, and Detection Lab are functional.
- The Email-to-Detection workflow produces a reproducible evidence-backed detection package.

## 25. First Execution Step After Approval

Implement Phase 1 only: persistent, lazily mounted tool frames and tool-session state. Do not begin the durable job kernel in the same change. Verify iframe identity, navigation, accessibility, memory behavior, and all existing browser tests before committing Phase 1.
