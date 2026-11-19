"""Run the reproducible Seclyst verification suite."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str], cwd: Path = ROOT) -> None:
    print(f"\n[{cwd.relative_to(ROOT) if cwd != ROOT else '.'}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()

    python = sys.executable
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("npm is required for Seclyst verification.")

    run([python, "-m", "pytest", "-q"])
    run([
        python, "-m", "ruff", "check",
        "seclyst", "scripts", "tests",
        "engines/malware/run.py", "engines/malware/tests/test_seclyst_defaults.py",
        "engines/phishing/run.py", "engines/phishing/core/database.py",
        "engines/phishing/tests/test_seclyst_contract.py",
        "engines/ioc/app/backend/main.py", "engines/ruleforge/web/api.py",
    ])
    run([python, "-m", "pytest", "-q"], ROOT / "engines" / "malware")
    run([python, "-m", "pytest", "-q"], ROOT / "engines" / "events")
    run([python, "-m", "pytest", "-q"], ROOT / "engines" / "phishing")
    run([python, "-m", "pytest", "-q"], ROOT / "engines" / "ioc")
    run([python, "run.py", "verify"], ROOT / "engines" / "ruleforge")

    run([npm, "test"], ROOT / "apps" / "web")
    run([npm, "run", "build"], ROOT / "apps" / "web")
    run([npm, "test"], ROOT / "engines" / "ioc" / "ui")
    run([npm, "run", "lint"], ROOT / "engines" / "ioc" / "ui")
    run([npm, "run", "build"], ROOT / "engines" / "ioc" / "ui")

    if not args.skip_audit:
        run([python, "-m", "pip_audit", "-r", "requirements.txt"])
        run([npm, "audit"], ROOT / "apps" / "web")
        run([npm, "audit"], ROOT / "engines" / "ioc" / "ui")

    if not args.skip_browser:
        run([python, "scripts/verify_ui.py"])
    run([python, "scripts/verify_cli.py"])

    combined_workspace = ROOT.parent
    if all((combined_workspace / name).exists() for name in (
        "secconflux", "Malware Analyzer", "ioc-platform", "Event-Analyzer",
        "Phishing-Mail-Detector", "RuleForge",
    )):
        run([python, "scripts/source_snapshot.py"])

    print("\nAll Seclyst verification checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
