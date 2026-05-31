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
SEL_JOB_DESC       = "div[class*='JDC__dang-inner-html'], section[class*='job-desc-container']"
SEL_KEY_SKILLS     = "div[class*='key-skill'] a span, div[class*='key-skill'] a"
SEL_STATS          = "div[class*='jd-stats'] span[class*='stat']"
SEL_ABOUT_COMPANY  = "div[class*='comp-info-detail'], div[class*='about-company'], section[class*='company-info'], div[class*='aboutCompany'], div[class*='about_company']"
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

    # Wait for the main job description — this is the only blocking wait
    try:
        WebDriverWait(driver, 6).until(
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
        stats_data = driver.execute_script("""
            const result = {posted_date: '', openings: '', applicants_count: ''};
            // Try structured stat items first
            const stats = document.querySelectorAll('div[class*="jd-stats"] span[class*="stat"], div[class*="jd-stats"] li, div[class*="stats"] span');
            for (const s of stats) {
                const text = s.innerText.toLowerCase();
                const label = (s.querySelector('label,span[class*="label"]') || {innerText:''}).innerText.toLowerCase();
                const key = label || text;
                // find the "value" — last span child or direct text
                const valueEl = s.querySelectorAll('span');
                const value = valueEl.length ? valueEl[valueEl.length-1].innerText.trim() : s.innerText.trim();
                if (key.includes('posted') || key.includes('post')) result.posted_date = result.posted_date || value;
                if (key.includes('opening')) result.openings = result.openings || value;
                if (key.includes('applicant')) result.applicants_count = result.applicants_count || value;
            }
            // Fallback: scan all text on page for patterns
            if (!result.posted_date || !result.openings || !result.applicants_count) {
                const allText = document.body.innerText;
                const posted = allText.match(/Posted[:\\s]+(\\d+[^\\n]{0,20}ago|\\d{1,2}[\\/ ]\\w+[\\/ ]\\d{2,4})/i);
                if (posted && !result.posted_date) result.posted_date = posted[1].trim();
                const openings_m = allText.match(/(\\d+)\\s+Opening/i);
                if (openings_m && !result.openings) result.openings = openings_m[1];
                const applicants_m = allText.match(/(\\d+[\\+k]?)\\s+Applicant/i);
                if (applicants_m && !result.applicants_count) result.applicants_count = applicants_m[1];
            }
            return result;
        """)
        if stats_data:
            posted_date = stats_data.get("posted_date", "")
            openings = stats_data.get("openings", "")
            applicants_count = stats_data.get("applicants_count", "")
    except Exception:
        pass

    # About company — try CSS selectors first, then JS heading-search fallback
    about_company = _get_text(driver, SEL_ABOUT_COMPANY)
    if not about_company:
        try:
            about_company = driver.execute_script("""
                // Walk all headings looking for "about company" / "about us"
                const headings = document.querySelectorAll('h1,h2,h3,h4,span[class*="heading"],div[class*="heading"]');
                for (const h of headings) {
                    const txt = h.innerText.toLowerCase();
                    if (txt.includes('about company') || txt.includes('about us') || txt.includes('about the company')) {
                        // grab the next sibling container or parent's text
                        const parent = h.closest('section, div[class*="section"], div[class*="comp"]') || h.parentElement;
                        if (parent) return parent.innerText.trim().slice(0, 1000);
                    }
                }
                // Fallback: any element whose class contains "about"
                const el = document.querySelector('[class*="about"]');
                return el ? el.innerText.trim().slice(0, 1000) : '';
            """) or ""
        except Exception:
            pass

    return JobDetails(
        job_description=description,
        key_skills=key_skills,
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
