import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing, JobDetails
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Selectors derived from actual Naukri JD page HTML
SEL_COMPANY_NAME   = "div[class*='jd-header-comp-name'] a"
SEL_COMPANY_LOGO   = "img[class*='jhc__comp-banner']"
SEL_EXPERIENCE     = "div[class*='jhc__exp'] span"
SEL_SALARY         = "div[class*='jhc__salary'] span"
SEL_JOB_HIGHLIGHTS = "ul[class*='job-highlight-list'] li"
SEL_JOB_DESC       = "div[class*='JDC__dang-inner-html'], section[class*='job-desc-container']"
SEL_KEY_SKILLS     = "div[class*='key-skill'] a span, div[class*='key-skill'] a"
SEL_STATS          = "div[class*='jd-stats'] span[class*='stat']"
SEL_ABOUT_COMPANY  = "div[class*='comp-info-detail'], div[class*='about-company'], section[class*='company-info']"
SEL_EXTERNAL_BTN   = "button#company-site-button, button[class*='company-site-button']"


def _get_text(driver, selector: str, default: str = "") -> str:
    try:
        el = driver.find_element(By.CSS_SELECTOR, selector)
        return el.text.strip() or default
    except NoSuchElementException:
        return default


def _get_attr(driver, selector: str, attr: str, default: str = "") -> str:
    try:
        el = driver.find_element(By.CSS_SELECTOR, selector)
        return el.get_attribute(attr) or default
    except NoSuchElementException:
        return default


def get_job_details(driver, listing: JobListing, rate_limiter: RateLimiter) -> JobDetails:
    driver.get(listing.url)
    rate_limiter.wait_page_load()

    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass

    # Wait for the main job description to appear before scraping anything
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_JOB_DESC))
        )
    except TimeoutException:
        logger.warning("Job description not found for: %s", listing.url)

    # Company name (JD page is more reliable than search card)
    company_name = _get_text(driver, SEL_COMPANY_NAME, listing.company)

    # Company logo
    company_logo_url = _get_attr(driver, SEL_COMPANY_LOGO, "src")

    # Experience and salary
    experience_required = _get_text(driver, SEL_EXPERIENCE)
    salary = _get_text(driver, SEL_SALARY)

    # Job highlights (bullet list at top of JD)
    job_highlights = []
    try:
        highlight_els = driver.find_elements(By.CSS_SELECTOR, SEL_JOB_HIGHLIGHTS)
        job_highlights = [el.text.strip() for el in highlight_els if el.text.strip()]
    except Exception:
        pass

    # Full job description text
    description = listing.raw_snippet or listing.title
    try:
        desc_el = driver.find_element(By.CSS_SELECTOR, SEL_JOB_DESC)
        text = desc_el.text.strip()
        if text:
            description = text
    except NoSuchElementException:
        pass

    # Key skills from the dedicated skills section
    key_skills = []
    try:
        skill_els = driver.find_elements(By.CSS_SELECTOR, SEL_KEY_SKILLS)
        key_skills = [el.text.strip() for el in skill_els if el.text.strip()]
    except Exception:
        pass

    # Append skills to description so LLM has richer context
    if key_skills:
        description += f"\n\nKey Skills: {', '.join(key_skills)}"

    # Stats: Posted date, openings, applicants
    posted_date = ""
    openings = ""
    applicants_count = ""
    try:
        stat_els = driver.find_elements(By.CSS_SELECTOR, SEL_STATS)
        for stat in stat_els:
            try:
                label = stat.find_element(By.CSS_SELECTOR, "label").text.strip().lower()
                spans = stat.find_elements(By.CSS_SELECTOR, "span")
                value = spans[-1].text.strip() if spans else ""
                if "posted" in label:
                    posted_date = value
                elif "opening" in label:
                    openings = value
                elif "applicant" in label:
                    applicants_count = value
            except Exception:
                continue
    except Exception:
        pass

    # About company (optional section, not always present)
    about_company = _get_text(driver, SEL_ABOUT_COMPANY)

    return JobDetails(
        job_description=description,
        key_skills=key_skills,
        job_highlights=job_highlights,
        experience_required=experience_required,
        salary=salary,
        about_company=about_company,
        posted_date=posted_date,
        applicants_count=applicants_count,
        openings=openings,
        company_logo_url=company_logo_url,
        company_name=company_name,
    )


def get_job_description(driver, listing: JobListing, rate_limiter: RateLimiter) -> str:
    return get_job_details(driver, listing, rate_limiter).job_description
