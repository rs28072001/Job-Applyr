from ..base_platform import BasePlatform, JobListing, JobDetails, ApplicationResult
from . import login, search, job_scraper, apply


class LinkedInPlatform(BasePlatform):
    name = "linkedin"

    def check_login(self) -> bool:
        return login.check_login(self.driver)

    def login(self) -> None:
        login.login(self.driver, self.config.linkedin_userid, self.config.linkedin_password)

    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        easy_apply_only = bool(getattr(self.config, "easy_apply_only", True))
        date_posted_filter = getattr(self.config, "date_posted_filter", "any")
        return _search_each_keyword(
            lambda kw, limit: search.search_jobs(
                self.driver, [kw], location, limit, self.rate_limiter,
                easy_apply_only=easy_apply_only,
                date_posted_filter=date_posted_filter,
            ),
            keywords,
            max_jobs,
        )

    def get_job_description(self, listing: JobListing) -> str:
        return job_scraper.get_job_description(self.driver, listing, self.rate_limiter)

    def get_job_details(self, listing: JobListing) -> JobDetails:
        return job_scraper.get_job_details(self.driver, listing, self.rate_limiter)

    def apply_to_job(self, listing: JobListing, cv_data=None, llm=None) -> ApplicationResult:
        return apply.apply_to_job(self.driver, listing, self.rate_limiter, cv_data)


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
