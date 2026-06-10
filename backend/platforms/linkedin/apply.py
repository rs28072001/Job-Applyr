import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

from ..base_platform import JobListing, ApplicationResult
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_EASY_APPLY_BTN = "button[class*='jobs-apply-button'], button[aria-label*='Easy Apply']"
SEL_MODAL = "div[class*='jobs-easy-apply-modal'], div[class*='artdeco-modal']"
SEL_NEXT_BTN = "button[aria-label='Continue to next step']"
SEL_REVIEW_BTN = "button[aria-label='Review your application']"
SEL_SUBMIT_BTN = "button[aria-label='Submit application']"
SEL_CLOSE_BTN = "button[aria-label='Dismiss'], button[data-test-modal-close-btn]"
SEL_ALREADY_APPLIED = "span[class*='artdeco-inline-feedback__message']"
SEL_ERROR_MSG = "p[class*='jobs-easy-apply-form-element__error']"
SEL_PHONE_FIELD = "input[id*='phoneNumber'], input[aria-label*='Phone']"
SEL_TEXT_FIELDS = "input[class*='artdeco-text-input--input'], textarea[class*='jobs-easy-apply']"
SEL_SELECT_FIELDS = "select[class*='artdeco-select__select']"
SEL_RADIO_YES = "label[for*='Yes'], input[type='radio'][value*='Yes']"


def _fill_generic_fields(driver, cv_data=None) -> None:
    """Fill common form fields with sensible defaults."""
    # Phone number
    try:
        phone_fields = driver.find_elements(By.CSS_SELECTOR, SEL_PHONE_FIELD)
        for field in phone_fields:
            if not field.get_attribute("value"):
                phone = cv_data.phone if cv_data and cv_data.phone else "0000000000"
                field.clear()
                field.send_keys(phone)
    except Exception:
        pass

    # Numeric/experience fields — fill with experience years if empty
    try:
        text_fields = driver.find_elements(By.CSS_SELECTOR, SEL_TEXT_FIELDS)
        for field in text_fields:
            if not field.get_attribute("value"):
                label = field.get_attribute("aria-label") or field.get_attribute("id") or ""
                label_lower = label.lower()
                if any(kw in label_lower for kw in ["year", "experience", "exp"]):
                    years = str(int(cv_data.experience_years)) if cv_data else "3"
                    field.send_keys(years)
                elif "city" in label_lower or "location" in label_lower:
                    pass  # Skip location fields
    except Exception:
        pass

    # Select fields — pick first non-empty option
    try:
        selects = driver.find_elements(By.CSS_SELECTOR, SEL_SELECT_FIELDS)
        from selenium.webdriver.support.ui import Select
        for sel_el in selects:
            sel = Select(sel_el)
            if sel.first_selected_option.get_attribute("value") == "":
                options = [o for o in sel.options if o.get_attribute("value")]
                if options:
                    sel.select_by_index(1)
    except Exception:
        pass


def apply_to_job(
    driver, listing: JobListing, rate_limiter: RateLimiter, cv_data=None
) -> ApplicationResult:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    # Check already applied
    try:
        msg_el = driver.find_element(By.CSS_SELECTOR, SEL_ALREADY_APPLIED)
        if "applied" in msg_el.text.lower():
            return ApplicationResult(success=False, status="skipped", error="already_applied")
    except NoSuchElementException:
        pass

    # Find Easy Apply button
    try:
        apply_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_EASY_APPLY_BTN))
        )
    except TimeoutException:
        return ApplicationResult(success=False, status="error", error="Easy Apply button not found")

    try:
        driver.execute_script("arguments[0].click();", apply_btn)
        rate_limiter.wait_page_load()

        # Wait for modal
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_MODAL))
        )

        # Navigate multi-step modal
        max_steps = 10
        for step in range(max_steps):
            _fill_generic_fields(driver, cv_data)
            rate_limiter.wait_page_load()

            # Try Review button first (last step before submit)
            try:
                review_btn = driver.find_element(By.CSS_SELECTOR, SEL_REVIEW_BTN)
                driver.execute_script("arguments[0].click();", review_btn)
                rate_limiter.wait_page_load()
                break
            except NoSuchElementException:
                pass

            # Try Next button
            try:
                next_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_NEXT_BTN))
                )
                driver.execute_script("arguments[0].click();", next_btn)
                rate_limiter.wait_page_load()
                continue
            except TimeoutException:
                pass

            # Try Submit directly (single-step apply)
            try:
                driver.find_element(By.CSS_SELECTOR, SEL_SUBMIT_BTN)
                break
            except NoSuchElementException:
                pass

            break

        # Submit
        try:
            submit_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_SUBMIT_BTN))
            )
            driver.execute_script("arguments[0].click();", submit_btn)
            rate_limiter.wait_page_load()
        except TimeoutException:
            return ApplicationResult(success=False, status="error", error="Submit button not found")

        # Close confirmation modal
        try:
            close = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_CLOSE_BTN))
            )
            close.click()
        except TimeoutException:
            pass

        logger.info("Applied successfully (LinkedIn): %s @ %s", listing.title, listing.company)
        return ApplicationResult(success=True, status="applied")

    except Exception as e:
        # Try to close modal on error
        try:
            close = driver.find_element(By.CSS_SELECTOR, SEL_CLOSE_BTN)
            close.click()
        except Exception:
            pass
        logger.error("LinkedIn apply error for %s: %s", listing.title, e)
        return ApplicationResult(success=False, status="error", error=str(e))
