"""Account-safe automation limits: persisted daily cap, per-company dedupe,
human pacing, and exponential (capped) backoff."""
from datetime import datetime, timedelta, timezone

from api.models import Application
from api.pipeline import applies_today, daily_cap_reached, is_duplicate_company
from api.session_manager import BACKOFF_SECONDS, _backoff_seconds
from core.statuses import AppStatus


def _applied(db, company="X Corp", days_ago=0.0, status=AppStatus.APPLIED, url="https://x/1"):
    app = Application(platform="naukri", job_title="role", company=company,
                      job_url=url, status=status)
    db.add(app); db.commit()
    if days_ago:
        app.timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.commit()
    return app


class TestDailyCap:
    def test_cap_counts_only_last_24h_applies(self, db):
        _applied(db, url="https://x/1")
        _applied(db, url="https://x/2", days_ago=2)  # outside window
        _applied(db, url="https://x/3", status=AppStatus.SKIPPED)  # not an apply
        assert applies_today(db) == 1

    def test_cap_reached(self, db):
        for i in range(3):
            _applied(db, url=f"https://x/{i}")
        assert daily_cap_reached(db, 3)
        assert not daily_cap_reached(db, 4)


class TestCompanyDedupe:
    def test_recent_apply_to_company_blocks_reapply(self, db):
        _applied(db, company="Acme Pvt Ltd")
        assert is_duplicate_company(db, "Acme Pvt Ltd")
        assert is_duplicate_company(db, "acme pvt ltd")  # case-insensitive

    def test_old_application_does_not_block(self, db):
        _applied(db, company="Acme Pvt Ltd", days_ago=10)
        assert not is_duplicate_company(db, "Acme Pvt Ltd", days=7)

    def test_skipped_rows_do_not_block(self, db):
        _applied(db, company="Acme Pvt Ltd", status=AppStatus.SKIPPED)
        assert not is_duplicate_company(db, "Acme Pvt Ltd")

    def test_email_outreach_counts_as_contact(self, db):
        _applied(db, company="Acme Pvt Ltd", status=AppStatus.EMAIL_DRAFTED)
        assert is_duplicate_company(db, "Acme Pvt Ltd")

    def test_empty_company_never_blocks(self, db):
        assert not is_duplicate_company(db, "")


class TestBackoff:
    def test_exponential_growth(self):
        assert _backoff_seconds(1) == BACKOFF_SECONDS
        assert _backoff_seconds(2) == BACKOFF_SECONDS * 2
        assert _backoff_seconds(3) == BACKOFF_SECONDS * 4

    def test_capped_at_ten_minutes(self):
        assert _backoff_seconds(10) == 600


class TestHumanPacing:
    def test_between_jobs_delay_is_seconds_not_millis(self, monkeypatch):
        from utils.rate_limiter import RateLimiter
        slept = []
        monkeypatch.setattr("utils.rate_limiter.time.sleep", lambda s: slept.append(s))
        RateLimiter().wait_between_jobs()
        assert 4 <= slept[0] <= 9
