import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing, JobDetails
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_JOB_DESC = "div.job-desc, div[class*='job-desc'], div[id='job-description-wrapper'], div.jd-container, div[class*='jd-desc'], section[class*='job-desc']"
SEL_SKILLS_TAG = "a.chip, a[class*='chip'], span[class*='skill'], div[class*='skill']"
SEL_SHOW_MORE = "a[class*='show-more'], button[class*='show-more'], button[class*='expand']"
SEL_EXPERIENCE = "span[class*='exp'], div[class*='exp-wrap'] span, div.exp span, li[class*='expwanted'] span"
SEL_ABOUT_COMPANY = "div.comp-info-detail, div[class*='company-overview'], div[class*='about-company'], section[class*='company-info']"


def get_job_details(driver, listing: JobListing, rate_limiter: RateLimiter) -> JobDetails:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass

    # Extract job description
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

    # Click show more if present
    try:
        for selector in SEL_SHOW_MORE.split(", "):
            try:
                show_more = driver.find_element(By.CSS_SELECTOR, selector)
                driver.execute_script("arguments[0].click();", show_more)
                rate_limiter.wait()
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

    description = desc_el.text.strip() if desc_el else (listing.raw_snippet or listing.title)

    # Extract key skills
    key_skills = []
    try:
        for selector in SEL_SKILLS_TAG.split(", "):
            try:
                skill_tags = driver.find_elements(By.CSS_SELECTOR, selector)
                if skill_tags:
                    key_skills = [t.text.strip() for t in skill_tags if t.text.strip()]
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Append skills to description so LLM has richer context
    if key_skills:
        description += f"\n\nRequired Skills: {', '.join(key_skills)}"

    # Extract experience required
    experience_required = ""
    try:
        for selector in SEL_EXPERIENCE.split(", "):
            try:
                exp_el = driver.find_element(By.CSS_SELECTOR, selector)
                text = exp_el.text.strip()
                if text:
                    experience_required = text
                    break
            except NoSuchElementException:
                continue
    except Exception:
        pass

    # Extract about company
    about_company = ""
    try:
        for selector in SEL_ABOUT_COMPANY.split(", "):
            try:
                comp_el = driver.find_element(By.CSS_SELECTOR, selector)
                text = comp_el.text.strip()
                if text and len(text) > 20:
                    about_company = text
                    break
            except NoSuchElementException:
                continue
    except Exception:
        pass

    return JobDetails(
        job_description=description or listing.title,
        key_skills=key_skills,
        experience_required=experience_required,
        about_company=about_company,
    )


def get_job_description(driver, listing: JobListing, rate_limiter: RateLimiter) -> str:
    return get_job_details(driver, listing, rate_limiter).job_description
