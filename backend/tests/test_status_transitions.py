"""Lifecycle guarantees: explicit states, guarded transitions, no row ever
stuck in an in-flight ('analysing') state, apply gated on LLM recommendation."""
from api.models import Application, Session as SessionModel
from api.pipeline import decide_apply, finalize_session, set_app_status
from core.statuses import (
    ACTIVE_STATUSES, AppStatus, FailureReason, can_transition, is_terminal,
)


class TestTransitionRules:
    def test_happy_path_apply(self):
        path = [AppStatus.QUEUED, AppStatus.FETCHING, AppStatus.SCORING,
                AppStatus.APPLYING, AppStatus.APPLIED]
        for a, b in zip(path, path[1:]):
            assert can_transition(a, b), f"{a} → {b} must be allowed"

    def test_happy_path_outreach(self):
        assert can_transition(AppStatus.SCORING, AppStatus.EMAIL_DRAFTED)
        assert can_transition(AppStatus.EMAIL_DRAFTED, AppStatus.EMAIL_SENT)

    def test_terminal_states_are_final(self):
        for terminal in (AppStatus.APPLIED, AppStatus.SKIPPED, AppStatus.FAILED,
                         AppStatus.STOPPED, AppStatus.EMAIL_SENT):
            assert is_terminal(terminal)
            for other in AppStatus.ALL:
                if other != terminal:
                    assert not can_transition(terminal, other)

    def test_every_active_state_can_be_stopped_or_failed(self):
        for active in ACTIVE_STATUSES:
            assert can_transition(active, AppStatus.STOPPED)
            assert can_transition(active, AppStatus.FAILED)

    def test_applied_cannot_be_clobbered_in_db(self, db):
        app = Application(platform="naukri", job_title="X", status=AppStatus.APPLIED)
        db.add(app); db.commit()
        changed = set_app_status(db, app, AppStatus.SKIPPED, emit=False)
        assert changed is False
        assert app.status == AppStatus.APPLIED


class TestApplyDecision:
    def test_apply_requires_both_recommendation_and_score(self):
        ok, _ = decide_apply("apply", 80, 75)
        assert ok

    def test_skip_recommendation_always_honoured(self):
        ok, reason = decide_apply("skip", 99, 75)
        assert not ok
        assert reason == FailureReason.LLM_RECOMMENDED_SKIP

    def test_below_threshold_never_applies(self):
        ok, reason = decide_apply("apply", 60, 75)
        assert not ok
        assert reason == FailureReason.BELOW_THRESHOLD

    def test_missing_recommendation_treated_as_skip(self):
        ok, _ = decide_apply("", 100, 75)
        assert not ok


class TestNoStuckRows:
    """Rows must never remain in an in-flight ('analysing') state."""

    def _session_with_inflight_rows(self, db):
        sess = SessionModel(platform="naukri", mode="search_and_apply", status="running")
        db.add(sess); db.commit()
        rows = {}
        for status in [AppStatus.QUEUED, AppStatus.FETCHING, AppStatus.SCORING,
                       AppStatus.APPLYING, AppStatus.APPLIED, AppStatus.MANUAL_REVIEW,
                       AppStatus.EMAIL_DRAFTED]:
            app = Application(session_id=sess.id, platform="naukri",
                              job_title=f"job-{status}", job_url=f"https://x/{status}",
                              status=status)
            db.add(app)
            rows[status] = app
        db.commit()
        return sess, rows

    def test_finalize_completed_session_leaves_no_inflight_rows(self, db):
        sess, rows = self._session_with_inflight_rows(db)
        finalize_session(db, sess.id, stopped=False)
        for status in ACTIVE_STATUSES:
            db.refresh(rows[status])
            assert rows[status].status not in ACTIVE_STATUSES
            assert rows[status].status == AppStatus.FAILED
        # Reviewable & terminal rows untouched
        assert rows[AppStatus.APPLIED].status == AppStatus.APPLIED
        assert rows[AppStatus.MANUAL_REVIEW].status == AppStatus.MANUAL_REVIEW
        assert rows[AppStatus.EMAIL_DRAFTED].status == AppStatus.EMAIL_DRAFTED

    def test_finalize_marks_session_completed(self, db):
        sess, _ = self._session_with_inflight_rows(db)
        finalize_session(db, sess.id, stopped=False)
        db.refresh(sess)
        assert sess.status == "completed"
        assert sess.ended_at is not None

    def test_counters_reflect_persisted_rows(self, db):
        sess, rows = self._session_with_inflight_rows(db)
        finalize_session(db, sess.id, stopped=False)
        db.refresh(sess)
        persisted_applied = sum(1 for a in db.query(Application).filter_by(session_id=sess.id)
                                if a.status == AppStatus.APPLIED)
        assert sess.applied == persisted_applied == 1
        assert sess.errors == 4  # the four in-flight rows finalized as failed
