import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass
class Config:
    naukri_userid: str
    naukri_password: str
    linkedin_userid: str
    linkedin_password: str
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_deployment_name: str
    confidence_threshold: int
    port_num: int
    chrome_user_data_dir: str
    cv_path: str
    log_path: str
    max_jobs_per_hour: int
    max_jobs_per_day: int
    job_target: int
    location: str
    platform_choice: str


def load_config() -> Config:
    load_dotenv()

    def require(key: str) -> str:
        val = os.getenv(key, "").strip()
        if not val:
            raise ConfigError(f"Missing required environment variable: {key}")
        return val

    def optional_int(key: str, default: int) -> int:
        val = os.getenv(key, "").strip()
        if not val:
            return default
        try:
            return int(val)
        except ValueError:
            raise ConfigError(f"{key} must be an integer, got: {val!r}")

    base_dir = Path(__file__).parent.parent

    def resolve_path(key: str, default: str) -> str:
        raw = os.getenv(key, default).strip()
        p = Path(raw)
        if not p.is_absolute():
            p = base_dir / p
        return str(p)

    return Config(
        naukri_userid=require("NAUKRI_USERID"),
        naukri_password=require("NAUKRI_PASSWORD"),
        linkedin_userid=require("LINKEDIN_USERID"),
        linkedin_password=require("LINKEDIN_PASSWORD"),
        azure_openai_endpoint=require("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=require("AZURE_OPENAI_API_KEY"),
        azure_deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o-mini").strip(),
        confidence_threshold=optional_int("CONFIDENCE_THRESHOLD", 75),
        port_num=optional_int("PORT_NUM", 9222),
        chrome_user_data_dir=resolve_path("CHROME_USER_DATA_DIR", "./chrome_profile"),
        cv_path=resolve_path("CV_PATH", "./cv/resume.pdf"),
        log_path=resolve_path("LOG_PATH", "./logs/applications.json"),
        max_jobs_per_hour=optional_int("MAX_JOBS_PER_HOUR", 30),
        max_jobs_per_day=optional_int("MAX_JOBS_PER_DAY", 150),
        job_target=optional_int("JOB_TARGET", 10),
        location=os.getenv("LOCATION", "India").strip(),
        platform_choice=os.getenv("PLATFORM_CHOICE", "naukri").strip(),
    )
