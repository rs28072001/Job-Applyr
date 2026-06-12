"""
Manages the single active job-search session.
Runs the blocking Selenium code in a ThreadPoolExecutor thread so FastAPI
stays responsive. Exposes start() / stop() / status.

Account-safe by design: no CAPTCHA bypass, no proxy rotation, no fingerprint
tricks. Conservative randomized delays, hourly/daily caps, dedupe against
history, and backoff + abort on challenge/error pages.
"""
import logging
import hashlib
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session")

# Shared mutable state (guarded by _lock)
_lock             = threading.Lock()
_stop_event:  Optional[threading.Event]  = None
_session_id:  Optional[int]              = None
_started_at:  Optional[datetime]         = None
_is_running:  bool                       = False
_driver:      Optional[object]            = None  # Selenium WebDriver

# Abort a platform loop after this many consecutive hard failures (backoff).
MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_SECONDS = 90


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def is_running() -> bool:
    return _is_running


def current_session_id() -> Optional[int]:
    return _session_id


def started_at() -> Optional[datetime]:
    return _started_at


def start(session_id: int, run_kwargs: dict) -> None:
    """Submit the session to the thread pool. Raises if already running."""
    global _stop_event, _session_id, _started_at, _is_running
    with _lock:
        if _is_running:
            raise RuntimeError("A session is already running")
        _stop_event = threading.Event()
        _session_id = session_id
        _started_at = datetime.now(timezone.utc)
        _is_running = True

    future = _executor.submit(
        _run_session_sync,
        session_id,
        run_kwargs,
        _stop_event,
    )
    future.add_done_callback(_on_done)


