import logging
import sys

from config.settings import load_config, ConfigError
from core.chrome_manager import ensure_chrome_running, ChromeNotFoundError, ChromeAttachError
from core.cv_parser import parse_cv, CVParseError
from core.llm_client import LLMClient, JobScore
from core.session_logger import (
    ApplicationRecord,
    append_record,
    append_csv_row,
    append_error_log,
    is_already_applied,
    get_session_summary,
    load_log,
)
from platforms.base_platform import LoginError, JobDetails
from platforms.naukri.platform import NaukriPlatform
from platforms.linkedin.platform import LinkedInPlatform
from ui import console as ui
from utils.rate_limiter import RateLimiter, RateLimitExceededError

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)


def run_platform(
    platform,
    platform_name: str,
    cv_data,
    llm: LLMClient,
    keywords: list[str],
    location: str,
    job_target: int,
    threshold: int,
    rate_limiter: RateLimiter,
    log_path: str,
    csv_path: str,
    error_log_path: str,
    session_records: list,
    applied_count: list,
) -> None:
    # Login
    try:
        ui.print_info(f"Checking {platform_name} login...")
        platform.ensure_logged_in()
        ui.print_login_status(platform_name, True)
    except LoginError as e:
        ui.print_error(str(e))
        ui.print_login_status(platform_name, False)
        return

    # Search
    max_to_fetch = min((job_target - applied_count[0]) * 5, 100)
    ui.print_info(f"Searching {platform_name} for: {', '.join(keywords[:3])}...")
    listings = platform.search_jobs(keywords, location, max_to_fetch)
    ui.print_search_results(platform_name, len(listings))

    if not listings:
        ui.print_info(f"No listings found on {platform_name}")
        return

    total_listings = len(listings)
    for idx, listing in enumerate(listings, 1):
        if applied_count[0] >= job_target:
            break

        # Deduplication
        if is_already_applied(log_path, listing.url):
            ui.print_info(f"Already applied: {listing.title} — skipping")
            continue

        # Get full job details (description + structured fields)
        details = JobDetails(job_description=listing.title)
        try:
            details = platform.get_job_details(listing)
        except Exception as e:
            logging.getLogger(__name__).warning("Could not fetch job details for %s: %s", listing.url, e)
        jd = details.job_description

        # Always call LLM — with CV it scores fit; without CV it extracts skills from JD
        ui.console.print(f"  [dim]🤖 LLM analysing job...[/dim]", end="")
        try:
            score = llm.score_job(jd)
            ui.console.print(
                f"[dim] score={score.score} | "
                f"matched={len(score.matched_skills)} | "
                f"missing={len(score.missing_skills)}[/dim]"
            )
        except Exception as e:
            ui.console.print(f"[red] FAILED: {e}[/red]")
            score = JobScore(score=100, rationale="LLM error - auto-apply", matched_skills=[], missing_skills=[], recommendation="apply")

        if not cv_data.raw_text:
            # No CV: force apply to all jobs but keep matched/missing skills from LLM
            score = JobScore(
                score=100,
                rationale=score.rationale,
                matched_skills=score.matched_skills,
                missing_skills=score.missing_skills,
                recommendation="apply",
            )
            ui.print_info(f"[{idx}/{total_listings}] {listing.title} @ {listing.company} — auto-apply (no CV)")
        else:
            ui.print_job_evaluation(idx, total_listings, listing, score, threshold)

        def _make_record(status, error=None, external_url=""):
            return ApplicationRecord(
                platform=platform_name,
                job_title=listing.title,
                company=details.company_name or listing.company,
                job_url=listing.url,
                score=score.score,
                location=listing.location,
                experience_required=details.experience_required,
                salary=details.salary,
                job_description=details.job_description,
                key_skills=details.key_skills,
                about_company=details.about_company,
                posted_date=details.posted_date,
                applicants_count=details.applicants_count,
                openings=details.openings,
                company_logo_url=details.company_logo_url,
                external_site_url=external_url or "",
                matched_skills=score.matched_skills,
                missing_skills=score.missing_skills,
                status=status,
                error_message=error,
            )

        # Decide
        if score.score >= threshold or not cv_data.raw_text:
            try:
                rate_limiter.record_action()
                result = platform.apply_to_job(listing, cv_data, llm=llm)
                ui.print_apply_result(listing, result)

                # Only pause after a real apply; skip/external jobs need no cool-down
                if result.status == "applied":
                    rate_limiter.wait_after_apply()
                    applied_count[0] += 1

                record = _make_record(result.status, result.error, result.external_url or "")
                append_record(log_path, record)
                append_csv_row(csv_path, record)
                append_error_log(error_log_path, record)
                session_records.append(record)

            except RateLimitExceededError as e:
                ui.print_error(str(e))
                break
            except Exception as e:
                record = _make_record("error", str(e))
                append_record(log_path, record)
                append_csv_row(csv_path, record)
                append_error_log(error_log_path, record)
                session_records.append(record)
        else:
            record = _make_record("skipped")
            append_record(log_path, record)
            append_csv_row(csv_path, record)
            session_records.append(record)
            # No wait needed — we only read this page, didn't submit anything


