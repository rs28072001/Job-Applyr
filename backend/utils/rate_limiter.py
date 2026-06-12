import random
import time
from collections import deque
from datetime import datetime, timedelta


class RateLimitExceededError(Exception):
    pass


class RateLimiter:
    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 2.5,
        max_per_hour: int = 30,
        max_per_day: int = 150,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self._hourly: deque = deque()
        self._daily: deque = deque()

    def _purge_old(self) -> None:
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        while self._hourly and self._hourly[0] < hour_ago:
            self._hourly.popleft()
        while self._daily and self._daily[0] < day_ago:
            self._daily.popleft()

    def record_action(self) -> None:
        now = datetime.now()
        self._purge_old()
        if len(self._hourly) >= self.max_per_hour:
            raise RateLimitExceededError(
                f"Hourly limit of {self.max_per_hour} actions reached. "
                "Wait before continuing."
            )
        if len(self._daily) >= self.max_per_day:
            raise RateLimitExceededError(
                f"Daily limit of {self.max_per_day} actions reached. "
                "Resume tomorrow."
            )
        self._hourly.append(now)
        self._daily.append(now)

    def wait(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        delay += random.gauss(0, 0.2)
        delay = max(0.5, delay)
        time.sleep(delay)

    def wait_after_apply(self) -> None:
        time.sleep(random.uniform(3, 6))

    def wait_between_jobs(self) -> None:
        """Human-paced pause between processing consecutive jobs."""
        time.sleep(random.uniform(4, 9))

    def wait_page_load(self) -> None:
        time.sleep(random.uniform(0.5, 1.2))

    @staticmethod
    def human_type(driver, element, text: str) -> None:
        element.clear()
        for i, char in enumerate(text):
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
            if i > 0 and i % random.randint(4, 8) == 0:
                time.sleep(random.uniform(0.1, 0.4))
