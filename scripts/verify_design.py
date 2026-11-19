"""Run Hallmark's rendered UI audit against a live Seclyst instance."""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seclyst.server import Supervisor, build_http_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sloplint", type=Path, help="path to Hallmark scripts/sloplint.mjs")
    args = parser.parse_args()
    if not args.sloplint.is_file():
        parser.error(f"sloplint was not found at {args.sloplint}")

    supervisor = Supervisor(7000)
    supervisor.start_all()
    server = build_http_server("127.0.0.1", 7000, supervisor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(3)
        result = subprocess.run(
            [
                "node",
                str(args.sloplint),
                str(ROOT / "apps" / "web" / "src"),
                "--genre",
                "modern-minimal",
                "--scope",
                "app",
                "--render",
                "--url",
                "http://127.0.0.1:7000/#/",
            ],
            cwd=ROOT,
            check=False,
        )
        return result.returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        supervisor.stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
