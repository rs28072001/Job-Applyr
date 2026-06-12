"""SMTP/Gmail config validation, test email, and the immutable send log."""
import pytest

from core.outreach import OutreachSendError, send_test_email, validate_smtp_settings


GOOD = {"host": "smtp.example-mail.dev", "port": 587,
        "username": "me@example-mail.dev", "password": "secret",
        "from_address": "me@example-mail.dev"}


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=20):
        self.host, self.port = host, port
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): pass
    def login(self, u, p): self.creds = (u, p)
    def send_message(self, msg): self.sent.append(msg)


class TestValidation:
    def test_valid_settings_pass(self):
        assert validate_smtp_settings(GOOD) == []

    def test_missing_host(self):
        problems = validate_smtp_settings({**GOOD, "host": ""})
        assert any("host" in p.lower() for p in problems)

    def test_bad_from_address(self):
        problems = validate_smtp_settings({**GOOD, "from_address": "not-an-email", "username": ""})
        assert any("not a valid email" in p for p in problems)

    def test_username_without_password(self):
        problems = validate_smtp_settings({**GOOD, "password": ""})
        assert any("password is empty" in p for p in problems)

    def test_gmail_hint_for_missing_app_password(self):
        problems = validate_smtp_settings({**GOOD, "host": "smtp.gmail.com", "password": ""})
        assert any("App Password" in p for p in problems)

    def test_implicit_ssl_port_rejected(self):
        problems = validate_smtp_settings({**GOOD, "port": 465})
        assert any("465" in p for p in problems)


class TestSendTestEmail:
    def setup_method(self):
        FakeSMTP.instances = []

    def test_sends_to_self_by_default(self):
        recipient = send_test_email(GOOD, smtp_client_factory=FakeSMTP)
        assert recipient == "me@example-mail.dev"
        assert len(FakeSMTP.instances) == 1
        msg = FakeSMTP.instances[0].sent[0]
        assert msg["To"] == "me@example-mail.dev"
        assert "SMTP test" in msg["Subject"]

    def test_invalid_settings_never_connect(self):
        with pytest.raises(OutreachSendError):
            send_test_email({**GOOD, "host": ""}, smtp_client_factory=FakeSMTP)
        assert FakeSMTP.instances == []

    def test_invalid_recipient_rejected(self):
        with pytest.raises(OutreachSendError, match="not a valid email"):
            send_test_email(GOOD, "bogus", smtp_client_factory=FakeSMTP)
        assert FakeSMTP.instances == []


class TestSendLog:
    def _draft(self, db):
        from api.models import Application, OutreachDraft, Session as S
        from core.statuses import AppStatus, DraftStatus
        sess = S(platform="naukri", mode="search_and_apply", status="completed")
        db.add(sess); db.commit()
        app = Application(session_id=sess.id, platform="naukri",
                          job_title="QA Engineer", company="StartupXYZ",
                          job_url="https://x/1", status=AppStatus.EMAIL_DRAFTED)
        db.add(app); db.commit()
        draft = OutreachDraft(application_id=app.id, session_id=sess.id,
                              recruiter_email="hr@startupxyz.com",
                              subject="Application for QA Engineer",
                              body="...", status=DraftStatus.APPROVED)
        db.add(draft); db.commit()
        return draft

    def test_mark_sent_writes_complete_log_row(self, db):
        from api.models import OutreachSendLog
        from api.routes.review import _mark_sent
        draft = self._draft(db)
        _mark_sent(draft, db, method="smtp")
        log = db.query(OutreachSendLog).one()
        assert log.job_title == "QA Engineer"
        assert log.company == "StartupXYZ"
        assert log.recipient == "hr@startupxyz.com"
        assert log.subject == "Application for QA Engineer"
        assert log.method == "smtp"
        assert log.sent_at is not None
        assert log.draft_id == draft.id

    def test_application_status_becomes_email_sent(self, db):
        from api.models import Application
        from api.routes.review import _mark_sent
        from core.statuses import AppStatus
        draft = self._draft(db)
        _mark_sent(draft, db, method="user_mail_client")
        app = db.get(Application, draft.application_id)
        assert app.status == AppStatus.EMAIL_SENT
