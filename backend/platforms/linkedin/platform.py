from ..base_platform import BasePlatform, JobListing, JobDetails, ApplicationResult
from . import login, search, job_scraper, apply


class LinkedInPlatform(BasePlatform):
    def check_login(self) -> bool:
        return login.check_login(self.driver)

    def login(self) -> None:
        login.login(self.driver, self.config.linkedin_userid, self.config.linkedin_password)

    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        return search.search_jobs(self.driver, keywords, location, max_jobs, self.rate_limiter)

    def get_job_description(self, listing: JobListing) -> str:
        return job_scraper.get_job_description(self.driver, listing, self.rate_limiter)

    def get_job_details(self, listing: JobListing) -> JobDetails:
        return job_scraper.get_job_details(self.driver, listing, self.rate_limiter)

    def apply_to_job(self, listing: JobListing, cv_data=None, llm=None) -> ApplicationResult:
        return apply.apply_to_job(self.driver, listing, self.rate_limiter, cv_data)
