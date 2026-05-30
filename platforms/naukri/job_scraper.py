import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_JOB_DESC = "div.job-desc, div[class*='job-desc'], div[id='job-description-wrapper'], div.jd-container, div[class*='jd-desc'], section[class*='job-desc']"
SEL_SKILLS_TAG = "a.chip, a[class*='chip'], span[class*='skill'], div[class*='skill']"
SEL_SHOW_MORE = "a[class*='show-more'], button[class*='show-more'], button[class*='expand']"


def get_job_description(driver, listing: JobListing, rate_limiter: RateLimiter) -> str:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    # Wait for page to load
    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass

    # Try multiple selectors for job description
    desc_el = None
    for selector in SEL_JOB_DESC.split(", "):
        try:
            desc_el = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            logger.info("Found job description using selector: %s", selector)
            break
        except TimeoutException:
            continue

    if not desc_el:
        logger.warning("Job description not found for: %s", listing.url)
        return listing.raw_snippet or listing.title

    # Click show more if present
    try:
        for selector in SEL_SHOW_MORE.split(", "):
            try:
                show_more = driver.find_element(By.CSS_SELECTOR, selector)
                driver.execute_script("arguments[0].click();", show_more)
                rate_limiter.wait()
                # Re-find description element after expanding
                for desc_selector in SEL_JOB_DESC.split(", "):
                    try:
                        desc_el = driver.find_element(By.CSS_SELECTOR, desc_selector)
                        break
                    except NoSuchElementException:
                        continue
                break
            except NoSuchElementException:
                continue
    except Exception:
        pass

    description = desc_el.text.strip()

    # Append skills tags for richer LLM context
    try:
        for selector in SEL_SKILLS_TAG.split(", "):
            try:
                skill_tags = driver.find_elements(By.CSS_SELECTOR, selector)
                if skill_tags:
                    skills_text = ", ".join(tag.text.strip() for tag in skill_tags if tag.text.strip())
                    if skills_text:
                        description += f"\n\nRequired Skills: {skills_text}"
                    break
            except Exception:
                continue
    except Exception:
        pass

    return description or listing.title
