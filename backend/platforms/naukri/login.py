import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from ..base_platform import LoginError

logger = logging.getLogger(__name__)

NAUKRI_HOME = "https://www.naukri.com/mnjuser/homepage"
NAUKRI_LOGIN = "https://www.naukri.com/nlogin/login"
NAUKRI_PROFILE = "https://www.naukri.com/mnjuser/profile"

LOGIN_URL_PART = "nlogin/login"

USERNAME_ID = "usernameField"
PASSWORD_ID = "passwordField"


def wait_for_page_load(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def _page_text(driver) -> str:
    try:
        return driver.execute_script("return document.body ? document.body.innerText : ''") or ""
    except Exception:
        return ""


def _has_logged_out_markers(driver) -> bool:
    current_url = driver.current_url.lower()
    if LOGIN_URL_PART in current_url:
        return True

    text = _page_text(driver).lower()
    logged_out_phrases = (
        "login to apply",
        "register to apply",
        "login to view",
        "register to unlock",
    )
    if any(phrase in text for phrase in logged_out_phrases):
        return True

    return bool(driver.execute_script("""
        const visible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.display !== 'none' && style.visibility !== 'hidden' &&
                   rect.width > 0 && rect.height > 0;
        };
        const authButtons = Array.from(document.querySelectorAll('a, button, span, div'))
            .filter(visible)
            .map((el) => (el.innerText || '').trim().toLowerCase())
            .filter(Boolean);
        return authButtons.some((text) => text === 'login' || text === 'register');
    """))


def _has_logged_in_markers(driver) -> bool:
    return bool(driver.execute_script("""
        const selectors = [
            'div.name-wrapper',
            '[class*="name-wrapper"]',
            '[class*="user-name"]',
            '[class*="userName"]',
            '[class*="profile"] [class*="name"]',
            'a[href*="/mnjuser/profile"]',
            'a[href*="/mnjuser/homepage"]'
        ];
        return selectors.some((selector) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
                   rect.width > 0 && rect.height > 0;
        });
    """))


def _configured_user_visible(driver, expected_userid: str) -> bool:
    expected = (expected_userid or "").strip().lower()
    if not expected:
        return True

    for url in (NAUKRI_HOME, NAUKRI_PROFILE):
        try:
            if driver.current_url.split("?")[0].rstrip("/") != url.rstrip("/"):
                driver.get(url)
                wait_for_page_load(driver)
                time.sleep(1)
            if expected in _page_text(driver).lower():
                return True
        except Exception as exc:
            logger.debug("Could not verify configured Naukri user on %s: %s", url, exc)

    return False


def clear_naukri_session(driver) -> None:
    try:
        driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
    except Exception:
        pass
    for origin in ("https://www.naukri.com", "https://login.naukri.com"):
        try:
            driver.execute_cdp_cmd(
                "Storage.clearDataForOrigin",
                {"origin": origin, "storageTypes": "cookies,local_storage,session_storage,indexeddb,cache_storage"},
            )
        except Exception:
            pass
    try:
        driver.get("https://www.naukri.com")
        driver.delete_all_cookies()
    except Exception:
        pass


def check_login(driver, expected_userid: str = "") -> bool:
    """
    Returns True if user is already logged in.
    Returns False if redirected to login page.
    """

    try:
        driver.get(NAUKRI_HOME)

        wait_for_page_load(driver)

        # Wait a bit for potential redirect
        time.sleep(3)

        current_url = driver.current_url

        logger.info("Current URL: %s", current_url)

        if _has_logged_out_markers(driver):
            logger.info("Logged-out markers found - not logged in")
            return False

        # Check for login form - if present, definitely not logged in
        try:
            username_field = driver.find_element(By.ID, USERNAME_ID)
            if username_field and username_field.is_displayed():
                logger.info("Login form found - not logged in")
                return False
        except:
            pass

        # Double-check URL after another wait
        time.sleep(2)
        current_url = driver.current_url
        if LOGIN_URL_PART in current_url:
            logger.info("Redirected to login page (after wait) - not logged in")
            return False

        if _has_logged_out_markers(driver):
            logger.info("Logged-out markers found after wait - not logged in")
            return False

        if _has_logged_in_markers(driver):
            if _configured_user_visible(driver, expected_userid):
                logger.info("Found logged-in profile markers for configured Naukri user")
                return True
            logger.warning("Browser is logged into a different Naukri account than configured")
            return False

        logger.info("Logged-in profile markers not found - not logged in")
        return False

    except Exception as e:
        logger.error("Login check failed: %s", e)
        return False


def login(driver, userid: str, password: str) -> None:
    """
    Login to Naukri using username/password.
    """

    try:
        if not userid or not password:
            raise LoginError("Naukri email and password are required.")

        if check_login(driver, userid):
            logger.info("Already logged in")
            return

        logger.info("Login required")
        clear_naukri_session(driver)
        driver.get(NAUKRI_LOGIN)
        wait_for_page_load(driver)

        # Username field
        username_field = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, USERNAME_ID))
        )

        username_field.clear()
        username_field.send_keys(userid)

        logger.info("Username entered")

        # Password field
        password_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, PASSWORD_ID))
        )

        password_field.clear()
        password_field.send_keys(password)

        logger.info("Password entered")

        # Login button
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[type='submit']")
            )
        )

        login_button.click()

        logger.info("Login button clicked")

        # Wait for redirect away from login page
        WebDriverWait(driver, 30).until(
            lambda d: LOGIN_URL_PART not in d.current_url.lower()
        )

        logger.info("Redirect detected")

        if not check_login(driver, userid):
            driver.save_screenshot("naukri_login_failed.png")
            raise LoginError(
                "Login unsuccessful. Naukri did not show the configured account after login."
            )

        logger.info("Login successful")

    except TimeoutException:

        driver.save_screenshot("naukri_login_timeout.png")

        raise LoginError(
            "Timed out while attempting to login."
        )

    except Exception as e:

        driver.save_screenshot("naukri_login_error.png")

        raise LoginError(
            f"Login failed: {str(e)}"
        )
