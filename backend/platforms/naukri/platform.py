from ..base_platform import BasePlatform, JobListing, JobDetails, ApplicationResult, LoginError
from . import login, search, job_scraper, apply
from . import api_search


class NaukriPlatform(BasePlatform):
    name = "naukri"

    def __init__(self, driver, config, rate_limiter):
        super().__init__(driver, config, rate_limiter)
        self._api_session = None   # requests.Session built from pasted tokens
        self._current_raw = {}     # raw API record of the job being processed

    def _is_api_mode(self) -> bool:
        return getattr(self.config, 'naukri_search_mode', 'selenium') == 'api'

    def collect_page_signals(self):
        # API mode has no live page — synthesize signals from the API record so
        # the classifier routes correctly (Naukri-internal jobs get scored;
        # company-site jobs are saved as external).
        if self._is_api_mode() and self.driver is None:
            from core.page_signals import PageSignals
            raw = self._current_raw or {}
            is_external = bool(raw.get("companyApplyJob"))
            return PageSignals(
                platform=self.name,
                url=raw.get("jdURL", ""),
                has_internal_apply=not is_external,
                has_external_apply=is_external,
            )
        return super().collect_page_signals()

    def check_login(self) -> bool:
        if self.driver is None:
            # API mode: report "logged in" only once we hold an authenticated
            # session, so ensure_logged_in() triggers login() to create one.
            if self._is_api_mode():
                return self._api_session is not None
            return True
        return login.check_login(self.driver, self.config.naukri_userid)

    def login(self) -> None:
        if self.driver is None:
            # API mode: build a session from the browser-pasted cookie + nkparam
            # (anonymous search is reCAPTCHA-gated, so these tokens are required).
            if self._is_api_mode():
                try:
                    self._api_session = api_search.build_session(
                        getattr(self.config, "naukri_cookie", ""),
                        getattr(self.config, "naukri_nkparam", ""),
                    )
                except api_search.NaukriAPIAuthError as e:
                    raise LoginError(str(e)) from e
            return
        login.login(self.driver, self.config.naukri_userid, self.config.naukri_password)

    def search_jobs(self, keywords: list[str], location: str, max_jobs: int) -> list[JobListing]:
        # Use API search mode if configured
        if self._is_api_mode():
            if self._api_session is None:
                # Defensive: ensure we have a session built from pasted tokens.
                self._api_session = api_search.build_session(
                    getattr(self.config, "naukri_cookie", ""),
                    getattr(self.config, "naukri_nkparam", ""),
                )
            return _search_each_keyword(
                lambda kw, limit: api_search.search_jobs_api(
                    [kw], location, limit, self.rate_limiter,
                    session=self._api_session,
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
        # API mode: every job's full record is already on the listing — parse
        # rich details (skills, salary, experience, logo, IST posted date) with
        # no extra request.
        if self._is_api_mode() and self.driver is None:
            # Remember this job's raw record for collect_page_signals(), which
            # the pipeline calls right after this in the same iteration.
            self._current_raw = listing.raw_data or {}
            if listing.raw_data:
                return api_search.get_job_details_api(listing.raw_data)
            return JobDetails(
                job_description=listing.raw_snippet or "",
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
