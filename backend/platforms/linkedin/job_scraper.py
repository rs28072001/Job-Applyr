import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base_platform import JobListing, JobDetails
from ...utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_DESCRIPTION = "div[class*='description__text'], div[class*='jobs-description__content'], div[class*='show-more-less-html__markup']"
SEL_SHOW_MORE = "button[aria-label='Show more, visually expands previously read content'], button[class*='show-more-less-html__button']"
SEL_CRITERIA_ITEM = "li[class*='job-criteria__item']"
SEL_CRITERIA_HEADER = "h3[class*='job-criteria__subheader']"
SEL_CRITERIA_TEXT = "span[class*='job-criteria__text']"
SEL_ABOUT_COMPANY = "div[class*='jobs-company__company-description'], section[data-test-id='about-the-company'] p, div[class*='company-details-module'] p"


def get_job_details(driver, listing: JobListing, rate_limiter: RateLimiter) -> JobDetails:
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

    # Extract job description
    description = listing.raw_snippet or listing.title
    try:
        desc_el = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_DESCRIPTION))
        )
        text = desc_el.text.strip()
        if text:
            description = text
    except TimeoutException:
        logger.warning("Job description not found for: %s", listing.url)

    # Extract experience from job criteria (seniority / level)
    experience_required = ""
    try:
        criteria_items = driver.find_elements(By.CSS_SELECTOR, SEL_CRITERIA_ITEM)
        for item in criteria_items:
            try:
                header = item.find_element(By.CSS_SELECTOR, SEL_CRITERIA_HEADER).text.strip().lower()
                value = item.find_element(By.CSS_SELECTOR, SEL_CRITERIA_TEXT).text.strip()
                if any(kw in header for kw in ("seniority", "level", "experience")):
                    experience_required = value
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Extract about company
    about_company = ""
    try:
        for selector in SEL_ABOUT_COMPANY.split(", "):
            try:
                els = driver.find_elements(By.CSS_SELECTOR, selector.strip())
                text = " ".join(el.text.strip() for el in els if el.text.strip())
                if text and len(text) > 20:
                    about_company = text
                    break
            except Exception:
                continue
    except Exception:
        pass

    return JobDetails(
        job_description=description,
        key_skills=[],
        experience_required=experience_required,
        about_company=about_company,
    )


def get_job_description(driver, listing: JobListing, rate_limiter: RateLimiter) -> str:
    return get_job_details(driver, listing, rate_limiter).job_description
