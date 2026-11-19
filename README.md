# Seclyst

Seclyst is a local security analyst workbench that starts and presents five existing tools in one shell:

- IOC Lookup Platform
- Malware Analyzer
- Event Analyzer
- Phishing Mail Detector
- RuleForge

The tools are not redrawn. Each copied backend serves its original interface on an isolated loopback origin, and Seclyst hosts that interface edge-to-edge inside the workbench. The shell adds live health, recent-work aggregation, shared navigation, and an IOC clipboard without changing the tools' normal screens.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer with npm
- A modern Chromium, Firefox, or Edge browser
- Optional native utilities required by individual analyzers, such as Tesseract OCR or libmagic

## Setup

From this directory:

```powershell
python scripts/setup.py
```

The setup script creates `.venv`, installs the copied Python engines, installs locked Node dependencies, and builds both the Seclyst shell and IOC interface.

Use `python scripts/setup.py --dev` when the full test and browser-verification toolchain is required.

## Start

Windows:

```powershell
.venv\Scripts\python.exe run.py
```

Linux or macOS:

```bash
.venv/bin/python run.py
```

Seclyst opens at `http://127.0.0.1:7000/`. One Ctrl+C stops the shell and all five copied engines.

Use `--no-browser` when automatic browser launch is not wanted. All listeners are restricted to loopback.

## Configuration

Copy `.env.example` to `.env` to override internal ports or provide optional threat-intelligence credentials. The root `.env` is loaded server-side and inherited by copied engines; values are never returned to the browser or stored in localStorage.

External submission features remain disabled by default. Enabling a provider key does not automatically opt a sample into public submission.

## Runtime Layout

| Service | Default port | Interface |
| --- | ---: | --- |
| Seclyst shell | 7000 | Unified workbench |
| Malware Analyzer | 7101 | Original Malware Analyzer UI |
| IOC Lookup | 7102 | Original IOC React UI |
| Event Analyzer | 7103 | Original Event Analyzer UI |
| Phishing Detector | 7104 | Original Phishing UI |
| RuleForge | 7105 | Original RuleForge UI |

Databases, uploads, logs, caches, and engine history are written beneath `runtime/`, which is excluded from version control.

## Verification

```powershell
python -m pytest
npm --prefix apps/web run build
npm --prefix engines/ioc/ui test
npm --prefix engines/ioc/ui run build
python scripts/source_snapshot.py
python scripts/verify_ui.py
python scripts/verify_cli.py
```

The complete local suite can be run with `.venv\Scripts\python.exe scripts\verify.py` on Windows or `.venv/bin/python scripts/verify.py` on Linux and macOS.

The final command verifies that the six source directories outside `Seclyst/` still match the baseline captured before this workspace was created. It is intended for the original Combined Project workspace and is not required after exporting Seclyst as a standalone repository.

## Repository Notes

- Required production code is tracked as source, not as generated browser captures.
- `.env`, runtime databases, uploaded samples, caches, logs, builds, and dependency directories are ignored.
- No nested Git repository is created by the setup script.
- The imported tools retain their own provenance and license status. See `docs/SOURCES.md` before publishing or redistributing this workspace.

See `docs/ARCHITECTURE.md` for the process and browser boundaries.
