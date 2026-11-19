"""Browser smoke test for the Seclyst shell and all five live tool frames."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError as exc:  # pragma: no cover - environment guidance
    raise SystemExit("Install requirements-dev.txt to run browser verification.") from exc

from seclyst.server import Supervisor, WEB_DIST, build_http_server  # noqa: E402


TOOLS = ("ioc", "malware", "phishing", "events", "ruleforge")


def wait_for_engines(supervisor: Supervisor) -> None:
    deadline = time.monotonic() + 40
    last = None
    while time.monotonic() < deadline:
        last = supervisor.status()
        if all(row["status"] == "online" for row in last["tools"].values()):
            return
        time.sleep(0.25)
    raise RuntimeError(f"Engines did not become ready: {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell-port", type=int, default=7000)
    parser.add_argument(
        "--engine-port-base",
        type=int,
        help="use base+1 through base+5 instead of the configured engine ports",
    )
    args = parser.parse_args()
    if args.engine_port_base is not None:
        for offset, name in enumerate((
            "SECLYST_MALWARE_PORT", "SECLYST_IOC_PORT", "SECLYST_EVENTS_PORT",
            "SECLYST_PHISHING_PORT", "SECLYST_RULEFORGE_PORT",
        ), 1):
            os.environ[name] = str(args.engine_port_base + offset)
    base_url = f"http://127.0.0.1:{args.shell_port}/"

    if not (WEB_DIST / "index.html").is_file():
        raise SystemExit("Build apps/web before running browser verification.")

    supervisor = Supervisor(args.shell_port)
    supervisor.start_all()
    server = build_http_server("127.0.0.1", args.shell_port, supervisor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = None
    try:
        wait_for_engines(supervisor)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1440,1000")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 25)

        for route, expected in (("#/", "Seclyst"), ("#/dashboard", "Command Center"), ("#/settings", "Settings")):
            driver.get(base_url + route)
            wait.until(lambda browser: expected in browser.find_element(By.TAG_NAME, "body").text)
            print(f"shell {route}: ok")

        driver.get(base_url + "#/dashboard")
        wait.until(lambda browser: "5 of 5" in browser.find_element(By.TAG_NAME, "body").text)
        print("live dashboard: 5 of 5 engines online")

        for tool in TOOLS:
            driver.get(base_url + f"#/t/{tool}")
            frame = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, "iframe.sc-frame"))
            driver.switch_to.frame(frame)
            wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
            wait.until(lambda browser: len(browser.find_element(By.TAG_NAME, "body").text.strip()) > 40)
            title = driver.title or "untitled"
            driver.switch_to.default_content()
            print(f"{tool}: ok ({title})")

        driver.get(base_url + "#/t/ruleforge")
        frame = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, "iframe.sc-frame"))
        driver.switch_to.frame(frame)
        driver.execute_script("window.location.hash = '#/studio/author/details'")
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, ".topbar-right").is_displayed())
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, ".page h1").text == "Details")
        driver.switch_to.default_content()
        print("ruleforge studio: unchanged workflow chrome is visible")

        severe = [
            entry for entry in driver.get_log("browser")
            if entry.get("level") == "SEVERE"
            and "favicon" not in entry.get("message", "").lower()
        ]
        if severe:
            for entry in severe:
                print(entry["message"], file=sys.stderr)
            raise RuntimeError(f"Browser reported {len(severe)} severe console errors.")
        print("Seclyst browser verification passed.")
        return 0
    except Exception:
        if driver is not None:
            output = ROOT / "runtime" / "browser-failure.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            driver.save_screenshot(str(output))
            print(f"Failure screenshot: {output}", file=sys.stderr)
        raise
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        supervisor.stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
