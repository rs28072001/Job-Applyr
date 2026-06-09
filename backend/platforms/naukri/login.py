import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

NAUKRI_HOME = "https://www.naukri.com/mnjuser/homepage"

LOGIN_URL_PART = "nlogin/login"

USERNAME_ID = "usernameField"
PASSWORD_ID = "passwordField"


class LoginError(Exception):
    pass


def wait_for_page_load(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def check_login(driver) -> bool:
    """
    Returns True if user is already logged in.
    Returns False if redirected to login page.
    """

    try:
        driver.get(NAUKRI_HOME)

        wait_for_page_load(driver)

        # Wait a bit for potential redirect
        import time
        time.sleep(3)

        current_url = driver.current_url

        logger.info("Current URL: %s", current_url)

        # If redirected to login page, not logged in
        if "nlogin/login" in current_url:
            logger.info("Redirected to login page - not logged in")
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
        if "nlogin/login" in current_url:
            logger.info("Redirected to login page (after wait) - not logged in")
            return False

        # Check for name-wrapper element (indicates logged in)
        try:
            name_wrapper = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.name-wrapper"))
            )
            if name_wrapper and name_wrapper.is_displayed():
                logger.info("Found name-wrapper element - logged in")
                return True
        except:
            pass

        logger.info("Name-wrapper not found - not logged in")
        return False

    except Exception as e:
        logger.error("Login check failed: %s", e)
        return False


def login(driver, userid: str, password: str) -> None:
    """
    Login to Naukri using username/password.
    """

    try:
        logger.info("Opening Naukri homepage")

        driver.get(NAUKRI_HOME)

        wait_for_page_load(driver)

        current_url = driver.current_url.lower()

        logger.info("Current URL: %s", current_url)

        # Already authenticated
        if LOGIN_URL_PART not in current_url:
            logger.info("Already logged in")
            return

        logger.info("Login required")

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

        # Final verification
        driver.get(NAUKRI_HOME)

        wait_for_page_load(driver)

        final_url = driver.current_url.lower()

        logger.info("Final URL: %s", final_url)

        if LOGIN_URL_PART in final_url:

            driver.save_screenshot("naukri_login_failed.png")

            raise LoginError(
                "Login unsuccessful. Still redirected to login page."
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