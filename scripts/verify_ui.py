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
    from selenium.webdriver.common.keys import Keys
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

        for route, expected in (("#/", "Security operations"), ("#/activity", "Your analysis timeline"), ("#/settings", "Settings")):
            driver.get(base_url + route)
            wait.until(lambda browser: expected in browser.find_element(By.TAG_NAME, "body").text)
            print(f"shell {route}: ok")

        driver.get(base_url + "#/")
        dashboard_order = driver.execute_script("const consoleSection=document.querySelector('.ops-intake'); const ruleforge=document.querySelector('.ops-ruleforge'); return Boolean(consoleSection && ruleforge && (ruleforge.compareDocumentPosition(consoleSection) & Node.DOCUMENT_POSITION_FOLLOWING));")
        if not dashboard_order:
            raise RuntimeError("Dashboard analysis console is not the final section.")
        print("dashboard hierarchy: analysis console is the final section")
        shell_scroll = driver.execute_script("const panel=document.querySelector('.sc-scroll'); panel.scrollTop=600; return {body:window.scrollY, panel:panel.scrollTop, rail:document.querySelector('.sc-rail').getBoundingClientRect().top};")
        if shell_scroll["body"] != 0 or shell_scroll["panel"] <= 0 or shell_scroll["rail"] != 0:
            raise RuntimeError(f"Sidebar and content scrolling are not isolated: {shell_scroll}")
        print("shell layout: sidebar remains fixed while content scrolls independently")

        for tool in TOOLS:
            driver.get(base_url + f"#/t/{tool}")
            frame = wait.until(
                lambda browser: browser.find_element(
                    By.CSS_SELECTOR,
                    f'.sc-tool-session.is-active[data-tool="{tool}"] iframe'
                )
            )
            driver.switch_to.frame(frame)
            wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
            wait.until(lambda browser: len(browser.find_element(By.TAG_NAME, "body").text.strip()) > 40)
            title = driver.title or "untitled"
            driver.switch_to.default_content()
            print(f"{tool}: ok ({title})")

        driver.get(base_url + "#/t/ruleforge")
        frame = wait.until(
            lambda browser: browser.find_element(
                By.CSS_SELECTOR,
                '.sc-tool-session.is-active[data-tool="ruleforge"] iframe'
            )
        )
        driver.switch_to.frame(frame)
        wait.until(lambda browser: browser.execute_script("return document.readyState") == "complete")
        wait.until(lambda browser: len(browser.find_element(By.TAG_NAME, "body").text.strip()) > 40)
        studio_links = driver.find_elements(By.CSS_SELECTOR, ".mainnav-link")
        if len(studio_links) < 2:
            raise RuntimeError("RuleForge Studio navigation is missing.")
        studio_links[1].click()
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, ".topbar-right").is_displayed())
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, ".page h1").text == "Details")
        driver.switch_to.default_content()
        print("ruleforge studio: unchanged workflow chrome is visible")

        driver.get(base_url + "#/t/malware")
        malware_frame = wait.until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '.sc-tool-session.is-active[data-tool="malware"] iframe')
        )
        driver.switch_to.frame(malware_frame)
        driver.execute_script("window.__seclystRetentionMarker = 'retained'")
        driver.switch_to.default_content()
        driver.execute_script("window.location.hash = '#/t/phishing'")
        wait.until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '.sc-tool-session.is-active[data-tool="phishing"] iframe')
        )
        inactive_malware = driver.find_element(By.CSS_SELECTOR, '.sc-tool-session[data-tool="malware"]')
        if inactive_malware.get_attribute("aria-hidden") != "true" or inactive_malware.get_attribute("inert") is None:
            raise RuntimeError("Inactive Malware frame is not isolated from accessibility and pointer navigation.")
        driver.execute_script("window.location.hash = '#/t/malware'")
        retained_frame = wait.until(
            lambda browser: browser.find_element(By.CSS_SELECTOR, '.sc-tool-session.is-active[data-tool="malware"] iframe')
        )
        if retained_frame.id != malware_frame.id:
            raise RuntimeError("Malware iframe was recreated while navigating between tools.")
        driver.switch_to.frame(retained_frame)
        marker = driver.execute_script("return window.__seclystRetentionMarker")
        driver.switch_to.default_content()
        if marker != "retained":
            raise RuntimeError("Malware iframe JavaScript context was lost during tool navigation.")
        print("tool sessions: iframe identity, JavaScript state and accessibility isolation retained")

        driver.execute_script("window.location.hash = '#/t/ioc'")
        ioc_frame = wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, '.sc-tool-session.is-active[data-tool="ioc"] iframe'))
        driver.switch_to.frame(ioc_frame)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.CONTROL, "m")
        driver.switch_to.default_content()
        wait.until(lambda browser: browser.find_element(By.CSS_SELECTOR, ".sc-modal .sc-palette-input"))
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        print("universal Ctrl+M navigator: opens from inside an isolated tool frame")

        severe = [
            entry for entry in driver.get_log("browser")
            if entry.get("level") == "SEVERE"
            and "favicon" not in entry.get("message", "").lower()
            and "focus-without-user-activation" not in entry.get("message", "").lower()
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
