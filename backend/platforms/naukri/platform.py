from ..base_platform import BasePlatform, JobListing, JobDetails, ApplicationResult
from . import login, search, job_scraper, apply
from . import api_search


class NaukriPlatform(BasePlatform):
    name = "naukri"

    def check_login(self) -> bool:
        if self.driver is None:
            # API mode doesn't need login check
            return True
        return login.check_login(self.driver, self.config.naukri_userid)

    def login(self) -> None:
        if self.driver is None:
            # API mode doesn't need login
            return
        login.login(self.driver, self.config.naukri_userid, self.config.naukri_password)

    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        # Use API search mode if configured
        if getattr(self.config, 'naukri_search_mode', 'selenium') == 'api':
            return _search_each_keyword(
                lambda kw, limit: api_search.search_jobs_api(
                    [kw], location, limit, self.rate_limiter
                ),
                keywords,
                max_jobs,
            )
        # Default to Selenium-based search
        if self.driver is None:
            raise RuntimeError("Selenium mode requires driver, but driver is None")
        return _search_each_keyword(
            lambda kw, limit: search.search_jobs(self.driver, [kw], location, limit, self.rate_limiter),
            keywords,
            max_jobs,
        )

    def get_job_description(self, listing: JobListing) -> str:
        if self.driver is None:
            # API mode: use description from listing
            return listing.raw_snippet or ""
        return job_scraper.get_job_description(self.driver, listing, self.rate_limiter)

    def get_job_details(self, listing: JobListing) -> JobDetails:
        # In API mode, parse details from the listing's raw data
        if getattr(self.config, 'naukri_search_mode', 'selenium') == 'api' and self.driver is None:
            # For API mode, we need to parse from the listing data
            # The API search already populates some details in the listing
            # We'll use a simplified version for now
            return JobDetails(
                job_description=listing.raw_snippet or "",
                key_skills=[],
                experience_required="",
                salary="",
                about_company="",
                posted_date="",
                applicants_count="",
                openings="",
                company_logo_url="",
                company_name=listing.company or "",
            )
        return job_scraper.get_job_details(self.driver, listing, self.rate_limiter)

    def apply_to_job(self, listing: JobListing, cv_data=None, llm=None) -> ApplicationResult:
        if self.driver is None:
            raise RuntimeError("Cannot apply in API mode (no browser)")
        return apply.apply_to_job(self.driver, listing, self.rate_limiter, cv_data=cv_data, llm=llm)


def _search_each_keyword(search_one, keywords: list[str], max_jobs: int) -> list[JobListing]:
    clean_keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
    if not clean_keywords:
        clean_keywords = ["software developer"]

    merged: list[JobListing] = []
    seen: set[str] = set()
    per_keyword = max(max_jobs, 1)
    for keyword in clean_keywords:
        for listing in search_one(keyword, per_keyword):
            if len(merged) >= max_jobs:
                continue
            key = (listing.url or "").strip().lower()
            if not key:
                key = f"{(listing.company or '').strip().lower()}::{(listing.title or '').strip().lower()}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(listing)
    return merged[:max_jobs]
