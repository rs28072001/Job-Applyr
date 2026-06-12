from datetime import timedelta

from api.models import Application, IgnoredJob, Session
from api.pipeline import set_app_status
from core.date_filters import is_within_posted_filter, linkedin_time_filter, posted_age_days
from core.ignored_jobs import add_ignored_job, find_ignored_job, mark_expired, now_utc
from core.statuses import AppStatus, FailureReason


def test_skipped_job_is_inserted_into_ignored_jobs(db):
    sess = Session(platform="naukri", mode="search", auto_ignore_skipped=True)
    db.add(sess); db.commit()
    app = Application(session_id=sess.id, platform="naukri", company="Oodles Technologies",
                      job_title="Odoo Developer", job_url="https://naukri.com/job/1",
                      status=AppStatus.QUEUED)
    db.add(app); db.commit()

    set_app_status(db, app, AppStatus.SKIPPED, failure_reason=FailureReason.LLM_RECOMMENDED_SKIP)

    row = db.query(IgnoredJob).one()
    assert row.company == "Oodles Technologies"
    assert row.job_title == "Odoo Developer"
    assert row.ignore_reason == FailureReason.LLM_RECOMMENDED_SKIP
    assert row.status == "active"


def test_same_job_url_is_ignored_next_session(db):
    add_ignored_job(db, platform="naukri", company="A", title="DevOps Engineer",
                    url="https://naukri.com/job/123?src=x", reason="ai_skip")

    found = find_ignored_job(db, platform="naukri", company="Other", title="Different",
                             url="https://naukri.com/job/123")

    assert found is not None
    assert found.ignore_reason == "ai_skip"


def test_same_company_title_is_ignored_when_url_changes(db):
    add_ignored_job(db, platform="naukri", company="Oodles Technologies",
                    title="Odoo Developer ( DM - 4347 )", url="", reason="title_mismatch")

    found = find_ignored_job(db, platform="naukri", company="oodles technologies",
                             title="Odoo Developer DM 4347", url="https://naukri.com/new-url")

    assert found is not None


def test_unignore_allows_job_to_appear_again(db):
    row = add_ignored_job(db, platform="naukri", company="A", title="QA", url="https://x/qa",
                          reason="low_score")
    row.status = "removed"
    db.commit()

    assert find_ignored_job(db, platform="naukri", company="A", title="QA", url="https://x/qa") is None


def test_expired_rows_are_not_matched(db):
    row = add_ignored_job(db, platform="naukri", company="A", title="QA", url="https://x/qa",
                          reason="low_score")
    row.expires_at = now_utc() - timedelta(days=1)
    db.commit()

    assert mark_expired(db) == 1
    assert find_ignored_job(db, platform="naukri", company="A", title="QA", url="https://x/qa") is None


def test_date_posted_filter_helpers():
    assert posted_age_days("Posted: 2 days ago") == 2
    assert is_within_posted_filter("3 weeks ago", "7d") is False
    assert is_within_posted_filter("few hours ago", "24h") is True
    assert is_within_posted_filter("", "24h") is True
    assert linkedin_time_filter("7d") == "r604800"
