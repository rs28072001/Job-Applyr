import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_DESCRIPTION = "div[class*='description__text'], div[class*='jobs-description__content'], div[class*='show-more-less-html__markup']"
SEL_SHOW_MORE = "button[aria-label='Show more, visually expands previously read content'], button[class*='show-more-less-html__button']"
SEL_JOB_TITLE_HEADING = "h1[class*='job-title'], h1[class*='jobs-unified-top-card__job-title']"


def get_job_description(driver, listing: JobListing, rate_limiter: RateLimiter) -> str:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    # Expand description if collapsed
    try:
        show_more = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_SHOW_MORE))
        )
        driver.execute_script("arguments[0].click();", show_more)
        rate_limiter.wait_page_load()
    except TimeoutException:
        pass

    try:
        desc_el = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_DESCRIPTION))
        )
        description = desc_el.text.strip()
        if description:
            return description
    except TimeoutException:
        pass

    logger.warning("Job description not found for: %s", listing.url)
    return listing.raw_snippet or listing.title
