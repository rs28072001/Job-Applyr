import logging
import os
import sys
import time
import subprocess
from pathlib import Path

import requests
from selenium import webdriver
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


def launch_chrome_debug(port: int, user_data_dir: str) -> subprocess.Popen:
    chrome_exe = get_chrome_executable()
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    args = [
        chrome_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
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


def ensure_chrome_running(port: int, user_data_dir: str) -> webdriver.Chrome:
    if not is_chrome_debug_running(port):
        launch_chrome_debug(port, user_data_dir)

    return get_driver(port)
