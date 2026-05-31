from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LoginError(Exception):
    pass


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    platform: str
    raw_snippet: str = ""


@dataclass
class JobDetails:
    job_description: str
    key_skills: list = field(default_factory=list)
    experience_required: str = ""
    salary: str = ""
    about_company: str = ""
    posted_date: str = ""
    applicants_count: str = ""
    openings: str = ""
    company_logo_url: str = ""
    company_name: str = ""


@dataclass
class ApplicationResult:
    success: bool
    status: str = "applied"
    error: str = None
    external_url: str = None


class BasePlatform(ABC):
    def __init__(self, driver, config, rate_limiter):
        self.driver = driver
        self.config = config
        self.rate_limiter = rate_limiter

    @abstractmethod
    def check_login(self) -> bool:
        pass

    @abstractmethod
    def login(self) -> None:
        pass

    @abstractmethod
    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        pass

    @abstractmethod
    def get_job_description(self, listing: JobListing) -> str:
        pass

    def get_job_details(self, listing: JobListing) -> JobDetails:
        return JobDetails(job_description=self.get_job_description(listing))

    @abstractmethod
    def apply_to_job(self, listing: JobListing) -> ApplicationResult:
        pass

    def ensure_logged_in(self) -> None:
        # Skip login check - assume user is already logged in
        self.login()
        return
