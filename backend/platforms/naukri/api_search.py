import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import requests

from ..base_platform import JobListing, JobDetails
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)

# Naukri's job-search API is gated behind reCAPTCHA Enterprise — an invisible
# token minted by JS in a real browser. A plain HTTP client can't produce it,
# so API mode reuses the `cookie` + `nkparam` headers the user pastes from a
# logged-in browser session (DevTools > the `search` request > Headers). These
# static headers mirror the rest of that browser request.
_SEARCH_HEADERS = {
    "accept": "application/json",
    "accept-language": "en-GB,en;q=0.9",
    "appid": "109",
    "clientid": "d3skt0p",
    "content-type": "application/json",
    "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
    "systemid": "Naukri",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": _USER_AGENT,
}


class NaukriAPIAuthError(Exception):
    """Raised when API-mode auth tokens (cookie / nkparam) are missing."""


class NaukriRecaptchaError(Exception):
    """Raised when Naukri's search API demands a reCAPTCHA token.

    Means the pasted cookie/nkparam are stale or invalid. The user must paste
    fresh values from a logged-in browser.
    """


def build_session(cookie: str, nkparam: str) -> requests.Session:
    """Build a requests.Session pre-loaded with the browser-pasted auth headers.

    `cookie` and `nkparam` come from a logged-in Naukri browser session and are
    what get the search API past its bot-protection. Raises NaukriAPIAuthError
    if either is missing so API mode fails loudly instead of returning 0 jobs.
    """
    if not cookie or not cookie.strip():
        raise NaukriAPIAuthError(
            "Naukri API mode needs a Cookie. Paste it from your browser "
            "(DevTools > Network > the 'search' request > Headers > cookie)."
        )
    if not nkparam or not nkparam.strip():
        raise NaukriAPIAuthError(
            "Naukri API mode needs an nkparam value. Paste it from your browser "
            "(DevTools > Network > the 'search' request > Headers > nkparam)."
        )

    session = requests.Session()
    session.headers.update(_SEARCH_HEADERS)
    session.headers["cookie"] = cookie.strip()
    session.headers["nkparam"] = nkparam.strip()
    return session


def _epoch_ms_to_ist(ms) -> str:
    """Convert Naukri's epoch-millis `createdDate` to a readable IST string."""
    if not ms:
        return ""
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=IST)
        return dt.strftime("%d %b %Y, %I:%M %p IST")
    except (ValueError, TypeError, OSError):
        return ""


