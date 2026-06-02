import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from platforms.base_platform import LoginError
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

NAUKRI_HOME = "https://www.naukri.com"
LOGIN_URL = "https://www.naukri.com/nlogin/login"

SEL_EMAIL = "input[id='usernameField']"
SEL_PASSWORD = "input[id='passwordField']"
SEL_SUBMIT = "button[type='submit']"
SEL_LOGGED_IN = "div.nI-gNb-icon__image, a[class*='nI-gNb-log']"


def check_login(driver) -> bool:
    try:
        driver.get(NAUKRI_HOME)
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_LOGGED_IN))
        )
        return True
    except TimeoutException:
        return False
    except Exception:
        # If driver crashes or any other error, assume not logged in
        return False


def login(driver, userid: str, password: str) -> None:
    logger.info("Skipping login check - assuming user is already logged in to Naukri.")
    logger.info("If you're not logged in, please log in manually in the Chrome browser.")
    return
