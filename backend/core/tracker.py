"""
Step-by-step job application tracker.
Writes a human-readable log to logs/tracking.log with full tracebacks.
Also emits structured JSON events into an optional queue for WebSocket streaming.
"""
import logging
import queue as _queue_mod
import traceback
from datetime import datetime, timezone
from pathlib import Path


_tracker: logging.Logger | None = None

# Injected by api/server.py at startup; None when running as CLI
_event_queue: _queue_mod.Queue | None = None


def set_event_queue(q: _queue_mod.Queue) -> None:
    """Called once at FastAPI startup to wire up WebSocket streaming."""
    global _event_queue
    _event_queue = q


def _emit(event: dict) -> None:
    """Put a structured event onto the WebSocket queue (no-op in CLI mode)."""
    if _event_queue is not None:
        try:
            _event_queue.put_nowait(event)
        except _queue_mod.Full:
            pass  # drop if queue is full — UI is disconnected


def init_tracker(log_dir: str) -> logging.Logger:
    global _tracker
    p = Path(log_dir)
    p.mkdir(parents=True, exist_ok=True)
    log_file = p / "tracking.log"

    logger = logging.getLogger("tracker")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

    # Also echo INFO+ to stderr so user sees it live
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("  %(message)s"))
    logger.addHandler(sh)

    _tracker = logger
    _banner(f"SESSION START — log file: {log_file}")
    return logger


def get() -> logging.Logger:
    global _tracker
    if _tracker is None:
        _tracker = logging.getLogger("tracker")
    return _tracker


def _banner(msg: str) -> None:
    get().info("=" * 70)
    get().info(msg)
    get().info("=" * 70)


# ── convenience wrappers ──────────────────────────────────────────────────────

def session_config(cfg) -> None:
    t = get()
    t.info("[CONFIG] platform=%s  target=%s  location=%s  threshold=%s",
           cfg.platform_choice, cfg.job_target, cfg.location, cfg.confidence_threshold)
    t.info("[CONFIG] cv_path=%s", cfg.cv_path)
    t.info("[CONFIG] model=%s", cfg.azure_deployment_name)
    _emit({"type": "session_config", "platform": cfg.platform_choice,
           "target": cfg.job_target, "location": cfg.location,
           "threshold": cfg.confidence_threshold})


def cv_parsed(cv_data) -> None:
    t = get()
    t.info("[CV] name=%s  exp=%.1f yrs  titles=%s",
           cv_data.name or "(unknown)", cv_data.experience_years,
           ", ".join(cv_data.job_titles or []))
    t.info("[CV] skills=%s", ", ".join(cv_data.skills[:15]))
    _emit({"type": "cv_parsed", "name": cv_data.name,
           "experience_years": cv_data.experience_years,
           "titles": cv_data.job_titles, "skills": cv_data.skills[:15]})


def cv_failed(err: Exception) -> None:
    get().warning("[CV] Parse failed — running without CV: %s", err)
    _emit({"type": "log", "level": "warning", "msg": f"CV parse failed: {err}"})


def login_ok(platform: str) -> None:
    get().info("[LOGIN] %s  ✓ logged in", platform)
    _emit({"type": "login", "platform": platform, "ok": True})


def login_fail(platform: str, err) -> None:
    get().error("[LOGIN] %s  FAILED: %s", platform, err)
    _emit({"type": "login", "platform": platform, "ok": False, "error": str(err)})


def search_results(platform: str, keywords: list, count: int) -> None:
    get().info("[SEARCH] %s  keywords=%s  found=%d listings", platform, keywords[:3], count)
    _emit({"type": "search", "platform": platform, "keywords": keywords[:3], "count": count})


def job_start(idx: int, total: int, title: str, company: str, url: str) -> None:
    t = get()
    t.info("")
    t.info("[JOB %d/%d] %s @ %s", idx, total, title, company)
    t.debug("[JOB %d/%d] url=%s", idx, total, url)
    _emit({"type": "job_start", "idx": idx, "total": total,
           "title": title, "company": company, "url": url})


def job_already_applied(title: str) -> None:
    get().info("  [SKIP] already applied — %s", title)
    _emit({"type": "job_skip", "reason": "already_applied", "title": title})


def job_details_fetched(details) -> None:
    t = get()
    t.debug("  [DETAILS] exp=%s  salary=%s  posted=%s  applicants=%s",
            details.experience_required, details.salary,
            details.posted_date, details.applicants_count)
    _emit({"type": "job_details",
           "exp_required": details.experience_required,
           "salary": details.salary,
           "posted_date": details.posted_date,
           "applicants": details.applicants_count})


def job_details_failed(url: str, err: Exception) -> None:
    get().warning("  [DETAILS] could not fetch details for %s: %s", url, err)
    _emit({"type": "log", "level": "warning", "msg": f"Details fetch failed: {err}"})


def llm_score(score, threshold: int) -> None:
    t = get()
    t.info("  [LLM] score=%d  threshold=%d  recommendation=%s",
           score.score, threshold, score.recommendation)
    t.info("  [LLM] rationale: %s", score.rationale)
    if score.matched_skills:
        t.info("  [LLM] matched: %s", ", ".join(score.matched_skills))
    if score.missing_skills:
        t.info("  [LLM] missing: %s", ", ".join(score.missing_skills))
    _emit({"type": "llm_score", "score": score.score, "threshold": threshold,
           "rationale": score.rationale, "recommendation": score.recommendation,
           "matched": score.matched_skills, "missing": score.missing_skills})


def llm_failed(err: Exception) -> None:
    get().error("  [LLM] FAILED: %s", err)
    get().debug("  [LLM] traceback:\n%s", traceback.format_exc())
    _emit({"type": "error", "msg": f"LLM failed: {err}", "traceback": traceback.format_exc()})


def apply_start(title: str, company: str) -> None:
    get().info("  [APPLY] attempting → %s @ %s", title, company)
    _emit({"type": "apply_start", "title": title, "company": company})


def apply_step(step: str, detail: str = "") -> None:
    msg = f"  [APPLY] step={step}"
    if detail:
        msg += f"  {detail}"
    get().debug(msg)


def apply_result(status: str, title: str, external_url: str = "", error: str = "") -> None:
    t = get()
    if status == "applied":
        t.info("  [APPLY] ✓ SUCCESS — %s", title)
    elif status in ("skipped", "skipped_external"):
        t.info("  [APPLY] skipped (%s)%s", status, f"  external_url={external_url}" if external_url else "")
    else:
        t.error("  [APPLY] FAILED status=%s  error=%s", status, error)
    _emit({"type": "apply_result", "status": status, "title": title,
           "external_url": external_url, "error": error})


def apply_exception(title: str, err: Exception) -> None:
    t = get()
    t.error("  [APPLY] EXCEPTION on '%s': %s", title, err)
    t.error("  [APPLY] traceback:\n%s", traceback.format_exc())
    _emit({"type": "error", "msg": f"Apply exception on '{title}': {err}",
           "traceback": traceback.format_exc()})


def rate_limit(msg: str) -> None:
    get().warning("[RATE_LIMIT] %s", msg)
    _emit({"type": "rate_limit", "msg": msg})


def session_end(applied: int, target: int, skipped: int, errors: int) -> None:
    _banner(
        f"SESSION END — applied={applied}/{target}  skipped={skipped}  errors={errors}"
    )
    _emit({"type": "session_end", "applied": applied, "target": target,
           "skipped": skipped, "errors": errors})
