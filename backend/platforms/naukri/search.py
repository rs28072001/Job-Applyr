import logging
import re
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base_platform import JobListing
from ...utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Naukri renders via React — cards appear with a data-job-id attribute.
# This is far more stable than hashed CSS class names.
SEL_CARD      = "[data-job-id]"
SEL_TITLE     = "a[class*='title'], a[class*='jobTitle']"
SEL_COMPANY   = "a[class*='comp-name'], span[class*='comp-name'], a[class*='company-name'], span[class*='company-name']"
SEL_LOCATION  = "span[class*='locWdth'], span[class*='loc'], span[class*='location'], li[class*='location'] span"
SEL_NEXT_PAGE = "a[class*='next-btn'], a[aria-label='Next Page'], button[aria-label='Next']"


def _slugify(text: str) -> str:
    """Convert 'QA Engineer' → 'qa-engineer' for SEO-friendly Naukri URLs."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_card(card) -> JobListing | None:
    """Extract job details from a single card element via JavaScript
    (avoids StaleElementReference on React re-renders)."""
    try:
        data = card.parent.execute_script("""
            const c = arguments[0];
            const titleEl  = c.querySelector('a[class*="title"], a[class*="jobTitle"]');
            const compEl   = c.querySelector('a[class*="comp-name"], span[class*="comp-name"], a[class*="company-name"], span[class*="company-name"]');
            const locEl    = c.querySelector('span[class*="locWdth"], span[class*="loc"], span[class*="location"]');
            return {
                title:    titleEl  ? titleEl.innerText.trim()        : '',
                url:      titleEl  ? titleEl.href                    : '',
                company:  compEl   ? compEl.innerText.trim()         : '',
                location: locEl    ? locEl.innerText.trim()          : '',
                job_id:   c.getAttribute('data-job-id') || ''
            };
        """, card)
    except Exception as e:
        logger.debug("JS card extraction failed: %s", e)
        return None

    title = data.get("title", "").strip()
    url   = data.get("url", "").split("?")[0].strip()

    if not title or not url or "naukri.com" not in url:
        return None

    return JobListing(
        title=title,
        company=data.get("company", "") or "Unknown",
        location=data.get("location", ""),
        url=url,
        platform="naukri",
    )


def search_jobs(
    driver,
    keywords: list[str],
    location: str,
    max_jobs: int,
    rate_limiter: RateLimiter,
) -> list[JobListing]:
    listings: list[JobListing] = []
    seen_urls: set = set()

    keyword_raw = keywords[0] if keywords else "software developer"
    keyword_slug = _slugify(keyword_raw)
    loc_slug = _slugify(location)
    # Naukri SEO URL — same page the user manually sees
    base_url = f"https://www.naukri.com/{keyword_slug}-jobs-in-{loc_slug}"

    page = 1
    while len(listings) < max_jobs:
        url = base_url if page == 1 else f"{base_url}-{page}"
        logger.info("Naukri search page %d: %s", page, url)
        driver.get(url)

        # Wait for React to render at least one job card (up to 15 s)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL_CARD))
            )
        except TimeoutException:
            logger.warning("No job cards rendered on page %d — stopping", page)
            break

        cards = driver.find_elements(By.CSS_SELECTOR, SEL_CARD)
        logger.info("Found %d raw cards on page %d", len(cards), page)

        new_count = 0
        for card in cards:
            listing = _parse_card(card)
            if listing and listing.url not in seen_urls:
                seen_urls.add(listing.url)
                listings.append(listing)
                new_count += 1
                if len(listings) >= max_jobs:
                    break

        logger.info("Parsed %d new listings on page %d (total: %d)", new_count, page, len(listings))

        if new_count == 0 or len(listings) >= max_jobs:
            break

        # Check for next page button before incrementing
        try:
            driver.find_element(By.CSS_SELECTOR, SEL_NEXT_PAGE)
        except NoSuchElementException:
            break

        page += 1
        rate_limiter.wait()

    return listings[:max_jobs]
