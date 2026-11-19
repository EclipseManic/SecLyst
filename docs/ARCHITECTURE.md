# Seclyst Architecture

## Process Model

`run.py` starts a standard-library supervisor. The supervisor creates runtime directories, starts five copied engines as child processes, serves the built Seclyst shell, and stops every child during shutdown.

The shell does not proxy or reinterpret tool requests. Each tool interface communicates with its own backend at the same loopback origin, preserving REST, server-sent event, WebSocket, download, and upload behavior without route rewriting.

The shell mounts a tool frame only on first visit, then keeps that frame mounted and makes inactive frames inert and visually hidden. This preserves browser-side state during navigation without loading all five applications at startup. The retained frame is a presentation optimization only; backend execution must not depend on it.

## Browser Boundary

The Seclyst shell is served from port 7000. Tool interfaces are hosted in sandboxed cross-origin frames on ports 7101 through 7105.

This boundary provides two properties:

- Original CSS and scripts cannot collide with the Seclyst shell.
- Tool scripts cannot read the shell DOM, shared clipboard storage, or shell preferences.

IOC Lookup and RuleForge originally denied all framing. Their copied backend headers allow only the Seclyst loopback origins while retaining their remaining content-security policies. RuleForge also waits for its initial example to be lowered before the first render, preventing an otherwise harmless validation error during boot; its visual interface is unchanged.

## Platform API

The shell reads only two same-origin endpoints:

- `GET /api/platform/status` returns measured health and configured tool URLs.
- `GET /api/platform/summary` returns recent records exposed by each engine's existing history endpoint.

Unavailable tools and collections remain explicitly unavailable. No fixture fallback or generated operational metric is present.

## Data Boundary

The supervisor redirects mutable engine state into `runtime/<tool>/`:

- Malware scan and request-cache databases
- IOC SQLite data and response cache
- Event databases and uploads
- Phishing scan database
- RuleForge history store
- Per-engine logs

Provider credentials are read from the process environment or root `.env` and passed only to child processes.

## Source Boundary

Copied engines live under `engines/`. Integration changes are deliberately narrow:

- Health endpoints were added where an engine lacked one.
- Mutable database locations can be supplied by the supervisor.
- IOC Lookup and RuleForge accept the Seclyst shell as a frame ancestor.
- Vulnerable dependency constraints were updated.
- Automatic browser launch is disabled by the supervisor.

Original interface source is otherwise retained. Seclyst-specific UI belongs only under `apps/web/`.

## Failure Model

One engine can fail without preventing Seclyst or the other tools from starting. The workbench shows the failed engine as offline and points to `runtime/logs/<tool>.log`. Occupied engine ports are reported rather than silently attaching to an unknown process.
