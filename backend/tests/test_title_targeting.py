"""Job targeting: only titles matching user keywords get scored/applied."""
from core.title_match import title_matches


class TestTitleMatches:
    KW = ["QA Engineer"]

    def test_exact_match(self):
        assert title_matches("QA Engineer", self.KW)

    def test_seniority_prefixes_ignored(self):
        assert title_matches("Senior QA Engineer", self.KW)
        assert title_matches("QA Engineer II", self.KW)

    def test_synonyms(self):
        assert title_matches("Quality Assurance Engineer", self.KW)
        assert title_matches("Software Tester", self.KW)          # qa → tester
        assert title_matches("SDET", ["QA Engineer", "SDET"])

    def test_clear_mismatches_rejected(self):
        assert not title_matches("Sales Executive", self.KW)
        assert not title_matches("HR Recruiter", self.KW)
        assert not title_matches("Delivery Driver", self.KW)
        assert not title_matches("Accountant", self.KW)

    def test_multiple_keywords_any_match(self):
        kws = ["QA Engineer", "Backend Developer"]
        assert title_matches("Python Backend Developer", kws)
        assert title_matches("Automation QA Lead", kws)
        assert not title_matches("Graphic Designer", kws)

    def test_no_keywords_allows_everything(self):
        assert title_matches("Anything At All", [])
        assert title_matches("Anything At All", ["", "  "])

    def test_empty_title_never_matches(self):
        assert not title_matches("", self.KW)


class TestPendingConfirmationStatus:
    def test_applying_can_become_pending(self):
        from core.statuses import AppStatus, can_transition, is_terminal
        assert can_transition(AppStatus.APPLYING, AppStatus.APPLIED_PENDING)
        assert is_terminal(AppStatus.APPLIED_PENDING)
        # only allowed follow-up is a confirmed 'applied'
        assert can_transition(AppStatus.APPLIED_PENDING, AppStatus.APPLIED)
        assert not can_transition(AppStatus.APPLIED_PENDING, AppStatus.FAILED)

    def test_pending_counts_toward_caps_and_dedupe(self, db):
        from api.models import Application
        from api.pipeline import applies_today, is_duplicate_company
        from core.statuses import AppStatus
        db.add(Application(platform="naukri", job_title="QA", company="Acme",
                           job_url="https://x/1", status=AppStatus.APPLIED_PENDING))
        db.commit()
        assert applies_today(db) == 1
        assert is_duplicate_company(db, "Acme")

    def test_pending_counts_as_applied_in_session_counters(self, db):
        from api.models import Application, Session as S
        from api.pipeline import refresh_session_counters
        from core.statuses import AppStatus
        sess = S(platform="naukri", mode="search_and_apply", status="running")
        db.add(sess); db.commit()
        db.add(Application(session_id=sess.id, platform="naukri", job_title="a",
                           status=AppStatus.APPLIED))
        db.add(Application(session_id=sess.id, platform="naukri", job_title="b",
                           status=AppStatus.APPLIED_PENDING))
        db.commit()
        refresh_session_counters(db, sess.id)
        db.refresh(sess)
        assert sess.applied == 2
