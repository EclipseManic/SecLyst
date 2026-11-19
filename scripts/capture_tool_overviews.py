"""Capture the visible landing surface of every live Seclyst tool frame."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from selenium import webdriver  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402

from seclyst.server import Supervisor, build_http_server  # noqa: E402


TOOLS = ("ioc", "malware", "phishing", "events", "ruleforge")
SHELL_PORT = 7200
CAPTURE_PORTS = {
    "SECLYST_MALWARE_PORT": 7201,
    "SECLYST_IOC_PORT": 7202,
    "SECLYST_EVENTS_PORT": 7203,
    "SECLYST_PHISHING_PORT": 7204,
    "SECLYST_RULEFORGE_PORT": 7205,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="current")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    args = parser.parse_args()
    output = ROOT / "runtime" / "tool-overviews" / args.label
    output.mkdir(parents=True, exist_ok=True)
    for name, port in CAPTURE_PORTS.items():
        os.environ[name] = str(port)

    supervisor = Supervisor(SHELL_PORT)
    supervisor.start_all()
    server = build_http_server("127.0.0.1", SHELL_PORT, supervisor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = None
    try:
        deadline = time.monotonic() + 40
        status = None
        while time.monotonic() < deadline:
            status = supervisor.status()
            if all(row["status"] == "online" for row in status["tools"].values()):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"The five tool engines did not become ready: {status}")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument(f"--window-size={args.width},{args.height}")
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 25)

        for tool in TOOLS:
            driver.get(f"http://127.0.0.1:{SHELL_PORT}/#/t/{tool}")
            frame = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, "iframe.sc-frame"))
            driver.switch_to.frame(frame)
            wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
            wait.until(lambda browser: len(browser.find_element(By.TAG_NAME, "body").text.strip()) > 40)
            driver.switch_to.default_content()
            frame = driver.find_element(By.CSS_SELECTOR, "iframe.sc-frame")
            path = output / f"{tool}.png"
            frame.screenshot(str(path))
            print(path)
        return 0
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        supervisor.stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
