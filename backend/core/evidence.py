"""Failed-job evidence capture.

When an apply attempt fails, save what the automation was looking at:
  * page screenshot (PNG, if the driver supports it)
  * page URL + visible text excerpt (TXT)
Stored under data/evidence/app_<id>/ and linked from the application row, so
failures in the review/history views can be diagnosed without re-running.
"""
from __future__ import annotations

import logging
import pathlib
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_EVIDENCE_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "evidence"
MAX_TEXT_CHARS = 8000

_TAGS = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def capture_evidence(driver, application_id: int,
                     base_dir: pathlib.Path | str = DEFAULT_EVIDENCE_DIR) -> str:
    """Capture screenshot + page text for one application. Returns the
    evidence directory path ('' on total failure). Never raises."""
    try:
        out = pathlib.Path(base_dir) / f"app_{application_id}"
        out.mkdir(parents=True, exist_ok=True)

        url, page_source = "", ""
        try:
            url = driver.current_url or ""
        except Exception:
            pass
        try:
            page_source = driver.page_source or ""
        except Exception:
            pass

        # Screenshot (optional capability)
        try:
            driver.save_screenshot(str(out / "page.png"))
        except Exception as e:
            logger.debug("Screenshot capture failed for app %s: %s", application_id, e)

        # Visible-text excerpt
        text = _TAG.sub(" ", _TAGS.sub(" ", page_source))
        text = " ".join(text.split())[:MAX_TEXT_CHARS]
        (out / "page.txt").write_text(
            f"captured_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"url: {url}\n\n{text}\n",
            encoding="utf-8",
        )
        return str(out)
    except Exception:
        logger.exception("Evidence capture failed for application %s", application_id)
        return ""