def _slugify(text: str) -> str:
    """Convert 'QA Engineer' → 'qa-engineer' for SEO-friendly Naukri URLs."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _build_search_url(
    keywords: list[str],
    location: str,
    page: int = 1,
    experience: int = None,
    no_of_results: int = 20
) -> str:
    """Build Naukri API search URL."""
    keyword_raw = keywords[0] if keywords else "software developer"
    keyword_slug = _slugify(keyword_raw)
    loc_slug = _slugify(location)
    
    # Build the keyword parameter (comma-separated)
    keyword_param = quote_plus(keyword_raw)
    location_param = quote_plus(location)
    
    # Build SEO key
    seo_key = f"{keyword_slug}-jobs-in-{loc_slug}"
    if page > 1:
        seo_key = f"{seo_key}-{page}"
    
    base_url = "https://www.naukri.com/jobapi/v3/search"
    params = [
        f"noOfResults={no_of_results}",
        "urlType=search_by_key_loc",
        "searchType=adv",
        f"location={location_param}",
        f"keyword={keyword_param}",
        f"pageNo={page}",
        f"k={keyword_param}",
        f"l={location_param}",
        f"seoKey={seo_key}",
        "src=jobsearchDesk",
        "latLong=",
    ]
    
    if experience is not None:
        params.append(f"experience={experience}")
    
    return f"{base_url}?{'&'.join(params)}"


def _parse_api_job(job_data: dict) -> JobListing | None:
    """Parse a single job from API response to JobListing."""
    try:
        title = job_data.get("title", "").strip()
        company = job_data.get("companyName", "").strip()
        jd_url = job_data.get("jdURL", "").strip()
        
        if not title or not company:
            return None
        
        # Build full URL if jdURL is relative
        if jd_url and not jd_url.startswith("http"):
            url = f"https://www.naukri.com{jd_url}"
        else:
            url = jd_url
        
        # Extract location from placeholders
        location = ""
        placeholders = job_data.get("placeholders", [])
        for ph in placeholders:
            if ph.get("type") == "location":
                location = ph.get("label", "")
                break
        
        return JobListing(
            title=title,
            company=company,
            location=location,
            url=url,
            platform="naukri",
            raw_snippet=job_data.get("jobDescription", ""),
            raw_data=job_data,  # full record → rich details without a 2nd request
        )
    except Exception as e:
        logger.debug("Failed to parse API job: %s", e)
        return None


def _parse_api_job_details(job_data: dict) -> JobDetails:
    """Parse full job details from API response."""
    # Extract experience
    experience_text = job_data.get("experienceText", "")
    min_exp = job_data.get("minimumExperience", "")
    max_exp = job_data.get("maximumExperience", "")
    if min_exp and max_exp:
        experience_required = f"{min_exp}-{max_exp} Yrs"
    else:
        experience_required = experience_text
    
    # Extract salary
    salary_detail = job_data.get("salaryDetail", {})
    if salary_detail.get("hideSalary"):
        salary = "Not disclosed"
    else:
        min_sal = salary_detail.get("minimumSalary", 0)
        max_sal = salary_detail.get("maximumSalary", 0)
        if min_sal and max_sal:
            # Convert to Lakhs if in INR
            currency = salary_detail.get("currency", "INR")
            if currency == "INR":
                salary = f"{min_sal//100000}-{max_sal//100000} Lacs PA"
            else:
                salary = f"{min_sal}-{max_sal} {currency}"
        else:
            salary = "Not disclosed"
    
    # Extract skills
    tags_and_skills = job_data.get("tagsAndSkills", "")
    key_skills = [s.strip() for s in tags_and_skills.split(",") if s.strip()] if tags_and_skills else []
    
    # Extract job description
    job_description = job_data.get("jobDescription", "")
    
    # Append skills to description for better context
    if key_skills:
        job_description += f"\n\nKey Skills: {', '.join(key_skills)}"
    
    # Company info
    company_name = job_data.get("companyName", "")
    company_logo_url = (
        job_data.get("logoPathV3", "") or job_data.get("logoPath", "")
    )

    # Company review data (AmbitionBox) — kept as structured fields for the UI.
    abox = job_data.get("ambitionBoxData") or {}
    rating = str(abox.get("AggregateRating") or "").strip()
    reviews_count = str(abox.get("ReviewsCount") or "").strip()
    company_url = (
        job_data.get("staticUrl", "") or abox.get("Url", "")
    ).strip()

    # About company — best-effort from AmbitionBox rating + consultant hiring info
    about_bits = []
    if rating:
        about_bits.append(f"AmbitionBox rating {rating}"
                          + (f" ({reviews_count} reviews)" if reviews_count else ""))
    if job_data.get("consultant") and job_data.get("hiringFor"):
        about_bits.append(f"Hiring for {job_data['hiringFor']}")
    about_company = " · ".join(about_bits)

    # Posted date — combine the relative label with the exact IST timestamp so
    # the date-posted filter still parses it ("2 Days Ago") while the dashboard
    # can show the precise time.
    relative = job_data.get("footerPlaceholderLabel", "")
    ist = _epoch_ms_to_ist(job_data.get("createdDate"))
    if relative and ist:
        posted_date = f"{relative} ({ist})"
    else:
        posted_date = relative or ist

    # Openings (vacancy count, when present)
    vacancy = job_data.get("vacancy")
    openings = str(vacancy) if vacancy else ""

    return JobDetails(
        job_description=job_description,
        key_skills=key_skills,
        experience_required=experience_required,
        salary=salary,
        about_company=about_company,
        posted_date=posted_date,
        applicants_count="",
        openings=openings,
        company_logo_url=company_logo_url,
        company_name=company_name,
        rating=rating,
        reviews_count=reviews_count,
        company_url=company_url,
    )


def search_jobs_api(
    keywords: list[str],
    location: str,
    max_jobs: int,
    rate_limiter: RateLimiter,
    experience: int = None,
    session: requests.Session = None,
) -> list[JobListing]:
    """Search jobs using Naukri API instead of Selenium.

    `session` must be a session from build_session() carrying the browser-pasted
    cookie + nkparam. Without valid tokens Naukri returns a reCAPTCHA challenge
    (NaukriRecaptchaError) — the user then needs to paste fresh values.
    """
    if session is None:
        logger.error("Naukri API search called without a session.")
        return []

    listings: list[JobListing] = []
    seen_urls: set = set()

    page = 1
    while len(listings) < max_jobs:
        url = _build_search_url(keywords, location, page, experience, no_of_results=20)
        # Browsers send a referer matching the human search page; mirror it.
        referer = _build_search_url(keywords, location, page, experience).replace(
            "https://www.naukri.com/jobapi/v3/search?", "https://www.naukri.com/"
        )
        logger.info("Naukri API search page %d: %s", page, url)

        try:
            response = session.get(url, headers={"referer": referer}, timeout=30)
            # Naukri returns 406 + {"message":"recaptcha required"} when the
            # pasted cookie/nkparam are stale or invalid.
            if response.status_code == 406 and "recaptcha" in response.text.lower():
                raise NaukriRecaptchaError(
                    "Naukri rejected the API request (reCAPTCHA). The pasted "
                    "Cookie / nkparam are likely expired — open Naukri in your "
                    "browser, copy fresh values into Job Preferences, and retry."
                )
            response.raise_for_status()
            data = response.json()
        except NaukriRecaptchaError:
            raise
        except Exception as e:
            logger.error("Failed to fetch Naukri API page %d: %s", page, e)
            break
        
        job_details = data.get("jobDetails", [])
        logger.info("Found %d jobs on API page %d", len(job_details), page)
        
        new_count = 0
        for job_data in job_details:
            listing = _parse_api_job(job_data)
            if listing and listing.url not in seen_urls:
                seen_urls.add(listing.url)
                listings.append(listing)
                new_count += 1
                if len(listings) >= max_jobs:
                    break
        
        logger.info("Parsed %d new listings from API page %d (total: %d)", new_count, page, len(listings))
        
        if new_count == 0 or len(listings) >= max_jobs:
            break
        
        page += 1
        rate_limiter.wait()
    
    return listings[:max_jobs]


def get_job_details_api(job_data: dict) -> JobDetails:
    """Get job details from API response data."""
    return _parse_api_job_details(job_data)
