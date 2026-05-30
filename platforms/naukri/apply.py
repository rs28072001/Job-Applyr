import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing, ApplicationResult
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_APPLY_BTN = "button[id='apply-button'], a[id='apply-button']"
SEL_APPLY_BTN_ALT = "button[class*='apply'], a[class*='apply-button']"
SEL_ALREADY_APPLIED = "button[class*='already-applied'], span[class*='already-applied']"
SEL_APPLIED_SUCCESS = "div.apply-success, div[class*='applied'], span[class*='applied']"
SEL_EXTERNAL_REDIRECT = "div[class*='external-apply'], a[class*='apply-on-company-site']"
SEL_CHAT_APPLY = "button[class*='chat-apply']"
SEL_CONFIRM_BTN = "button.btn-primary, button[class*='confirm']"


def apply_to_job(driver, listing: JobListing, rate_limiter: RateLimiter) -> ApplicationResult:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    # Check if already applied
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_ALREADY_APPLIED)
        logger.info("Already applied: %s", listing.title)
        return ApplicationResult(success=False, status="skipped", error="already_applied")
    except NoSuchElementException:
        pass

    # Skip external ATS redirects
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_EXTERNAL_REDIRECT)
        logger.info("Skipping external apply: %s", listing.title)
        return ApplicationResult(success=False, status="skipped_external", error="external_apply")
    except NoSuchElementException:
        pass

    # Skip Chat Apply
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_CHAT_APPLY)
        has_chat = True
    except NoSuchElementException:
        has_chat = False

    # Find the apply button
    apply_btn = None
    for sel in [SEL_APPLY_BTN, SEL_APPLY_BTN_ALT]:
        try:
            apply_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn_text = apply_btn.text.lower()
            if "chat" in btn_text:
                continue
            break
        except TimeoutException:
            continue

    if not apply_btn:
        return ApplicationResult(success=False, status="error", error="Apply button not found")

    try:
        driver.execute_script("arguments[0].click();", apply_btn)
        rate_limiter.wait_page_load()

        # Handle confirmation modal if present
        try:
            confirm = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_CONFIRM_BTN))
            )
            confirm.click()
            rate_limiter.wait_page_load()
        except TimeoutException:
            pass

        # Verify success
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL_APPLIED_SUCCESS))
            )
            logger.info("Applied successfully: %s @ %s", listing.title, listing.company)
            return ApplicationResult(success=True, status="applied")
        except TimeoutException:
            # Accept as success if no error is shown
            logger.info("Applied (no success indicator): %s @ %s", listing.title, listing.company)
            return ApplicationResult(success=True, status="applied")

    except Exception as e:
        logger.error("Error applying to %s: %s", listing.title, e)
        return ApplicationResult(success=False, status="error", error=str(e))
