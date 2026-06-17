import logging
import re
from urllib.parse import quote_plus
import requests

from ..base_platform import JobListing, JobDetails
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


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
    company_logo_url = job_data.get("logoPath", "") or job_data.get("logoPathV3", "")
    
    # Posted date
    posted_date = job_data.get("footerPlaceholderLabel", "")
    
    return JobDetails(
        job_description=job_description,
        key_skills=key_skills,
        experience_required=experience_required,
        salary=salary,
        about_company="",
        posted_date=posted_date,
        applicants_count="",
        openings="",
        company_logo_url=company_logo_url,
        company_name=company_name,
    )


def search_jobs_api(
    keywords: list[str],
    location: str,
    max_jobs: int,
    rate_limiter: RateLimiter,
    experience: int = None,
) -> list[JobListing]:
    """Search jobs using Naukri API instead of Selenium."""
    listings: list[JobListing] = []
    seen_urls: set = set()
    
    page = 1
    while len(listings) < max_jobs:
        url = _build_search_url(keywords, location, page, experience, no_of_results=20)
        logger.info("Naukri API search page %d: %s", page, url)
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
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
