"""Central selector registry with ordered fallback lists.

Every platform selector lives here so that (a) apply/login code tries each
fallback in order, and (b) the selector health check can verify the same
lists against bundled DOM snapshot fixtures.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: platform → purpose → ordered fallback list of CSS selectors
SELECTORS: dict[str, dict[str, list[str]]] = {
    "naukri": {
        "internal_apply_button": [
            "button#apply-button",
            "a#apply-button",
            "button[class*='apply-button']",
            "a[class*='apply-button']",
            "button[id*='apply']:not([id*='company-site'])",
        ],
        "external_apply_button": [
            "button#company-site-button",
            "button[class*='company-site-button']",
            "a[class*='company-site-button']",
        ],
        "already_applied": [
            "button[class*='already-applied']",
            "span[class*='already-applied']",
            "div[class*='already-applied']",
        ],
        "apply_success": [
            "div[class*='apply-success']",
            "div[class*='applied-banner']",
            "span[class*='applied-message']",
            "div[class*='apply-status-header']",
            "div[class*='success-msg']",
            "span[class*='apply-status']",
            "button[class*='already-applied']",   # button flips after apply
        ],
        "chatbot_drawer": [
            "div[class*='chatbot_Drawer']",
            "div[class*='chatbot_drawer']",
            "div[class*='chatBot']",
        ],
        "login_form": [
            "form[name='login-form']",
            "input#usernameField",
            "div[class*='login-layer']",
        ],
    },
    "linkedin": {
        "easy_apply_button": [
            "button[class*='jobs-apply-button']",
            "button[aria-label*='Easy Apply']",
            "div[class*='jobs-apply-button--top-card'] button",
        ],
        "external_apply_button": [
            "button[aria-label*='Apply on company website']",
            "a[aria-label*='Apply on company website']",
        ],
        "already_applied": [
            "span[class*='artdeco-inline-feedback__message']",
            "div[class*='post-apply-timeline']",
        ],
        "easy_apply_modal": [
            "div[class*='jobs-easy-apply-modal']",
            "div[class*='artdeco-modal']",
        ],
        "submit_button": [
            "button[aria-label='Submit application']",
            "button[aria-label*='Submit']",
        ],
        "next_button": [
            "button[aria-label='Continue to next step']",
            "button[aria-label*='Continue']",
        ],
        "review_button": [
            "button[aria-label='Review your application']",
            "button[aria-label*='Review']",
        ],
        "login_form": [
            "input#username",
            "form[class*='login__form']",
            "a[href*='/login']",
        ],
    },
}

#: text markers (lowercased page text) — shared across platforms
TEXT_MARKERS: dict[str, list[str]] = {
    "login_required": [
        "login to apply", "register to apply", "login to view",
        "register to unlock", "sign in to apply", "join now to apply",
    ],
    "challenge": [
        "captcha", "verify you are human", "unusual activity",
        "security check", "are you a robot", "access denied",
        "checking your browser",
    ],
    "apply_success": [
        "successfully applied", "application sent", "application submitted",
        "you have applied", "applied successfully", "application received",
    ],
    "apply_error": [
        "something went wrong", "could not process", "try again later",
        "application failed",
    ],
}


def find_first(driver, platform: str, purpose: str, timeout: float = 0):
    """Try each fallback selector in order; return (element, selector) or
    (None, None). Logs which fallback matched so drift is visible in logs."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    candidates = SELECTORS.get(platform, {}).get(purpose, [])
    for i, sel in enumerate(candidates):
        try:
            if timeout > 0:
                el = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            if i > 0:
                logger.info("Selector fallback #%d matched for %s/%s: %s",
                            i, platform, purpose, sel)
            return el, sel
        except (TimeoutException, NoSuchElementException):
            continue
        except Exception as e:
            logger.debug("Selector %s error: %s", sel, e)
            continue
    return None, None


def find_first_clickable(driver, platform: str, purpose: str, timeout: float = 5):
    """Like find_first but waits for clickability per fallback."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    candidates = SELECTORS.get(platform, {}).get(purpose, [])
    per_sel = max(1.0, timeout / max(1, len(candidates)))
    for i, sel in enumerate(candidates):
        try:
            el = WebDriverWait(driver, per_sel).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            if i > 0:
                logger.info("Selector fallback #%d matched for %s/%s: %s",
                            i, platform, purpose, sel)
            return el, sel
        except TimeoutException:
            continue
        except Exception:
            continue
    return None, None
