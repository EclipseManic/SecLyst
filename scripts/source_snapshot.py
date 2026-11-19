"""Record and verify that Seclyst's upstream source directories stay untouched."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]
SECLYST = WORKSPACE / "Seclyst"
BASELINE = SECLYST / "docs" / "source-baseline.json"

SOURCES = {
    "secconflux": WORKSPACE / "secconflux",
    "malware": WORKSPACE / "Malware Analyzer",
    "ioc": WORKSPACE / "ioc-platform",
    "events": WORKSPACE / "Event-Analyzer",
    "phishing": WORKSPACE / "Phishing-Mail-Detector",
    "ruleforge": WORKSPACE / "RuleForge",
}

EXCLUDED_DIRECTORIES = {
    ".git",
    ".hallmark",
    ".kilo",
    ".oxcode-memory",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "node_modules",
    "test_files",
    "venv",
    ".venv",
}

EXCLUDED_NAMES = {
    ".env",
    "eval(s)()",
    "extract_issues.py",
    "issues.html",
    "issues.txt",
    "show_rows.py",
}

EXCLUDED_SUFFIXES = {
    ".db",
    ".db-shm",
    ".db-wal",
    ".pyc",
    ".sqlite",
    ".sqlite3",
}


def excluded(path: Path, source: Path) -> bool:
    relative = path.relative_to(source)
    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
        return True
    name = path.name
    if name in EXCLUDED_NAMES:
        return True
    if name.startswith(("probe_", "session", "freebuff-chat-")):
        return True
    return any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def snapshot() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for source_name, source in SOURCES.items():
        files: dict[str, str] = {}
        for path in sorted(source.rglob("*")):
            if path.is_file() and not excluded(path, source):
                files[path.relative_to(source).as_posix()] = digest(path)
        result[source_name] = files
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="replace the source baseline")
    args = parser.parse_args()

    current = snapshot()
    if args.write:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Recorded {sum(len(files) for files in current.values())} source files.")
        return 0

    if not BASELINE.is_file():
        print(f"Missing source baseline: {BASELINE}")
        return 2

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    if current == expected:
        print("Original source directories match the Seclyst baseline.")
        return 0

    for source_name in SOURCES:
        old = expected.get(source_name, {})
        new = current.get(source_name, {})
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(path for path in set(old) & set(new) if old[path] != new[path])
        if added or removed or changed:
            print(f"{source_name}: +{len(added)} -{len(removed)} changed={len(changed)}")
            for path in (added + removed + changed)[:20]:
                print(f"  {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
