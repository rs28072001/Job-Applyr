"""POST /api/naukri/capture-tokens — auto-capture cookie + nkparam via Selenium CDP."""
import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from api.auth import get_current_user
from api.database import get_db
from api.models import Config, CVProfile, User

router = APIRouter()

# backend/ root (this file is backend/api/routes/naukri.py)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _chrome_profile_dir(cfg: Config) -> str:
    """Mirror session_manager.app_chrome_profile_dir so capture reuses the same
    logged-in profile the session would use."""
    override = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(_BACKEND_DIR, override)
    identity = ((cfg.naukri_email or cfg.linkedin_email or "no-platform-account") if cfg else "no-platform-account").strip().lower()
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return os.path.join(_BACKEND_DIR, "data", "chrome_profiles", digest)


class CaptureTokensResponse(BaseModel):
    ok: bool
    cookie_preview: str
    nkparam_preview: str
    search_url: str


class TestTokensRequest(BaseModel):
    cookie: str
    nkparam: str


class TestTokensResponse(BaseModel):
    ok: bool
    message: str
    found_jobs: int = 0


@router.post("/api/naukri/capture-tokens", response_model=CaptureTokensResponse)
def capture_naukri_tokens(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    if not cfg:
        raise HTTPException(400, "No configuration found. Complete setup first.")

    # Build the search URL from the user's own preferences for a realistic
    # request (and a better-matched token set).
    keywords = cfg.keywords or []
    keyword = keywords[0] if keywords else "software developer"
    location = cfg.location or "india"

    # Experience from the active CV profile, when available.
    experience = None
    cv = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
    if cv and cv.experience_years:
        try:
            experience = int(cv.experience_years)
        except (ValueError, TypeError):
            experience = None

    from platforms.naukri.token_capture import capture_tokens, build_search_page_url, TokenCaptureError
    from core.chrome_manager import ChromeNotFoundError

    user_data_dir = _chrome_profile_dir(cfg)
    search_url = build_search_page_url(keyword, location, experience)

    try:
        cookie, nkparam = capture_tokens(keyword, location, user_data_dir, experience)
    except TokenCaptureError as e:
        raise HTTPException(502, str(e))
    except ChromeNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Token capture failed: {str(e) or type(e).__name__}")

    cfg.naukri_cookie = cookie
    cfg.naukri_nkparam = nkparam
    # Capturing tokens only makes sense for API mode — switch into it.
    cfg.naukri_search_mode = "api"
    db.commit()

    return CaptureTokensResponse(
        ok=True,
        cookie_preview=f"{cookie[:24]}… ({len(cookie)} chars)",
        nkparam_preview=f"{nkparam[:16]}… ({len(nkparam)} chars)",
        search_url=search_url,
    )


@router.post("/api/naukri/test-tokens", response_model=TestTokensResponse)
def test_naukri_tokens(body: TestTokensRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Test if the provided cookie + nkparam tokens are still valid."""
    if not body.cookie or not body.nkparam:
        raise HTTPException(400, "Both cookie and nkparam are required.")

    from platforms.naukri.api_search import build_session, search_jobs_api, NaukriRecaptchaError, NaukriAPIAuthError
    from utils.rate_limiter import RateLimiter

    try:
        # Try to build a session with the provided tokens
        session = build_session(body.cookie, body.nkparam)
    except NaukriAPIAuthError as e:
        return TestTokensResponse(
            ok=False,
            message=f"Invalid tokens: {str(e)}",
            found_jobs=0
        )

    # Try a simple 1-job search to verify tokens work
    try:
        rate_limiter = RateLimiter(max_per_hour=999, max_per_day=999)
        results = search_jobs_api(
            keywords=["software engineer"],
            location="india",
            max_jobs=1,
            rate_limiter=rate_limiter,
            session=session,
        )
        return TestTokensResponse(
            ok=True,
            message="Tokens are valid and working! ✓",
            found_jobs=len(results)
        )
    except NaukriRecaptchaError:
        return TestTokensResponse(
            ok=False,
            message="Tokens have expired or are invalid — Naukri returned a reCAPTCHA challenge. Refresh your tokens.",
            found_jobs=0
        )
    except Exception as e:
        return TestTokensResponse(
            ok=False,
            message=f"Test failed: {str(e) or type(e).__name__}",
            found_jobs=0
        )
