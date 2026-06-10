"""
Manages the single active job-search session.
Runs the blocking Selenium code in a ThreadPoolExecutor thread so FastAPI
stays responsive. Exposes start() / stop() / status.
"""
import logging
import hashlib
import threading
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
    """Signal the running session to stop and close Chrome driver."""
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
            from api.models import Session as SessionModel
            db = SessionLocal()
            try:
                db_sess = db.get(SessionModel, session_id)
                if db_sess and db_sess.status == "running":
                    db_sess.status = "stopped"
                    db_sess.ended_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to mark session %s stopped immediately", session_id)


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
    # Ensure backend/ is on the path when running from Docker or a sub-process
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from api.database import SessionLocal
    from api.models import Session as SessionModel, Application, Config as ConfigModel, CVProfile
    from config.settings import Config
    from core.chrome_manager import ensure_chrome_running, ChromeNotFoundError, ChromeAttachError
    from core.cv_parser import CVData
    from core.llm_provider import get_llm_settings, validate_llm_settings
    from core.llm_client import LLMClient
    import core.tracker as tracker
    from platforms.naukri.platform import NaukriPlatform
    from platforms.linkedin.platform import LinkedInPlatform
    from utils.rate_limiter import RateLimiter
    from platforms.base_platform import LoginError, JobDetails

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

        # Build stdlib Config dataclass from DB row
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
        )

        # Build CVData from DB profile (or empty fallback)
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
        # Init tracker (file log)
        import pathlib
        pathlib.Path("./logs").mkdir(parents=True, exist_ok=True)
        tracker.init_tracker("./logs")
        tracker.session_config(cfg)
        if cv_data.raw_text:
            tracker.cv_parsed(cv_data)

        logger.info("Session %s: Connecting to Chrome", session_id)
        # Connect Chrome
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
            db_sess.status = "failed"
            db_sess.ended_at = datetime.now(timezone.utc)
            db.commit()
            return

        rate_limiter = RateLimiter(max_per_hour=cfg.max_jobs_per_hour,
                                   max_per_day=cfg.max_jobs_per_day)

        # Determine platforms and check login BEFORE LLM initialization
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
            )

        # Finalise session row
        final_apps = db.query(Application).filter_by(session_id=session_id).all()
        db_sess.applied  = sum(1 for a in final_apps if a.status == "applied")
        db_sess.skipped  = sum(1 for a in final_apps if a.status in ("skipped", "skipped_external"))
        db_sess.errors   = sum(1 for a in final_apps if a.status == "error")
        db_sess.ended_at = datetime.now(timezone.utc)
        db_sess.status   = "stopped" if stop_event.is_set() else "completed"
        db.commit()

        tracker.session_end(db_sess.applied, cfg.job_target, db_sess.skipped, db_sess.errors)

    except Exception as exc:
        logger.error("Session %s crashed: %s\n%s", session_id, exc, traceback.format_exc())
        tracker._emit({"type": "error", "msg": str(exc), "traceback": traceback.format_exc()})
        try:
            db_sess = db.get(SessionModel, session_id)
            if db_sess:
                db_sess.status = "failed"
                db_sess.ended_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _run_platform_db(
    platform, platform_name, cv_data, llm, keywords, location,
    job_target, threshold, rate_limiter, session_id, db,
    stop_event, applied_count,
) -> None:
    """Inner loop — mirrors run_platform() from main.py but writes to DB."""
    import core.tracker as tracker
    from api.models import Application
    from platforms.base_platform import LoginError, JobDetails
    from core.llm_client import JobScore
    from utils.rate_limiter import RateLimitExceededError
    from datetime import datetime, timezone

    # Login
    try:
        platform.ensure_logged_in()
        tracker.login_ok(platform_name)
    except LoginError as e:
        tracker.login_fail(platform_name, e)
        return

    # Search
    max_fetch = min((job_target - applied_count[0]) * 5, 100)
    listings  = platform.search_jobs(keywords, location, max_fetch)
    tracker.search_results(platform_name, keywords, len(listings))

    if not listings:
        return

    total = len(listings)
    for idx, listing in enumerate(listings, 1):
        if stop_event.is_set() or applied_count[0] >= job_target:
            break

        tracker.job_start(idx, total, listing.title, listing.company, listing.url)

        # Dedup against DB
        already = db.query(Application).filter_by(
            job_url=listing.url, status="applied"
        ).first()
        if already:
            tracker.job_already_applied(listing.title)
            continue

        # Job details
        details = JobDetails(job_description=listing.title)
        try:
            details = platform.get_job_details(listing)
            tracker.job_details_fetched(details)
        except Exception as e:
            tracker.job_details_failed(listing.url, e)

        # Check stop before LLM call
        if stop_event.is_set():
            break

        # LLM score
        try:
            score = llm.score_job(details.job_description)
            tracker.llm_score(score, threshold)
        except Exception as e:
            tracker.llm_failed(e)
            score = JobScore(score=100, rationale="LLM error",
                             matched_skills=[], missing_skills=[], recommendation="apply")

        # Force apply if no CV
        if not cv_data.raw_text:
            score = JobScore(score=100, rationale=score.rationale,
                             matched_skills=score.matched_skills,
                             missing_skills=score.missing_skills,
                             recommendation="apply")

        # Check stop before apply
        if stop_event.is_set():
            break

        # Apply decision
        if score.score >= threshold or not cv_data.raw_text:
            tracker.apply_start(listing.title, listing.company)
            try:
                rate_limiter.record_action()
                result = platform.apply_to_job(listing, cv_data, llm=llm)
                tracker.apply_result(result.status, listing.title,
                                     external_url=result.external_url or "",
                                     error=result.error or "")
                if result.status == "applied":
                    rate_limiter.wait_after_apply()
                    applied_count[0] += 1

                app = Application(
                    session_id=session_id, platform=platform_name,
                    job_title=listing.title, company=details.company_name or listing.company,
                    job_url=listing.url, score=score.score, location=listing.location,
                    experience_required=details.experience_required, salary=details.salary,
                    job_description=details.job_description, key_skills=details.key_skills,
                    about_company=details.about_company, posted_date=details.posted_date,
                    applicants_count=details.applicants_count, openings=details.openings,
                    company_logo_url=details.company_logo_url,
                    external_site_url=result.external_url or "",
                    matched_skills=score.matched_skills, missing_skills=score.missing_skills,
                    status=result.status, error_message=result.error,
                )
                db.add(app)
                db.commit()

            except RateLimitExceededError as e:
                tracker.rate_limit(str(e))
                break
            except Exception as e:
                tracker.apply_exception(listing.title, e)
                app = Application(
                    session_id=session_id, platform=platform_name,
                    job_title=listing.title, company=listing.company,
                    job_url=listing.url, score=score.score,
                    matched_skills=score.matched_skills, missing_skills=score.missing_skills,
                    status="error", error_message=str(e),
                )
                db.add(app)
                db.commit()
        else:
            tracker.apply_result("skipped", listing.title)
            app = Application(
                session_id=session_id, platform=platform_name,
                job_title=listing.title, company=listing.company,
                job_url=listing.url, score=score.score,
                matched_skills=score.matched_skills, missing_skills=score.missing_skills,
                status="skipped",
            )
            db.add(app)
            db.commit()
