import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..base_platform import JobListing, ApplicationResult
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# ── apply button selectors ────────────────────────────────────────────────────
SEL_APPLY_BTN       = "button[id='apply-button'], a[id='apply-button']"
SEL_APPLY_BTN_ALT   = "button[class*='apply-button'], a[class*='apply-button']"
SEL_EXTERNAL_BTN    = "button#company-site-button, button[class*='company-site-button']"
SEL_ALREADY_APPLIED = "button[class*='already-applied'], span[class*='already-applied']"
SEL_APPLIED_SUCCESS = "div[class*='apply-success'], div[class*='applied-banner'], span[class*='applied-message']"
SEL_CONFIRM_BTN     = "button.btn-primary, button[class*='confirm']"

# ── chatbot drawer selectors (from actual Naukri HTML) ────────────────────────
SEL_CHATBOT_DRAWER  = "div[class*='chatbot_Drawer']"
SEL_BOT_ITEMS       = "li.botItem, li[class*='botItem']"
SEL_USER_OPTIONS    = "li[class*='userItem'] label, li[class*='userItem'] span[class*='option']"
SEL_RADIO_INPUTS    = "li[class*='userItem'] input[type='radio']"
SEL_TEXT_INPUT      = "div[id*='userInput'][contenteditable='true'], div[class*='textArea'][contenteditable='true']"
SEL_SAVE_BTN        = "div.sendMsg, div[id*='sendMsg'] div.sendMsg"
SEL_CHAT_CLOSE      = "div[class*='crossIcon'], div[class*='closeIcon']"


def _page_requires_login(driver) -> bool:
    try:
        current = driver.current_url.lower()
        if "nlogin" in current or "/login" in current:
            return True
        text = driver.execute_script("return document.body ? document.body.innerText : ''") or ""
        text = text.lower()
        return any(
            phrase in text
            for phrase in (
                "login to apply",
                "register to apply",
                "login to view",
                "register to unlock",
            )
        )
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# External URL capture
# ─────────────────────────────────────────────────────────────────────────────

