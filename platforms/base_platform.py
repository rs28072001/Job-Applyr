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
class ApplicationResult:
    success: bool
    status: str = "applied"
    error: str = None


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

    @abstractmethod
    def apply_to_job(self, listing: JobListing) -> ApplicationResult:
        pass

    def ensure_logged_in(self) -> None:
        # Skip login check - assume user is already logged in
        self.login()
        return