def main() -> None:
    ui.print_banner()

    # Load config
    try:
        config = load_config()
    except ConfigError as e:
        ui.print_error(str(e))
        ui.console.print("[dim]Copy .env.example to .env and fill in your credentials.[/dim]")
        sys.exit(1)

    # Parse CV
    # ui.console.print(f"\n[bold]Parsing CV:[/bold] {config.cv_path}")
    # try:
    #     cv_data = parse_cv(
    #         config.cv_path,
    #         config.azure_openai_endpoint,
    #         config.azure_openai_api_key,
    #         config.azure_deployment_name,
    #     )
    #     ui.print_cv_summary(cv_data)
    # except CVParseError as e:
    #     ui.print_error(str(e))
    #     sys.exit(1)

    # Create empty CV data for now
    from core.cv_parser import CVData
    cv_data = CVData(
        raw_text="",
        name="",
        email="",
        phone="",
        skills=[],
        experience_years=0,
        job_titles=["QA Engineer", "Automation QA Engineer", "Test Engineer"],
        education=[],
        summary="",
    )
    ui.console.print("[dim]CV parsing skipped - using default profile[/dim]")

    # Use config values instead of prompts
    platform_choice = config.platform_choice
    job_target = config.job_target
    threshold = config.confidence_threshold
    location = config.location

    ui.console.print(f"\n[bold]Platform:[/bold] {platform_choice}")
    ui.console.print(f"[bold]Job Target:[/bold] {job_target}")
    ui.console.print(f"[bold]Location:[/bold] {location}")
    ui.console.print(f"[bold]Confidence Threshold:[/bold] {threshold}")

    keywords = cv_data.job_titles or ["software developer"]

    # Launch Chrome
    ui.console.print(f"\n[bold]Launching Chrome on port {config.port_num}...[/bold]")
    try:
        driver = ensure_chrome_running(config.port_num, config.chrome_user_data_dir)
        ui.console.print("[green]✓ Chrome connected[/green]")
    except (ChromeNotFoundError, ChromeAttachError) as e:
        ui.print_error(str(e))
        sys.exit(1)

    # Build LLM client with cached CV
    llm = LLMClient(
        config.azure_openai_endpoint,
        config.azure_openai_api_key,
        cv_data,
        config.azure_deployment_name,
    )

    # Build rate limiter
    rate_limiter = RateLimiter(
        max_per_hour=config.max_jobs_per_hour,
        max_per_day=config.max_jobs_per_day,
    )

    session_records: list[ApplicationRecord] = []
    applied_count = [0]  # mutable counter passed by reference

    from pathlib import Path as _Path
    _log_dir = _Path(config.log_path).parent
    csv_path = str(_log_dir / "applications_report.csv")
    error_log_path = str(_log_dir / "errors_report.csv")
    ui.console.print(f"[dim]Reports → {csv_path}[/dim]")
    ui.console.print(f"[dim]Error log → {error_log_path}[/dim]")

    # Determine which platforms to run
    platforms_to_run = []
    if platform_choice in ("naukri", "both"):
        platforms_to_run.append(("naukri", NaukriPlatform(driver, config, rate_limiter)))
    if platform_choice in ("linkedin", "both"):
        platforms_to_run.append(("linkedin", LinkedInPlatform(driver, config, rate_limiter)))

    ui.console.print()

    for platform_name, platform in platforms_to_run:
        if applied_count[0] >= job_target:
            break
        run_platform(
            platform=platform,
            platform_name=platform_name,
            cv_data=cv_data,
            llm=llm,
            keywords=keywords,
            location=location,
            job_target=job_target,
            threshold=threshold,
            rate_limiter=rate_limiter,
            log_path=config.log_path,
            csv_path=csv_path,
            error_log_path=error_log_path,
            session_records=session_records,
            applied_count=applied_count,
        )

    if applied_count[0] >= job_target:
        ui.print_target_reached(job_target)

    ui.print_final_summary(session_records, config.log_path)
    ui.console.print(f"\n[bold]CSV report:[/bold] {csv_path}")
    ui.console.print(f"[bold]Error log:[/bold]  {error_log_path}")


if __name__ == "__main__":
    main()