def stop() -> None:
    """Signal the running session to stop, close Chrome, and IMMEDIATELY
    persist 'stopped' on the session row and all in-flight application rows."""
    global _driver, _stop_event, _is_running, _session_id, _started_at
    session_id = None
    with _lock:
        session_id = _session_id
        if _stop_event:
            _stop_event.set()
        if _driver:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None
        _is_running = False
        _session_id = None
        _started_at = None

    if session_id:
        try:
            from api.database import SessionLocal
            from api.pipeline import mark_session_stopped
            db = SessionLocal()
            try:
                stopped_rows = mark_session_stopped(db, session_id)
                logger.info("Session %s stopped immediately (%d in-flight rows marked stopped)",
                            session_id, stopped_rows)
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to mark session %s stopped immediately", session_id)

        try:
            import core.tracker as tracker
            tracker._emit({"type": "session_stopped", "session_id": session_id})
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _on_done(future) -> None:
    global _is_running, _driver
    with _lock:
        _is_running = False
        _driver = None
    exc = future.exception()
    if exc:
        logger.error("Session thread raised: %s\n%s", exc,
                     "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _run_session_sync(session_id: int, kwargs: dict, stop_event: threading.Event) -> None:
    """
    Blocking entry point that runs inside the ThreadPoolExecutor thread.
    Builds all objects from DB rows (no .env), runs the job loop, writes
    results back to DB.
    """
    import sys, os
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from api.database import SessionLocal
    from api.models import Session as SessionModel, Config as ConfigModel, CVProfile
    from api.pipeline import finalize_session
    from config.settings import Config
    from core.chrome_manager import ensure_chrome_running, ChromeNotFoundError, ChromeAttachError
    from core.cv_parser import CVData
    from core.llm_provider import get_llm_settings, validate_llm_settings
    from core.llm_client import LLMClient
    import core.tracker as tracker
    from platforms.naukri.platform import NaukriPlatform
    from platforms.linkedin.platform import LinkedInPlatform
    from utils.rate_limiter import RateLimiter

    db = SessionLocal()
    try:
        db_cfg   = db.get(ConfigModel, 1)
        db_cv    = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
        db_sess  = db.get(SessionModel, session_id)

        if not db_cfg or not db_sess:
            logger.error("Session %s: missing config or session row", session_id)
            return

        def app_chrome_profile_dir() -> str:
            override = os.getenv("CHROME_USER_DATA_DIR", "").strip()
            if override:
                return override if os.path.isabs(override) else os.path.join(backend_dir, override)
            identity = (db_cfg.naukri_email or db_cfg.linkedin_email or "no-platform-account").strip().lower()
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
            return os.path.join(backend_dir, "data", "chrome_profiles", digest)

        easy_apply_only         = bool(kwargs.get("easy_apply_only",
                                       getattr(db_sess, "easy_apply_only", True)))
        include_external_review = bool(kwargs.get("include_external_review",
                                       getattr(db_sess, "include_external_review", True)))
        outreach_mode           = kwargs.get("outreach_mode",
                                       getattr(db_sess, "outreach_mode", None)) or "draft_only"
        hide_previously_skipped = bool(kwargs.get("hide_previously_skipped",
                                       getattr(db_sess, "hide_previously_skipped", True)))
        auto_ignore_skipped     = bool(kwargs.get("auto_ignore_skipped",
                                       getattr(db_sess, "auto_ignore_skipped", True)))
        date_posted_filter      = kwargs.get("date_posted_filter",
                                       getattr(db_sess, "date_posted_filter", None)) or "any"

        cfg = Config(
            naukri_userid       = db_cfg.naukri_email,
            naukri_password     = db_cfg.naukri_password,
            linkedin_userid     = db_cfg.linkedin_email,
            linkedin_password   = db_cfg.linkedin_password,
            azure_openai_endpoint    = db_cfg.azure_openai_endpoint,
            azure_openai_api_key     = db_cfg.azure_openai_api_key,
            azure_deployment_name    = db_cfg.azure_deployment_name or "gpt-4o-mini",
            ai_provider         = db_cfg.ai_provider or "azure",
            openai_api_key      = db_cfg.openai_api_key or "",
            openai_model        = db_cfg.openai_model or "gpt-4o-mini",
            gemini_api_key      = db_cfg.gemini_api_key or "",
            gemini_model        = db_cfg.gemini_model or "gemini-2.5-flash",
            groq_api_key        = db_cfg.groq_api_key or "",
            groq_model          = db_cfg.groq_model or "openai/gpt-oss-120b",
            openrouter_api_key  = db_cfg.openrouter_api_key or "",
            openrouter_model    = db_cfg.openrouter_model or "openai/gpt-oss-120b",
            openrouter_base_url = db_cfg.openrouter_base_url or "https://openrouter.ai/api/v1",
            confidence_threshold= kwargs.get("confidence_threshold", db_cfg.confidence_threshold),
            port_num            = db_cfg.port_num,
            chrome_user_data_dir= app_chrome_profile_dir(),
            cv_path             = db_cv.pdf_path if db_cv else "",
            log_path            = "./logs/applications.json",
            max_jobs_per_hour   = db_cfg.max_jobs_per_hour,
            max_jobs_per_day    = db_cfg.max_jobs_per_day,
            job_target          = kwargs.get("job_target", db_sess.job_target),
            location            = kwargs.get("location", db_sess.location),
            platform_choice     = kwargs.get("platform", db_sess.platform),
            easy_apply_only     = easy_apply_only,
            include_external_review = include_external_review,
            outreach_mode       = outreach_mode,
            hide_previously_skipped = hide_previously_skipped,
            auto_ignore_skipped = auto_ignore_skipped,
            date_posted_filter  = date_posted_filter,
        )

        if db_cv:
            cv_data = CVData(
                raw_text         = db_cv.raw_text or "",
                name             = db_cv.name or "",
                email            = db_cv.email or "",
                phone            = db_cv.phone or "",
                skills           = db_cv.skills or [],
                experience_years = db_cv.experience_years or 0.0,
                job_titles       = db_cv.job_titles or ["QA Engineer"],
                education        = db_cv.education or [],
                summary          = db_cv.summary or "",
            )
        else:
            cv_data = CVData(raw_text="", name="", email="", phone="", skills=[],
                             experience_years=0.0,
                             job_titles=kwargs.get("keywords", ["Software Engineer"]),
                             education=[], summary="")

        keywords = db_sess.keywords or cv_data.job_titles or ["Software Engineer"]

        logger.info("Session %s: Initializing tracker", session_id)
        import pathlib
        pathlib.Path("./logs").mkdir(parents=True, exist_ok=True)
        tracker.init_tracker("./logs")
        tracker.session_config(cfg)
        from core.audit import log_event
        log_event(db, session_id, "session_started", {
            "platform": cfg.platform_choice, "location": cfg.location,
            "job_target": cfg.job_target, "threshold": cfg.confidence_threshold,
            "easy_apply_only": cfg.easy_apply_only,
            "include_external_review": cfg.include_external_review,
            "outreach_mode": cfg.outreach_mode,
            "hide_previously_skipped": cfg.hide_previously_skipped,
            "auto_ignore_skipped": cfg.auto_ignore_skipped,
            "date_posted_filter": cfg.date_posted_filter,
            "max_jobs_per_day": cfg.max_jobs_per_day,
        })
        if cv_data.raw_text:
            tracker.cv_parsed(cv_data)

        logger.info("Session %s: Connecting to Chrome", session_id)
        global _driver
        try:
            driver = ensure_chrome_running(cfg.port_num, cfg.chrome_user_data_dir)
            with _lock:
                _driver = driver
            logger.info("Session %s: Chrome connected successfully", session_id)
        except (ChromeNotFoundError, ChromeAttachError) as e:
            logger.error("Session %s: Chrome connection failed: %s", session_id, e)
            tracker.get().error("[CHROME] Failed to connect: %s", e)
            tracker._emit({"type": "error", "msg": f"Chrome error: {e}"})
            finalize_session(db, session_id, stopped=False, failed=True)
            return

        rate_limiter = RateLimiter(max_per_hour=cfg.max_jobs_per_hour,
                                   max_per_day=cfg.max_jobs_per_day)

        platforms_to_run = []
        if cfg.platform_choice in ("naukri", "both"):
            platforms_to_run.append(("naukri",   NaukriPlatform(driver, cfg, rate_limiter)))
        if cfg.platform_choice in ("linkedin", "both"):
            platforms_to_run.append(("linkedin", LinkedInPlatform(driver, cfg, rate_limiter)))

        logger.info("Session %s: Initializing LLM client", session_id)
        llm_settings = get_llm_settings(cfg)
        validate_llm_settings(llm_settings)
        llm = LLMClient(llm_settings.base_url, llm_settings.api_key,
                        cv_data, llm_settings.model)
        logger.info("Session %s: LLM client initialized", session_id)

        applied_count = [0]
        mode   = kwargs.get("mode", db_sess.mode)
        # Search-only: use threshold 101 (nothing ever qualifies)
        threshold = 101 if mode == "search" else cfg.confidence_threshold

        for platform_name, platform in platforms_to_run:
            if stop_event.is_set() or applied_count[0] >= cfg.job_target:
                break
            _run_platform_db(
                platform=platform,
                platform_name=platform_name,
                cv_data=cv_data,
                llm=llm,
                keywords=keywords,
                location=cfg.location,
                job_target=cfg.job_target,
                threshold=threshold,
                rate_limiter=rate_limiter,
                session_id=session_id,
                db=db,
                stop_event=stop_event,
                applied_count=applied_count,
                settings=cfg,
            )

        finalize_session(db, session_id, stopped=stop_event.is_set())

        db_sess = db.get(SessionModel, session_id)
        tracker.session_end(db_sess.applied, cfg.job_target, db_sess.skipped, db_sess.errors)

    except Exception as exc:
        logger.error("Session %s crashed: %s\n%s", session_id, exc, traceback.format_exc())
        try:
            import core.tracker as tracker
            tracker._emit({"type": "error", "msg": str(exc), "traceback": traceback.format_exc()})
        except Exception:
            pass
        try:
            from api.pipeline import finalize_session
            finalize_session(db, session_id, stopped=False, failed=True)
        except Exception:
            pass
    finally:
        db.close()


def _run_platform_db(
    platform, platform_name, cv_data, llm, keywords, location,
    job_target, threshold, rate_limiter, session_id, db,
    stop_event, applied_count, settings,
) -> None:
    """Per-platform job loop with explicit lifecycle states.

    queued → fetching → (classification) → scoring → skipped | applying |
    manual_review | email_drafted → applied | failed | stopped
    """
    import core.tracker as tracker
    from api.models import Application
    from api.pipeline import (
        create_outreach_draft, daily_cap_reached, decide_apply,
        is_duplicate_company, refresh_session_counters, set_app_status,
    )
    from core.date_filters import is_within_posted_filter
    from core.ignored_jobs import find_ignored_job, maybe_auto_ignore
    from core.audit import log_event
    from core.evidence import capture_evidence
    from core.job_classifier import classify_job, route_classification
    from core.llm_client import JobScore
    from core.statuses import AppStatus, FailureReason, JobClassification
    from core.title_match import title_matches
    from platforms.base_platform import LoginError, JobDetails
    from utils.rate_limiter import RateLimitExceededError

    def _evidence(app):
        """Capture failure evidence; never breaks the run."""
        try:
            path = capture_evidence(platform.driver, app.id)
            if path:
                app.evidence_path = path
                db.commit()
        except Exception:
            pass

    # Login
    try:
        platform.ensure_logged_in()
        tracker.login_ok(platform_name)
        log_event(db, session_id, "login_ok", {"platform": platform_name})
    except LoginError as e:
        tracker.login_fail(platform_name, e)
        log_event(db, session_id, "login_failed", {"platform": platform_name, "error": str(e)})
        return

    # Search (LinkedIn applies the platform Easy Apply filter when enabled)
    max_fetch = min((job_target - applied_count[0]) * 5, 100)
    listings  = platform.search_jobs(keywords, location, max_fetch)
    tracker.search_results(platform_name, keywords, len(listings))

    if not listings:
        return

    consecutive_failures = 0
    seen_title_company: set[tuple[str, str]] = set()
    total = len(listings)
    for idx, listing in enumerate(listings, 1):
        if stop_event.is_set() or applied_count[0] >= job_target:
            break

        # Same-session dedupe: identical title+company (or url, handled below).
        tc_key = ((listing.title or "").strip().lower(),
                  (listing.company or "").strip().lower())
        if tc_key in seen_title_company:
            tracker.job_already_applied(f"{listing.title} (duplicate listing this session)")
            continue
        seen_title_company.add(tc_key)

        # Hard keyword targeting gate: unrelated platform/sponsored results
        # never become Application rows and never enter Ignored Jobs.
        if not title_matches(listing.title, keywords):
            log_event(db, session_id, "title_mismatch_discarded", {
                "platform": platform_name,
                "job_title": listing.title,
                "company": listing.company,
                "job_url": listing.url,
                "keywords": keywords,
            })
            tracker.job_already_applied(f"{listing.title} (title mismatch discarded)")
            continue

        # Hard daily apply cap from PERSISTED rows (survives restarts).
        if daily_cap_reached(db, settings.max_jobs_per_day):
            tracker.rate_limit(f"Daily apply cap ({settings.max_jobs_per_day}) reached — stopping platform loop")
            log_event(db, session_id, "daily_cap_reached",
                      {"max_per_day": settings.max_jobs_per_day})
            break

        # Human pacing between jobs.
        if idx > 1:
            rate_limiter.wait_between_jobs()
            if stop_event.is_set():
                break

        ignored = find_ignored_job(
            db,
            platform=platform_name,
            company=listing.company,
            title=listing.title,
            url=listing.url,
        )
        if ignored:
            if getattr(settings, "hide_previously_skipped", True):
                tracker.apply_result("skipped", listing.title,
                                     error=FailureReason.IGNORED_PREVIOUS_SKIP)
                continue
            app = Application(
                session_id=session_id, platform=platform_name,
                job_title=listing.title, company=listing.company,
                job_url=listing.url, location=listing.location,
                status=AppStatus.SKIPPED,
                failure_reason=FailureReason.IGNORED_PREVIOUS_SKIP,
                error_message=f"Previously skipped: {ignored.ignore_reason}",
            )
            db.add(app)
            db.commit()
            tracker.apply_result("skipped", listing.title,
                                 error=FailureReason.IGNORED_PREVIOUS_SKIP)
            refresh_session_counters(db, session_id)
            continue

        tracker.job_start(idx, total, listing.title, listing.company, listing.url)

        # Dedupe against persisted history (any prior positive outcome).
        already = db.query(Application).filter(
            Application.job_url == listing.url,
            Application.status.in_([AppStatus.APPLIED, AppStatus.APPLIED_PENDING,
                                    AppStatus.EMAIL_SENT, AppStatus.EMAIL_DRAFTED]),
        ).first()
        if already:
            tracker.job_already_applied(listing.title)
            continue

        # Per-company dedupe: don't hit the same employer twice in a week.
        if is_duplicate_company(db, listing.company):
            tracker.apply_result("skipped", listing.title,
                                 error=FailureReason.DUPLICATE_COMPANY)
            app = Application(
                session_id=session_id, platform=platform_name,
                job_title=listing.title, company=listing.company,
                job_url=listing.url, location=listing.location,
                status=AppStatus.SKIPPED,
                failure_reason=FailureReason.DUPLICATE_COMPANY,
            )
            db.add(app)
            db.commit()
            maybe_auto_ignore(db, app, enabled=getattr(settings, "auto_ignore_skipped", True))
            refresh_session_counters(db, session_id)
            continue

        # 1) Persist the row immediately — visible as "queued", never stuck.
        app = Application(
            session_id=session_id, platform=platform_name,
            job_title=listing.title, company=listing.company,
            job_url=listing.url, location=listing.location,
            status=AppStatus.QUEUED,
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        tracker.job_status(app.id, AppStatus.QUEUED, title=app.job_title, company=app.company)

        try:
            # 2) Fetch details
            set_app_status(db, app, AppStatus.FETCHING)
            details = JobDetails(job_description=listing.title)
            try:
                details = platform.get_job_details(listing)
                tracker.job_details_fetched(details)
            except Exception as e:
                tracker.job_details_failed(listing.url, e)

            app.company             = details.company_name or listing.company
            app.experience_required = details.experience_required
            app.salary              = details.salary
            app.job_description     = details.job_description
            app.key_skills          = details.key_skills
            app.about_company       = details.about_company
            app.posted_date         = details.posted_date
            app.applicants_count    = details.applicants_count
            app.openings            = details.openings
            app.company_logo_url    = details.company_logo_url
            db.commit()

            if not is_within_posted_filter(app.posted_date, getattr(settings, "date_posted_filter", "any")):
                set_app_status(db, app, AppStatus.SKIPPED,
                               failure_reason=FailureReason.POSTED_DATE_OUT_OF_RANGE)
                tracker.apply_result("skipped", listing.title,
                                     error=FailureReason.POSTED_DATE_OUT_OF_RANGE)
                refresh_session_counters(db, session_id)
                continue

            if stop_event.is_set():
                set_app_status(db, app, AppStatus.STOPPED,
                               failure_reason=FailureReason.SESSION_STOPPED)
                break

            # 3) Classify BEFORE scoring/applying (reads visible page only).
            signals = platform.collect_page_signals()
            classification = classify_job(signals, outreach_mode=settings.outreach_mode)
            app.classification = classification
            db.commit()
            tracker.job_classified(app.id, classification, title=app.job_title)

            decision = route_classification(
                classification, signals,
                easy_apply_only=settings.easy_apply_only,
                include_external_review=settings.include_external_review,
                outreach_mode=settings.outreach_mode,
            )

            if decision.action == "finalize":
                set_app_status(db, app, decision.status,
                               failure_reason=decision.failure_reason)
                tracker.apply_result(decision.status, listing.title,
                                     error=decision.failure_reason)
                if decision.status == AppStatus.FAILED:
                    _evidence(app)
                if decision.failure_reason == FailureReason.CAPTCHA_OR_CHALLENGE:
                    # Back off and abort this platform — never try to bypass.
                    secs = _backoff_seconds(consecutive_failures)
                    tracker.backoff("challenge page detected", secs)
                    log_event(db, session_id, "backoff",
                              {"reason": "captcha_or_challenge", "seconds": secs},
                              application_id=app.id)
                    _interruptible_sleep(stop_event, secs)
                    break
                refresh_session_counters(db, session_id)
                continue

            # 4) Score
            set_app_status(db, app, AppStatus.SCORING)
            try:
                score = llm.score_job(details.job_description)
                tracker.llm_score(score, threshold)
            except Exception as e:
                tracker.llm_failed(e)
                set_app_status(db, app, AppStatus.FAILED,
                               failure_reason=FailureReason.SCORING_FAILED,
                               error_message=str(e))
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    tracker.backoff("repeated scoring failures", BACKOFF_SECONDS)
                    break
                continue

            app.score          = score.score
            app.rationale      = score.rationale
            app.recommendation = score.recommendation
            app.matched_skills = score.matched_skills
            app.missing_skills = score.missing_skills
            db.commit()

            if score.rationale.startswith("LLM unavailable"):
                set_app_status(db, app, AppStatus.FAILED,
                               failure_reason=FailureReason.SCORING_FAILED,
                               error_message=score.rationale)
                continue

            if stop_event.is_set():
                set_app_status(db, app, AppStatus.STOPPED,
                               failure_reason=FailureReason.SESSION_STOPPED)
                break

            # 5) Apply only on LLM "apply" + score >= threshold. A "skip"
            #    recommendation is always honoured (no override setting).
            ok, skip_reason = decide_apply(score.recommendation, score.score, threshold)
            if not ok:
                set_app_status(db, app, AppStatus.SKIPPED, failure_reason=skip_reason)
                tracker.apply_result("skipped", listing.title, error=skip_reason)
                refresh_session_counters(db, session_id)
                continue

            # 6a) Email outreach path (external job + visible recruiter email)
            if decision.action == "outreach" and signals.visible_emails:
                finding = signals.visible_emails[0]
                draft = create_outreach_draft(db, app, cv_data, finding, llm=llm)
                set_app_status(db, app, AppStatus.EMAIL_DRAFTED)
                tracker.outreach_drafted(app.id, draft.id, finding.email,
                                         source_url=finding.source_url)
                refresh_session_counters(db, session_id)
                continue

            # 6b) Platform-native apply
            set_app_status(db, app, AppStatus.APPLYING)
            tracker.apply_start(listing.title, listing.company)
            try:
                rate_limiter.record_action()
                result = platform.apply_to_job(listing, cv_data, llm=llm)
            except RateLimitExceededError as e:
                set_app_status(db, app, AppStatus.STOPPED,
                               failure_reason=FailureReason.RATE_LIMITED,
                               error_message=str(e))
                tracker.rate_limit(str(e))
                break
            except Exception as e:
                tracker.apply_exception(listing.title, e)
                set_app_status(db, app, AppStatus.FAILED,
                               failure_reason=FailureReason.BROWSER_ERROR,
                               error_message=str(e))
                _evidence(app)
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    secs = _backoff_seconds(consecutive_failures)
                    tracker.backoff("repeated apply failures", secs)
                    log_event(db, session_id, "backoff",
                              {"reason": "repeated_failures", "seconds": secs})
                    _interruptible_sleep(stop_event, secs)
                    break
                continue

            app.external_site_url = result.external_url or app.external_site_url or ""
            db.commit()
            tracker.apply_result(result.status, listing.title,
                                 external_url=result.external_url or "",
                                 error=result.error or "")

            if result.status == "applied":
                set_app_status(db, app, AppStatus.APPLIED)
                consecutive_failures = 0
                applied_count[0] += 1
                rate_limiter.wait_after_apply()
            elif result.status == "applied_pending_confirmation":
                # Click went through, nothing bad appeared — success-like.
                set_app_status(db, app, AppStatus.APPLIED_PENDING,
                               error_message=result.error)
                consecutive_failures = 0
                applied_count[0] += 1
                rate_limiter.wait_after_apply()
            elif result.status == "skipped":
                set_app_status(db, app, AppStatus.SKIPPED,
                               failure_reason=result.failure_reason,
                               error_message=result.error)
            elif result.status == "saved":
                set_app_status(db, app, AppStatus.SAVED,
                               failure_reason=result.failure_reason or FailureReason.EXTERNAL_SITE,
                               error_message=result.error)
            elif result.status == "manual_review":
                set_app_status(db, app, AppStatus.MANUAL_REVIEW,
                               failure_reason=result.failure_reason or FailureReason.EXTERNAL_SITE,
                               error_message=result.error)
            else:
                set_app_status(db, app, AppStatus.FAILED,
                               failure_reason=result.failure_reason or FailureReason.UNSUPPORTED_FLOW,
                               error_message=result.error)
                _evidence(app)
                consecutive_failures += 1
                if result.failure_reason in (FailureReason.LOGIN_REQUIRED,
                                             FailureReason.CAPTCHA_OR_CHALLENGE):
                    secs = _backoff_seconds(consecutive_failures)
                    tracker.backoff(f"{result.failure_reason} — aborting platform", secs)
                    log_event(db, session_id, "backoff",
                              {"reason": result.failure_reason, "seconds": secs},
                              application_id=app.id)
                    _interruptible_sleep(stop_event, secs)
                    break
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    secs = _backoff_seconds(consecutive_failures)
                    tracker.backoff("repeated apply failures", secs)
                    log_event(db, session_id, "backoff",
                              {"reason": "repeated_failures", "seconds": secs})
                    _interruptible_sleep(stop_event, secs)
                    break

            refresh_session_counters(db, session_id)

        except Exception as e:
            # Belt-and-braces: a row must never stay in an in-flight state.
            logger.exception("Unhandled error processing %s", listing.url)
            try:
                set_app_status(db, app, AppStatus.FAILED,
                               failure_reason=FailureReason.BROWSER_ERROR,
                               error_message=str(e))
            except Exception:
                pass
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                break

    refresh_session_counters(db, session_id)


def _interruptible_sleep(stop_event: threading.Event, seconds: float) -> None:
    """Sleep that wakes immediately when the session is stopped."""
    stop_event.wait(timeout=seconds)


def _backoff_seconds(failure_count: int) -> float:
    """Exponential backoff capped at 10 minutes (no retries past that —
    the platform loop aborts and the user is shown why)."""
    return min(BACKOFF_SECONDS * (2 ** max(0, failure_count - 1)), 600)
