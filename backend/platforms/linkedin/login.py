import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from platforms.base_platform import LoginError
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

LINKEDIN_HOME = "https://www.linkedin.com"
LOGIN_URL = "https://www.linkedin.com/login"

SEL_EMAIL = "input[id='username']"
SEL_PASSWORD = "input[id='password']"
SEL_SUBMIT = "button[type='submit']"
SEL_LOGGED_IN = "div[data-control-name='nav.homepage'], a[href='/feed/'], div.global-nav__me"


def check_login(driver) -> bool:
    try:
        driver.get(LINKEDIN_HOME)
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_LOGGED_IN))
        )
        return True
    except TimeoutException:
        return False


def login(driver, userid: str, password: str) -> None:
    logger.info("Skipping login check - assuming user is already logged in to LinkedIn.")
    logger.info("If you're not logged in, please log in manually in the Chrome browser.")
    return