def _capture_external_url(driver, rate_limiter: RateLimiter) -> str:
    """
    Capture the external ATS URL from the 'Apply on company site' button.
    Strategy:
      1. Try to read URL from button attributes (href / data-href / onclick) — no click needed.
      2. Fall back to a real Selenium click (trusted gesture → browser allows window.open),
         then capture the new-tab URL and close it.
    """
    try:
        btn = driver.find_element(By.CSS_SELECTOR, SEL_EXTERNAL_BTN)

        # ── Strategy 1: extract URL from attributes without clicking ─────────
        attr_url = driver.execute_script("""
            const btn = arguments[0];
            // direct href
            if (btn.href && btn.href !== window.location.href) return btn.href;
            if (btn.getAttribute('href') && btn.getAttribute('href') !== '#') return btn.getAttribute('href');
            // data attributes
            for (const attr of ['data-href', 'data-url', 'data-link', 'data-redirect']) {
                const v = btn.getAttribute(attr);
                if (v && v.startsWith('http')) return v;
            }
            // onclick / action
            const oc = btn.getAttribute('onclick') || '';
            const m = oc.match(/(?:window\\.open|location\\.href)[^'\"]*['\"](https?[^'\"]+)['\\"]/);
            if (m) return m[1];
            // walk up to nearest anchor
            let el = btn;
            for (let i = 0; i < 4; i++) {
                if (el.tagName === 'A' && el.href) return el.href;
                if (!el.parentElement) break;
                el = el.parentElement;
            }
            return '';
        """, btn)

        if attr_url and attr_url.startswith("http"):
            logger.debug("External URL from attributes: %s", attr_url)
            return attr_url

        # ── Strategy 2: real click → new tab ─────────────────────────────────
        original_handles = set(driver.window_handles)
        btn.click()  # real WebDriver click = trusted gesture → allows window.open()

        # Poll up to 6 s for a new tab
        for _ in range(12):
            time.sleep(0.5)
            if set(driver.window_handles) - original_handles:
                break

        new_handles = set(driver.window_handles) - original_handles
        if not new_handles:
            logger.debug("No new tab opened after real click on external button")
            return ""

        new_tab = new_handles.pop()
        driver.switch_to.window(new_tab)

        # Wait for the URL to resolve past about:blank
        for _ in range(12):
            url = driver.current_url
            if url and url not in ("about:blank", ""):
                break
            time.sleep(0.5)

        url = driver.current_url
        driver.close()
        driver.switch_to.window(list(original_handles)[0])
        return url if url not in ("about:blank", "") else ""

    except Exception as e:
        logger.debug("Could not capture external URL: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Chatbot handler
# ─────────────────────────────────────────────────────────────────────────────

def _chatbot_latest_question(driver) -> str:
    """Return the text of the latest bot message, or '' if none."""
    try:
        return driver.execute_script("""
            const items = document.querySelectorAll('li.botItem, li[class*="botItem"]');
            if (!items.length) return '';
            const last = items[items.length - 1];
            const el = last.querySelector('span, div.botMsg');
            return el ? el.innerText.trim() : '';
        """) or ""
    except Exception:
        return ""


def _chatbot_choices(driver) -> list[str]:
    """Return visible radio/option texts inside the latest user-item area."""
    try:
        # Try label text inside userItem
        choices = driver.execute_script("""
            const labels = document.querySelectorAll(
                'li[class*="userItem"] label, li[class*="userItem"] span[class*="option"]'
            );
            return Array.from(labels)
                .map(l => l.innerText.trim())
                .filter(t => t.length > 0);
        """)
        if choices:
            return choices
        # Fallback: any radio + label pairs on the page
        choices = driver.execute_script("""
            const radios = document.querySelectorAll('input[type="radio"]');
            return Array.from(radios).map(r => {
                const lbl = document.querySelector('label[for="' + r.id + '"]');
                return lbl ? lbl.innerText.trim() : r.value.trim();
            }).filter(t => t.length > 0);
        """)
        return choices or []
    except Exception:
        return []


def _chatbot_click_choice(driver, answer: str) -> bool:
    """Click the option whose text matches answer (case-insensitive)."""
    try:
        clicked = driver.execute_script("""
            const ans = arguments[0].toLowerCase();
            // Try labels in userItem
            const labels = document.querySelectorAll(
                'li[class*="userItem"] label, li[class*="userItem"] span[class*="option"]'
            );
            for (const l of labels) {
                if (l.innerText.trim().toLowerCase() === ans) { l.click(); return true; }
            }
            // Try radio inputs by value / associated label
            const radios = document.querySelectorAll('input[type="radio"]');
            for (const r of radios) {
                const lbl = document.querySelector('label[for="' + r.id + '"]');
                const text = (lbl ? lbl.innerText : r.value).trim().toLowerCase();
                if (text === ans) { r.click(); if (lbl) lbl.click(); return true; }
            }
            return false;
        """, answer.lower())
        return bool(clicked)
    except Exception:
        return False


def _chatbot_type_answer(driver, answer: str) -> bool:
    """Type answer into the contenteditable text area."""
    try:
        inp = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_TEXT_INPUT))
        )
        driver.execute_script("""
            const el = arguments[0];
            el.focus();
            el.innerText = arguments[1];
            el.dispatchEvent(new Event('input',  {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
        """, inp, answer)
        return True
    except Exception:
        return False


def _chatbot_click_save(driver) -> bool:
    """Click the Save / Send button."""
    try:
        btn = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_SAVE_BTN))
        )
        driver.execute_script("arguments[0].click();", btn)
        return True
    except Exception:
        return False


def _handle_chatbot(driver, llm, cv_data, rate_limiter: RateLimiter) -> None:
    """
    Drive Naukri's chatbot-apply sidebar to completion.
    Uses LLM (or sensible fallbacks) to answer each question.
    """
    # Wait up to 4 s for the drawer to appear
    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEL_CHATBOT_DRAWER))
        )
    except TimeoutException:
        return  # no chatbot on this job

    logger.info("Chatbot drawer detected — starting automated answers")
    last_question = ""
    stale_turns = 0

    for turn in range(25):
        time.sleep(0.8)

        question = _chatbot_latest_question(driver)

        # Drawer closed or finished
        if not driver.find_elements(By.CSS_SELECTOR, SEL_CHATBOT_DRAWER):
            logger.info("Chatbot drawer closed — done")
            break

        if not question:
            stale_turns += 1
            if stale_turns >= 3:
                break
            continue

        # Completion phrases
        if any(w in question.lower() for w in ("thank", "application submitted", "applied successfully", "we'll get back")):
            logger.info("Chatbot completed: %s", question)
            time.sleep(1)
            break

        if question == last_question:
            stale_turns += 1
            if stale_turns >= 3:
                break
            continue

        last_question = question
        stale_turns = 0
        logger.info("Chatbot Q: %s", question)

        # ── determine input type and get answer ──────────────────────────────
        choices = _chatbot_choices(driver)

        if llm:
            try:
                answer = llm.answer_chatbot_question(question, choices if choices else None)
            except Exception as e:
                logger.warning("LLM chatbot answer failed: %s", e)
                answer = _fallback_answer(question, choices, cv_data)
        else:
            answer = _fallback_answer(question, choices, cv_data)

        logger.info("Chatbot A: %s", answer)

        # ── fill in the answer ───────────────────────────────────────────────
        if choices:
            if not _chatbot_click_choice(driver, answer):
                # fallback: click first option
                if choices:
                    _chatbot_click_choice(driver, choices[0])
        else:
            _chatbot_type_answer(driver, answer)

        time.sleep(0.5)
        _chatbot_click_save(driver)

    # Try to close the drawer if it's still open
    try:
        close_btn = driver.find_element(By.CSS_SELECTOR, SEL_CHAT_CLOSE)
        driver.execute_script("arguments[0].click();", close_btn)
    except NoSuchElementException:
        pass


