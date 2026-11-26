# Security policy

## Supported versions

Seclyst is pre-1.0. Security fixes are made against the latest release and the
`main` branch. Older versions are not patched.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| < 0.1 | No |

## Reporting a vulnerability

Report privately through GitHub Security Advisories:

<https://github.com/EclipseManic/SecLyst/security/advisories/new>

Do not open a public issue, and do not include working exploit details in a
public discussion. If you cannot use advisories, open a public issue that says
only that you have a security report and how to reach you.

Please include: the version or commit, the affected component, the impact, and
the smallest reproduction you have.

## What is in scope

- The platform control plane: authentication, session handling, settings, and
  the engine-to-platform internal channel.
- The access-token boundary that guards the engine ports.
- Artifact handling: upload limits, content addressing, and download
  disposition.
- The provider broker: whether credentials can leak to an engine, a log, or the
  browser.
- Cross-origin isolation between the shell and the tool frames.
- Dependency vulnerabilities reachable from the platform's default
  configuration.

## What is out of scope

- **Sample analysis is inherently unsafe.** Seclyst parses hostile files,
  archives, documents, and email. A crash, hang, or resource spike caused by a
  deliberately malformed input is a robustness bug, not a security vulnerability,
  unless it leads to code execution or escapes the engine process.
- **Local-only threat models.** Seclyst binds loopback by default. Reports that
  require the analyst to expose the port publicly, disable the access token, or
  run as an untrusted local user are considered configuration issues.
- **Third-party provider behaviour.** How VirusTotal, Hybrid Analysis, Triage,
  FileScan, or any enrichment provider handles submitted data is governed by that
  provider.
- **Outbound actions that are off by default.** Active port scanning, URL
  fetching, public sample submission, and webhooks must be enabled explicitly.
  A finding that requires enabling them is a design discussion, not a
  vulnerability.

## Hardening expectations

Seclyst ships with these defaults, and a report that assumes them is in scope:

- Every listener binds to loopback only.
- Engine ports require the workspace access token; direct requests are rejected.
- Provider credentials stay server-side and are withheld from engines when the
  broker is active.
- Active network actions and public submission are disabled.
- Artifacts are never rendered inline and downloads use attachment disposition.

## What to expect

- Acknowledgement of a report within a few days.
- An assessment with the severity and the reasoning.
- A fix in the next release for anything confirmed, with credit in the release
  notes if you want it.

This is a small project. There is no bug bounty.
