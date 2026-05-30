import functools
import time
import logging

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

logger = logging.getLogger(__name__)


def selenium_retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    exceptions: tuple = (StaleElementReferenceException, TimeoutException),
):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                        attempt + 1,
                        max_attempts,
                        func.__name__,
                        type(e).__name__,
                        delay,
                    )
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
