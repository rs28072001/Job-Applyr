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
    ai_provider: str
    openai_api_key: str
    openai_model: str
    gemini_api_key: str
    gemini_model: str
    groq_api_key: str
    groq_model: str
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
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
    naukri_search_mode: str = "selenium"   # selenium | api
    # API-mode auth: pasted from a logged-in browser (DevTools > search request)
    naukri_cookie: str = ""                 # full `cookie` header value
    naukri_nkparam: str = ""                # `nkparam` header value
    # Safer-automation controls
    easy_apply_only: bool = True            # platform-native apply flows only
    include_external_review: bool = True    # external jobs → manual review queue
    outreach_mode: str = "draft_only"       # off | draft_only | send_after_approval
    hide_previously_skipped: bool = True
    auto_ignore_skipped: bool = True
    date_posted_filter: str = "any"         # any | 24h | 3d | 7d | 14d


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

    # Desktop app sets SJA_BASE_DIR to a writable per-user data directory;
    # otherwise fall back to the backend checkout directory.
    _env_base = os.getenv("SJA_BASE_DIR", "").strip()
    base_dir = Path(_env_base) if _env_base else Path(__file__).parent.parent

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
        ai_provider=os.getenv("AI_PROVIDER", "azure").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b").strip(),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
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
        naukri_search_mode=os.getenv("NAUKRI_SEARCH_MODE", "selenium").strip(),
    )
