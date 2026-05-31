import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing, ApplicationResult
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Regular Naukri apply button
SEL_APPLY_BTN        = "button[id='apply-button'], a[id='apply-button']"
SEL_APPLY_BTN_ALT    = "button[class*='apply-button'], a[class*='apply-button']"
# "Apply on company site" external button (from actual HTML)
SEL_EXTERNAL_BTN     = "button#company-site-button, button[class*='company-site-button']"
SEL_ALREADY_APPLIED  = "button[class*='already-applied'], span[class*='already-applied']"
SEL_APPLIED_SUCCESS  = "div[class*='apply-success'], div[class*='applied-banner'], span[class*='applied-message']"
SEL_CONFIRM_BTN      = "button.btn-primary, button[class*='confirm']"


def _capture_external_url(driver, rate_limiter: RateLimiter) -> str:
    """Click the external apply button, grab the new-tab URL, then close it."""
    original_handles = set(driver.window_handles)
    try:
        btn = driver.find_element(By.CSS_SELECTOR, SEL_EXTERNAL_BTN)
        driver.execute_script("arguments[0].click();", btn)
        rate_limiter.wait_page_load()
        new_handles = set(driver.window_handles) - original_handles
        if new_handles:
            new_tab = new_handles.pop()
            driver.switch_to.window(new_tab)
            url = driver.current_url
            driver.close()
            driver.switch_to.window(list(original_handles)[0])
            return url
    except Exception as e:
        logger.debug("Could not capture external URL: %s", e)
    return ""


def apply_to_job(driver, listing: JobListing, rate_limiter: RateLimiter) -> ApplicationResult:
    # Skip navigation if get_job_details() already loaded this page
    if driver.current_url.split("?")[0].rstrip("/") != listing.url.rstrip("/"):
        driver.get(listing.url)
        rate_limiter.wait_page_load()

    # Check if already applied
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_ALREADY_APPLIED)
        logger.info("Already applied: %s", listing.title)
        return ApplicationResult(success=False, status="skipped", error="already_applied")
    except NoSuchElementException:
        pass

    # Detect "Apply on company site" button → external ATS
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_EXTERNAL_BTN)
        logger.info("External apply detected: %s", listing.title)
        external_url = _capture_external_url(driver, rate_limiter)
        return ApplicationResult(
            success=False,
            status="skipped_external",
            error="external_apply",
            external_url=external_url,
        )
    except NoSuchElementException:
        pass

    # Find the regular apply button
    apply_btn = None
    for sel in [SEL_APPLY_BTN, SEL_APPLY_BTN_ALT]:
        try:
            candidate = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn_text = candidate.text.lower()
            if "company site" in btn_text or "external" in btn_text:
                continue
            apply_btn = candidate
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
            logger.info("Applied (no success indicator): %s @ %s", listing.title, listing.company)
            return ApplicationResult(success=True, status="applied")

    except Exception as e:
        logger.error("Error applying to %s: %s", listing.title, e)
        return ApplicationResult(success=False, status="error", error=str(e))
