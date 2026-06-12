import logging
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base_platform import JobListing
from core.date_filters import linkedin_time_filter
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_JOB_CARD = "li[class*='jobs-search-results__list-item'], div[data-job-id]"
SEL_TITLE = "a[class*='job-card-list__title'], a[class*='job-card-container__link']"
SEL_COMPANY = "span[class*='job-card-container__company-name'], div[class*='artdeco-entity-lockup__subtitle']"
SEL_LOCATION = "li[class*='job-card-container__metadata-item']"
SEL_NEXT_PAGE = "button[aria-label='View next page'], li[class*='artdeco-pagination__indicator--number'][aria-current='true'] + li button"


def _parse_card(card, platform="linkedin") -> JobListing | None:
    try:
        title_el = card.find_element(By.CSS_SELECTOR, SEL_TITLE)
        title = title_el.text.strip()
        url = title_el.get_attribute("href") or ""

        if not title or not url:
            return None

        try:
            company = card.find_element(By.CSS_SELECTOR, SEL_COMPANY).text.strip()
        except NoSuchElementException:
            company = "Unknown"

        try:
            location = card.find_element(By.CSS_SELECTOR, SEL_LOCATION).text.strip()
        except NoSuchElementException:
            location = ""

        # Normalize URL to job view URL
        if "linkedin.com/jobs/view/" not in url:
            try:
                job_id = card.get_attribute("data-job-id") or card.get_attribute("data-entity-urn")
                if job_id:
                    job_id = job_id.split(":")[-1]
                    url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            except Exception:
                pass

        clean_url = url.split("?")[0].rstrip("/") + "/"

        return JobListing(
            title=title,
            company=company,
            location=location,
            url=clean_url,
            platform=platform,
        )
    except NoSuchElementException:
        return None


def build_search_url(
    keywords: list[str],
    location: str,
    easy_apply_only: bool = True,
    date_posted_filter: str = "any",
) -> str:
    """Build the LinkedIn jobs search URL.

    When easy_apply_only is True (the default) the platform's own Easy Apply
    filter (f_LF=f_AL) is applied so only platform-native applications are
    returned — no external ATS redirects.
    """
    keyword = quote_plus(keywords[0] if keywords else "software developer")
    loc = quote_plus(location)
    url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={loc}"
    if easy_apply_only:
        url += "&f_LF=f_AL"  # LinkedIn Easy Apply platform filter
    time_filter = linkedin_time_filter(date_posted_filter)
    if time_filter:
        url += f"&f_TPR={time_filter}"
    return url


def search_jobs(
    driver,
    keywords: list[str],
    location: str,
    max_jobs: int,
    rate_limiter: RateLimiter,
    easy_apply_only: bool = True,
    date_posted_filter: str = "any",
) -> list[JobListing]:
    listings: list[JobListing] = []
    seen_urls: set = set()

    base_url = build_search_url(keywords, location, easy_apply_only, date_posted_filter)

    page = 0
    while len(listings) < max_jobs:
        url = f"{base_url}&start={page * 25}"
        logger.info("LinkedIn search page %d: %s", page + 1, url)
        driver.get(url)
        rate_limiter.wait_page_load()

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL_JOB_CARD))
            )
        except TimeoutException:
            logger.info("No job cards on LinkedIn page %d, stopping", page + 1)
            break

        cards = driver.find_elements(By.CSS_SELECTOR, SEL_JOB_CARD)
        if not cards:
            break

        new_count = 0
        for card in cards:
            listing = _parse_card(card)
            if listing and listing.url not in seen_urls:
                seen_urls.add(listing.url)
                listings.append(listing)
                new_count += 1
                if len(listings) >= max_jobs:
                    break

        logger.info("Found %d new listings on page %d (total: %d)", new_count, page + 1, len(listings))

        if new_count == 0:
            break

        page += 1
        rate_limiter.wait()

    return listings[:max_jobs]
