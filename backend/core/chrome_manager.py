import logging
import json
import os
import sys
import time
import subprocess
from pathlib import Path

import requests
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class ChromeNotFoundError(Exception):
    pass


class ChromeAttachError(Exception):
    pass


def get_chrome_executable() -> str:
    system = sys.platform

    if system == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif system == "win32":
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.path.expanduser("~"), "AppData", "Local", "Google", "Chrome", "Application", "chrome.exe"),
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]

    for path in candidates:
        if path and os.path.exists(path):
            return path

    raise ChromeNotFoundError(
        f"Chrome not found on {system}. Install Google Chrome and try again."
    )


def is_chrome_debug_running(port: int) -> bool:
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _chrome_debug_pids(port: int) -> list[int]:
    if sys.platform == "win32":
        return []
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
        )
        return [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
    except Exception:
        return []


def _process_command(pid: int) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _process_user_data_dir(command: str) -> str:
    marker = "--user-data-dir="
    if marker not in command:
        return ""
    value = command.split(marker, 1)[1].split(" ", 1)[0].strip("'\"")
    return str(Path(value).expanduser().resolve())


def ensure_matching_chrome_profile(port: int, user_data_dir: str) -> None:
    expected = str(Path(user_data_dir).expanduser().resolve())
    stale_pids: list[int] = []

    for pid in _chrome_debug_pids(port):
        command = _process_command(pid)
        if f"--remote-debugging-port={port}" not in command:
            continue
        actual = _process_user_data_dir(command)
        if actual and actual != expected:
            stale_pids.append(pid)

    if not stale_pids:
        return

    logger.info("Restarting Chrome debug port %s with isolated local profile %s", port, expected)
    for pid in stale_pids:
        try:
            os.kill(pid, 15)
        except Exception:
            pass

    for _ in range(20):
        if not is_chrome_debug_running(port):
            return
        time.sleep(0.25)

    for pid in stale_pids:
        try:
            os.kill(pid, 9)
        except Exception:
            pass

    for _ in range(20):
        if not is_chrome_debug_running(port):
            return
        time.sleep(0.25)


def write_local_profile_preferences(user_data_dir: str) -> None:
    default_dir = Path(user_data_dir) / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    preferences_path = default_dir / "Preferences"

    preferences = {}
    if preferences_path.exists():
        try:
            preferences = json.loads(preferences_path.read_text())
        except Exception:
            preferences = {}

    preferences["credentials_enable_service"] = False
    preferences.setdefault("profile", {})
    preferences["profile"]["password_manager_enabled"] = False
    preferences["profile"]["default_content_setting_values"] = {
        **preferences["profile"].get("default_content_setting_values", {}),
        "notifications": 2,
    }

    preferences_path.write_text(json.dumps(preferences))


def get_chrome_page_targets(port: int) -> list[dict]:
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2)
        if resp.status_code != 200:
            return []
        return [target for target in resp.json() if target.get("type") == "page"]
    except Exception:
        return []


def ensure_chrome_page_target(port: int) -> None:
    if get_chrome_page_targets(port):
        return

    try:
        requests.put(f"http://127.0.0.1:{port}/json/new?about:blank", timeout=2)
    except Exception as exc:
        raise ChromeAttachError(
            f"Chrome debug port {port} is available, but no browser page could be opened: {exc}"
        ) from exc

    for _ in range(10):
        if get_chrome_page_targets(port):
            return
        time.sleep(0.25)

    raise ChromeAttachError(
        f"Chrome debug port {port} is available, but Selenium could not find an open browser page."
    )


def launch_chrome_debug(port: int, user_data_dir: str) -> subprocess.Popen:
    chrome_exe = get_chrome_executable()
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    write_local_profile_preferences(user_data_dir)

    args = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--disable-blink-features=AutomationControlled",
        "--disable-save-password-bubble",
        "--disable-sync",
        "--disable-features=PasswordManagerOnboarding,AutofillServerCommunication",
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
    ]

    proc = subprocess.Popen(args)

    for _ in range(30):
        if is_chrome_debug_running(port):
            return proc
        time.sleep(0.5)

    raise ChromeAttachError(f"Chrome launched but did not respond on port {port} within 15s")


def get_driver(port: int) -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    return driver


def get_capture_driver(user_data_dir: str) -> webdriver.Chrome:
    """Launch a dedicated Chrome with CDP performance logging enabled.

    Unlike get_driver() (which *attaches* to a running debug Chrome via
    debuggerAddress — where performance logging is unreliable), this LAUNCHES
    its own Chrome so `driver.get_log("performance")` reliably surfaces
    Network.requestWillBeSent events. Used to scrape the cookie + nkparam
    headers off Naukri's search XHR. The browser runs visibly so any login /
    bot-check the user must complete is interactive.
    """
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    write_local_profile_preferences(user_data_dir)

    options = Options()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-save-password-bubble")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    return driver


def ensure_chrome_running(port: int, user_data_dir: str) -> webdriver.Chrome:
    ensure_matching_chrome_profile(port, user_data_dir)

    if not is_chrome_debug_running(port):
        launch_chrome_debug(port, user_data_dir)

    ensure_chrome_page_target(port)

    try:
        return get_driver(port)
    except WebDriverException as exc:
        logger.warning("Chrome attach failed once; opening a fresh page target and retrying: %s", exc)
        ensure_chrome_page_target(port)
        try:
            return get_driver(port)
        except WebDriverException as retry_exc:
            raise ChromeAttachError(f"Could not attach Selenium to Chrome on port {port}: {retry_exc}") from retry_exc
