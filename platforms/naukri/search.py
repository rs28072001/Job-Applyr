import logging
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.base_platform import JobListing
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEL_JOB_CARD  = "article.jobTuple, div[class*='srp-jobtuple'], div[class*='job-tuple'], div[class*='jobTuple']"
SEL_TITLE     = "a[class*='title'], a[class*='jobTitle'], h2[class*='title'] a"
SEL_COMPANY   = "a[class*='comp-name'], span[class*='comp-name'], a[class*='company-name'], span[class*='company-name'], a.subTitle"
SEL_LOCATION  = "span[class*='locWdth'], span[class*='location'], li[class*='location'] span, span[class*='loc']"
SEL_NEXT_PAGE = "a[class*='next'], button[aria-label='Next']"


def _parse_card(card, platform="naukri") -> JobListing | None:
    try:
        title_el = card.find_element(By.CSS_SELECTOR, SEL_TITLE)
        title = title_el.text.strip()
        url = title_el.get_attribute("href") or ""

        try:
            company = card.find_element(By.CSS_SELECTOR, SEL_COMPANY).text.strip()
        except NoSuchElementException:
            company = "Unknown"

        try:
            location = card.find_element(By.CSS_SELECTOR, SEL_LOCATION).text.strip()
        except NoSuchElementException:
            location = ""

        if not title or not url:
            return None

        return JobListing(
            title=title,
            company=company,
            location=location,
            url=url.split("?")[0],
            platform=platform,
        )
    except NoSuchElementException:
        return None


def search_jobs(
    driver,
    keywords: list[str],
    location: str,
    max_jobs: int,
    rate_limiter: RateLimiter,
) -> list[JobListing]:
    listings: list[JobListing] = []
    seen_urls: set = set()
    keyword = quote_plus(keywords[0] if keywords else "software developer")
    loc = quote_plus(location)

    page = 1
    while len(listings) < max_jobs:
        # Use Naukri search with query parameters
        url = f"https://www.naukri.com/jobs?k={keyword}&l={loc}"
        if page > 1:
            url += f"&pg={page}"
        logger.info("Naukri search page %d: %s", page, url)
        driver.get(url)
        rate_limiter.wait_page_load()

        # Wait for page to load
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("Page load timeout on page %d", page)

        # Try to find job cards with multiple selectors
        cards = []
        for selector in [SEL_JOB_CARD, "article.jobTuple", "div[class*='job-tuple']", "div[class*='jobTuple']"]:
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    logger.info("Found %d cards using selector: %s", len(cards), selector)
                    break
            except Exception:
                continue

        if not cards:
            logger.info("No job cards found on page %d, stopping search", page)
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

        logger.info("Found %d new listings on page %d (total: %d)", new_count, page, len(listings))

        if new_count == 0:
            break

        # Check for next page
        try:
            driver.find_element(By.CSS_SELECTOR, SEL_NEXT_PAGE)
        except NoSuchElementException:
            break

        page += 1
        rate_limiter.wait()

    return listings[:max_jobs]
