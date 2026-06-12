"""Session audit log and failed-job evidence capture."""
import pathlib

from api.models import Application, AuditEvent, Session as SessionModel
from api.pipeline import finalize_session, mark_session_stopped, set_app_status
from core.audit import log_event
from core.evidence import capture_evidence
from core.statuses import AppStatus, FailureReason


class TestAuditLog:
    def test_status_changes_are_audited(self, db):
        sess = SessionModel(platform="naukri", mode="search_and_apply", status="running")
        db.add(sess); db.commit()
        app = Application(session_id=sess.id, platform="naukri", job_title="X",
                          status=AppStatus.QUEUED)
        db.add(app); db.commit()

        set_app_status(db, app, AppStatus.FETCHING, emit=False)
        set_app_status(db, app, AppStatus.SCORING, emit=False)
        set_app_status(db, app, AppStatus.SKIPPED,
                       failure_reason=FailureReason.BELOW_THRESHOLD, emit=False)

        events = db.query(AuditEvent).filter_by(session_id=sess.id,
                                                event_type="status_change").all()
        assert [e.detail["status"] for e in events] == ["fetching", "scoring", "skipped"]
        assert events[-1].detail["failure_reason"] == FailureReason.BELOW_THRESHOLD  # "low_score"
        assert all(e.application_id == app.id for e in events)

    def test_stop_and_finalize_are_audited(self, db):
        sess = SessionModel(platform="naukri", mode="search_and_apply", status="running")
        db.add(sess); db.commit()
        mark_session_stopped(db, sess.id)
        types = {e.event_type for e in db.query(AuditEvent).filter_by(session_id=sess.id)}
        assert "session_stopped" in types

        sess2 = SessionModel(platform="naukri", mode="search_and_apply", status="running")
        db.add(sess2); db.commit()
        finalize_session(db, sess2.id, stopped=False)
        types2 = {e.event_type for e in db.query(AuditEvent).filter_by(session_id=sess2.id)}
        assert "session_finalized" in types2

    def test_audit_failures_never_raise(self, db):
        # Even with a broken payload the helper must not blow up the pipeline.
        log_event(db, None, "weird_event", {"x": object()})  # non-JSON value


class FakeDriver:
    current_url = "https://www.naukri.com/job-view/test-job-123"
    page_source = ("<html><head><script>secret()</script></head>"
                   "<body><h1>QA Engineer</h1><p>Apply flow broke here.</p></body></html>")

    def save_screenshot(self, path):
        pathlib.Path(path).write_bytes(b"\x89PNG fake")
        return True


class TestEvidenceCapture:
    def test_capture_writes_screenshot_and_text(self, tmp_path):
        out = capture_evidence(FakeDriver(), 42, base_dir=tmp_path)
        d = pathlib.Path(out)
        assert d.name == "app_42"
        assert (d / "page.png").exists()
        text = (d / "page.txt").read_text()
        assert "naukri.com/job-view/test-job-123" in text
        assert "Apply flow broke here." in text
        assert "secret()" not in text  # scripts stripped

    def test_capture_never_raises_on_broken_driver(self, tmp_path):
        class BrokenDriver:
            @property
            def current_url(self): raise RuntimeError("gone")
            @property
            def page_source(self): raise RuntimeError("gone")
            def save_screenshot(self, p): raise RuntimeError("gone")
        out = capture_evidence(BrokenDriver(), 1, base_dir=tmp_path)
        assert out  # directory still created with empty text file
