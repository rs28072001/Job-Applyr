"""Capture Naukri's `cookie` + `nkparam` headers automatically via Selenium CDP.

Naukri's job-search API (jobapi/v3/search) is gated behind reCAPTCHA Enterprise
plus Akamai bot-protection tokens (bm_sv, ak_bmsc) and a JS-minted `nkparam`
request header. A plain HTTP client can't generate these — but a real browser
does, for any visitor (login is optional).

This module drives a real Chrome to the human search-results page, then reads
the browser's CDP performance log to lift the exact `cookie` and `nkparam`
headers off the search XHR. Those are saved to config so API mode can replay
them — no manual DevTools copy-paste.
"""
import json
import logging
import time
from urllib.parse import quote_plus

from core.chrome_manager import get_capture_driver
from .api_search import _slugify

logger = logging.getLogger(__name__)


class TokenCaptureError(Exception):
    """Raised when the cookie / nkparam headers could not be captured."""


def build_search_page_url(keyword: str, location: str, experience: int | None = None) -> str:
    """Build the human-facing Naukri search-results URL (not the API URL).

    e.g. https://www.naukri.com/qa-testing-jobs-in-gurugram?k=qa%20testing&l=gurugram&experience=1
    """
    keyword = (keyword or "software developer").strip()
    location = (location or "india").strip()
    kw_slug = _slugify(keyword)
    loc_slug = _slugify(location)

    seo_path = f"{kw_slug}-jobs-in-{loc_slug}" if loc_slug else f"{kw_slug}-jobs"
    params = [f"k={quote_plus(keyword)}"]
    if location:
        params.append(f"l={quote_plus(location)}")
    if experience is not None:
        params.append(f"experience={experience}")

    return f"https://www.naukri.com/{seo_path}?{'&'.join(params)}"


def capture_tokens(
    keyword: str,
    location: str,
    user_data_dir: str,
    experience: int | None = None,
    timeout: int = 40,
) -> tuple[str, str]:
    """Drive Chrome to a Naukri search page and capture (cookie, nkparam).

    Returns the full `cookie` header string and the `nkparam` header value as
    seen on the search XHR. Raises TokenCaptureError if nkparam never appears
    (e.g. the page didn't load, or a manual bot-check blocked the search).
    """
    search_url = build_search_page_url(keyword, location, experience)
    logger.info("Token capture: navigating to %s", search_url)

    try:
        driver = get_capture_driver(user_data_dir)
    except Exception as chrome_err:
        raise TokenCaptureError(
            f"Failed to launch Chrome for token capture: {chrome_err}. "
            "This usually means:\n"
            "1. Chrome/Chromium is not installed\n"
            "2. Chrome already crashed and still has locks\n"
            "3. System is out of memory or file descriptors\n"
            "Workaround: Manually paste Naukri cookie + nkparam in Settings > Naukri API"
        ) from chrome_err

    try:
        driver.get(search_url)

        nkparam: str | None = None
        cookie: str | None = None
        search_req_ids: set[str] = set()
        deadline = time.time() + timeout

        while time.time() < deadline:
            for entry in driver.get_log("performance"):
                try:
                    msg = json.loads(entry["message"])["message"]
                except (KeyError, ValueError):
                    continue

                method = msg.get("method")
                params = msg.get("params", {})

                # nkparam is a custom JS-set header → present on requestWillBeSent
                if method == "Network.requestWillBeSent":
                    req = params.get("request", {})
                    if "jobapi/v3/search" in req.get("url", ""):
                        search_req_ids.add(params.get("requestId"))
                        for k, v in (req.get("headers") or {}).items():
                            lk = k.lower()
                            if lk == "nkparam":
                                nkparam = v
                            elif lk == "cookie":
                                cookie = v

                # cookie header is added by the network stack → arrives in ExtraInfo
                elif method == "Network.requestWillBeSentExtraInfo":
                    if params.get("requestId") in search_req_ids:
                        for k, v in (params.get("headers") or {}).items():
                            if k.lower() == "cookie":
                                cookie = v

            if nkparam and cookie:
                break
            time.sleep(0.5)

        # Fallback: reconstruct the cookie header from the browser's cookie jar
        if not cookie:
            try:
                jar = driver.get_cookies()
                cookie = "; ".join(f"{c['name']}={c['value']}" for c in jar)
            except Exception:
                cookie = ""

        if not nkparam:
            raise TokenCaptureError(
                "Could not capture nkparam from Naukri. The search page may not "
                "have loaded, or a bot-check blocked it. Try again, and complete "
                "any captcha in the opened browser window before it closes."
            )
        if not cookie:
            raise TokenCaptureError("Captured nkparam but no cookie — please retry.")

        logger.info("Token capture succeeded (cookie %d chars, nkparam %d chars)",
                    len(cookie), len(nkparam))
        return cookie, nkparam
    finally:
        try:
            driver.quit()
        except Exception:
            pass
