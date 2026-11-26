"""Create the local Seclyst environment and build both React applications."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"[{cwd.relative_to(ROOT) if cwd != ROOT else '.'}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def setup_python(*, dev: bool = False) -> Path:
    if sys.version_info < (3, 11):
        raise SystemExit("Seclyst requires Python 3.11 or newer.")
    python = venv_python()
    if not python.is_file():
        print(f"Creating {VENV}")
        venv.EnvBuilder(with_pip=True).create(VENV)
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    requirements = "requirements-dev.txt" if dev else "requirements.txt"
    run([str(python), "-m", "pip", "install", "-r", requirements])
    return python


def setup_node() -> None:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("Node.js and npm are required to build the Seclyst interfaces.")
    for project in (ROOT / "web", ROOT / "engines" / "ioc" / "ui"):
        run([npm, "ci"], cwd=project)
        run([npm, "run", "build"], cwd=project)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-python", action="store_true", help="do not create or update .venv")
    parser.add_argument("--skip-node", action="store_true", help="do not install or build Node projects")
    parser.add_argument("--dev", action="store_true", help="install test and browser-verification dependencies")
    args = parser.parse_args()

    python = venv_python()
    if not args.skip_python:
        python = setup_python(dev=args.dev)
    if not args.skip_node:
        setup_node()

    if not (ROOT / "web" / "dist" / "index.html").is_file():
        raise SystemExit("Seclyst web build is missing. Run setup without --skip-node.")
    if not (ROOT / "engines" / "ioc" / "ui" / "dist" / "index.html").is_file():
        raise SystemExit("IOC interface build is missing. Run setup without --skip-node.")

    launcher = python if python.is_file() else Path(sys.executable)
    print("\nSeclyst setup is complete.")
    print(f"Start it with: {launcher} {ROOT / 'run.py'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
