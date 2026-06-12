"""Stop semantics: stopping a session IMMEDIATELY persists 'stopped' on the
session row and on every in-flight application row."""
from api.models import Application, Session as SessionModel
from api.pipeline import mark_session_stopped
from core.statuses import ACTIVE_STATUSES, AppStatus, FailureReason


def _make_session(db):
    sess = SessionModel(platform="both", mode="search_and_apply", status="running")
    db.add(sess); db.commit()
    return sess


def _add_app(db, sess, status, title="job"):
    app = Application(session_id=sess.id, platform="naukri", job_title=title,
                      job_url=f"https://x/{title}", status=status)
    db.add(app); db.commit()
    return app


def test_stop_marks_session_stopped_immediately(db):
    sess = _make_session(db)
    mark_session_stopped(db, sess.id)
    db.refresh(sess)
    assert sess.status == "stopped"
    assert sess.ended_at is not None


def test_stop_marks_all_active_rows_stopped(db):
    sess = _make_session(db)
    active = [_add_app(db, sess, s, f"a-{s}") for s in ACTIVE_STATUSES]
    n = mark_session_stopped(db, sess.id)
    assert n == len(active)
    for app in active:
        db.refresh(app)
        assert app.status == AppStatus.STOPPED
        assert app.failure_reason == FailureReason.SESSION_STOPPED


def test_stop_preserves_terminal_and_reviewable_rows(db):
    sess = _make_session(db)
    applied = _add_app(db, sess, AppStatus.APPLIED, "applied")
    review  = _add_app(db, sess, AppStatus.MANUAL_REVIEW, "review")
    saved   = _add_app(db, sess, AppStatus.SAVED, "saved")
    drafted = _add_app(db, sess, AppStatus.EMAIL_DRAFTED, "drafted")
    skipped = _add_app(db, sess, AppStatus.SKIPPED, "skipped")
    mark_session_stopped(db, sess.id)
    for app, expected in [(applied, AppStatus.APPLIED), (review, AppStatus.MANUAL_REVIEW),
                          (saved, AppStatus.SAVED),
                          (drafted, AppStatus.EMAIL_DRAFTED), (skipped, AppStatus.SKIPPED)]:
        db.refresh(app)
        assert app.status == expected


def test_stop_is_idempotent(db):
    sess = _make_session(db)
    _add_app(db, sess, AppStatus.SCORING)
    mark_session_stopped(db, sess.id)
    n_second = mark_session_stopped(db, sess.id)
    assert n_second == 0
    db.refresh(sess)
    assert sess.status == "stopped"


def test_stop_refreshes_counters_from_rows(db):
    sess = _make_session(db)
    _add_app(db, sess, AppStatus.APPLIED, "ok1")
    _add_app(db, sess, AppStatus.APPLIED, "ok2")
    _add_app(db, sess, AppStatus.FAILED, "bad")
    _add_app(db, sess, AppStatus.APPLYING, "inflight")
    mark_session_stopped(db, sess.id)
    db.refresh(sess)
    assert sess.applied == 2
    assert sess.errors == 1
