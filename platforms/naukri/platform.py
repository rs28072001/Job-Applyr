from platforms.base_platform import BasePlatform, JobListing, ApplicationResult
from platforms.naukri import login, search, job_scraper, apply


class NaukriPlatform(BasePlatform):
    def check_login(self) -> bool:
        return login.check_login(self.driver)

    def login(self) -> None:
        login.login(self.driver, self.config.naukri_userid, self.config.naukri_password)

    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        return search.search_jobs(self.driver, keywords, location, max_jobs, self.rate_limiter)

    def get_job_description(self, listing: JobListing) -> str:
        return job_scraper.get_job_description(self.driver, listing, self.rate_limiter)

    def apply_to_job(self, listing: JobListing, cv_data=None) -> ApplicationResult:
        return apply.apply_to_job(self.driver, listing, self.rate_limiter)
