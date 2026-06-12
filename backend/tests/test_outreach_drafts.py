"""Email outreach safety: drafts are generated and stored but NEVER sent by
default; sending requires send_after_approval mode + explicit approval."""
import pytest

from api.models import Application, OutreachDraft, Session as SessionModel
from api.pipeline import create_outreach_draft
from core.email_discovery import EmailFinding
from core.outreach import OutreachSendError, generate_outreach_draft, send_outreach_email
from core.statuses import AppStatus, DraftStatus, OutreachMode


class FakeCV:
    name = "Sumit Tiwari"
    skills = ["Python", "Selenium", "FastAPI"]
    experience_years = 4.0
    phone = "+91 9999999999"
    email = "sumit@example-candidate.dev"


class SpySMTPFactory:
    """Records whether any SMTP connection was ever attempted."""
    def __init__(self):
        self.calls = []
        self.sent_messages = []

    def __call__(self, host, port, timeout=30):
        self.calls.append((host, port))
        spy = self

        class _Client:
            def __enter__(self):  return self
            def __exit__(self, *a): return False
            def starttls(self):  pass
            def login(self, u, p): pass
            def send_message(self, msg): spy.sent_messages.append(msg)
        return _Client()


def _make_draft(db, status=DraftStatus.DRAFT):
    sess = SessionModel(platform="naukri", mode="search_and_apply", status="running")
    db.add(sess); db.commit()
    app = Application(session_id=sess.id, platform="naukri", job_title="QA Engineer",
                      company="StartupXYZ", job_url="https://naukri.com/job/1",
                      status=AppStatus.SCORING)
    db.add(app); db.commit()
    finding = EmailFinding(email="priya.sharma@startupxyz.com", source="mailto",
                           source_url="https://naukri.com/job/1")
    draft = create_outreach_draft(db, app, FakeCV(), finding)
    draft.status = status
    db.commit()
    return draft


def test_template_draft_contains_essentials():
    content = generate_outreach_draft(FakeCV(), "QA Engineer", "StartupXYZ",
                                      "https://naukri.com/job/1")
    assert "QA Engineer" in content.subject
    assert "Sumit Tiwari" in content.body
    assert "https://naukri.com/job/1" in content.body


def test_draft_is_stored_with_source_url_and_status(db):
    draft = _make_draft(db)
    row = db.query(OutreachDraft).one()
    assert row.id == draft.id
    assert row.status == DraftStatus.DRAFT
    assert row.recruiter_email == "priya.sharma@startupxyz.com"
    assert row.email_source == "mailto"
    assert row.email_source_url == "https://naukri.com/job/1"
    assert row.subject and row.body


def test_drafting_never_touches_smtp(db, monkeypatch):
    """Creating a draft must not open any SMTP connection."""
    import smtplib
    def _boom(*a, **k):
        raise AssertionError("SMTP must never be used during drafting")
    monkeypatch.setattr(smtplib, "SMTP", _boom)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _boom, raising=False)
    _make_draft(db)  # would raise if SMTP were touched


def test_send_refused_in_default_draft_only_mode(db):
    draft = _make_draft(db, status=DraftStatus.APPROVED)
    spy = SpySMTPFactory()
    with pytest.raises(OutreachSendError, match="disabled"):
        send_outreach_email(draft, OutreachMode.DRAFT_ONLY,
                            {"host": "smtp.example-mail.dev", "from_address": "me@x.dev"},
                            smtp_client_factory=spy)
    assert spy.calls == [], "no SMTP connection may be opened in draft_only mode"


def test_send_refused_in_off_mode(db):
    draft = _make_draft(db, status=DraftStatus.APPROVED)
    spy = SpySMTPFactory()
    with pytest.raises(OutreachSendError):
        send_outreach_email(draft, OutreachMode.OFF,
                            {"host": "smtp.example-mail.dev", "from_address": "me@x.dev"},
                            smtp_client_factory=spy)
    assert spy.calls == []


def test_send_refused_without_explicit_approval(db):
    draft = _make_draft(db, status=DraftStatus.DRAFT)
    spy = SpySMTPFactory()
    with pytest.raises(OutreachSendError, match="approved"):
        send_outreach_email(draft, OutreachMode.SEND_AFTER_APPROVAL,
                            {"host": "smtp.example-mail.dev", "from_address": "me@x.dev"},
                            smtp_client_factory=spy)
    assert spy.calls == []


def test_send_refused_without_smtp_config(db):
    draft = _make_draft(db, status=DraftStatus.APPROVED)
    with pytest.raises(OutreachSendError, match="SMTP"):
        send_outreach_email(draft, OutreachMode.SEND_AFTER_APPROVAL, {})


def test_send_works_only_with_all_gates_passed(db):
    draft = _make_draft(db, status=DraftStatus.APPROVED)
    spy = SpySMTPFactory()
    send_outreach_email(draft, OutreachMode.SEND_AFTER_APPROVAL,
                        {"host": "smtp.example-mail.dev", "from_address": "me@x.dev"},
                        smtp_client_factory=spy)
    assert len(spy.sent_messages) == 1
    assert spy.sent_messages[0]["To"] == "priya.sharma@startupxyz.com"