def _fallback_answer(question: str, choices: list[str], cv_data) -> str:
    """Rule-based fallback when LLM is unavailable."""
    q = question.lower()
    if choices:
        for c in choices:
            if c.lower() in ("yes", "y"):
                return c
        return choices[0]
    if any(w in q for w in ("year", "years", "experience", "how long", "how many")):
        return str(int(cv_data.experience_years)) if cv_data and cv_data.experience_years else "3"
    if any(w in q for w in ("notice", "notice period")):
        return "30 days"
    if any(w in q for w in ("salary", "ctc", "expected", "package")):
        return "As per industry standards"
    return "Yes"


# ─────────────────────────────────────────────────────────────────────────────
# Main apply function
# ─────────────────────────────────────────────────────────────────────────────

def apply_to_job(
    driver,
    listing: JobListing,
    rate_limiter: RateLimiter,
    cv_data=None,
    llm=None,
) -> ApplicationResult:
    # Skip navigation if get_job_details() already loaded this page
    if driver.current_url.split("?")[0].rstrip("/") != listing.url.rstrip("/"):
        driver.get(listing.url)
        rate_limiter.wait_page_load()

    if _page_requires_login(driver):
        logger.warning("Naukri job page requires login before apply: %s", listing.title)
        return ApplicationResult(success=False, status="error", error="Not logged in — job page shows login/register to apply")

    # Check if already applied
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_ALREADY_APPLIED)
        logger.info("Already applied: %s", listing.title)
        return ApplicationResult(success=False, status="skipped", error="already_applied")
    except NoSuchElementException:
        pass

    # Detect "Apply on company site" button → capture URL and skip
    try:
        driver.find_element(By.CSS_SELECTOR, SEL_EXTERNAL_BTN)
        logger.info("External apply detected: %s", listing.title)
        external_url = _capture_external_url(driver, rate_limiter)
        return ApplicationResult(
            success=False,
            status="skipped_external",
            error="external_apply",
            external_url=external_url,
        )
    except NoSuchElementException:
        pass

    # Find the regular apply button
    apply_btn = None
    for sel in [SEL_APPLY_BTN, SEL_APPLY_BTN_ALT]:
        try:
            candidate = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            if "company site" in candidate.text.lower():
                continue
            apply_btn = candidate
            break
        except TimeoutException:
            continue

    if not apply_btn:
        return ApplicationResult(success=False, status="error", error="Apply button not found")

    try:
        driver.execute_script("arguments[0].click();", apply_btn)
        rate_limiter.wait_page_load()

        # Detect redirect to login page — means session expired / not logged in
        if _page_requires_login(driver):
            logger.warning("Redirected to login page after apply — not logged in: %s", listing.title)
            return ApplicationResult(success=False, status="error", error="Not logged in — redirected to login page")

        # Handle Naukri chatbot drawer if it appears
        _handle_chatbot(driver, llm, cv_data, rate_limiter)

        # Handle confirmation modal if present
        try:
            confirm = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_CONFIRM_BTN))
            )
            confirm.click()
            rate_limiter.wait_page_load()
        except TimeoutException:
            pass

        # Verify success indicator
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SEL_APPLIED_SUCCESS))
            )
            logger.info("Applied successfully: %s @ %s", listing.title, listing.company)
            return ApplicationResult(success=True, status="applied")
        except TimeoutException:
            # Check once more if redirected to login
            if _page_requires_login(driver):
                return ApplicationResult(success=False, status="error", error="Not logged in — redirected to login page")
            logger.warning("No success indicator after apply — marking as error: %s", listing.title)
            return ApplicationResult(success=False, status="error", error="No success confirmation shown after applying")

    except Exception as e:
        logger.error("Error applying to %s: %s", listing.title, e)
        return ApplicationResult(success=False, status="error", error=str(e))
