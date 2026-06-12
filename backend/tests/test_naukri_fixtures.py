"""Naukri fixture coverage: internal apply, external apply, no apply button,
login required, and visible recruiter email."""
from conftest import load_fixture

from core.job_classifier import classify_job, route_classification
from core.page_signals import signals_from_html
from core.statuses import AppStatus, FailureReason, JobClassification, OutreachMode


def _sig(name, platform="naukri"):
    return signals_from_html(load_fixture(name), platform)


class TestInternalApply:
    def test_signals(self):
        sig = _sig("naukri_internal_apply.html")
        assert sig.has_internal_apply
        assert not sig.has_external_apply
        assert not sig.requires_login

    def test_classification(self):
        assert classify_job(_sig("naukri_internal_apply.html")) == \
            JobClassification.PLATFORM_INTERNAL_APPLY


class TestExternalApply:
    def test_signals(self):
        sig = _sig("naukri_external_apply.html")
        assert sig.has_external_apply
        assert not sig.has_internal_apply

    def test_routed_to_saved(self):
        sig = _sig("naukri_external_apply.html")
        decision = route_classification(classify_job(sig), sig)
        assert decision.status == AppStatus.SAVED
        assert decision.failure_reason == FailureReason.EXTERNAL_SITE


class TestNoApplyButton:
    def test_classified_manual_review(self):
        sig = _sig("naukri_no_apply_button.html")
        assert not sig.has_internal_apply and not sig.has_external_apply
        assert classify_job(sig) == JobClassification.MANUAL_REVIEW

    def test_routed_with_explicit_reason(self):
        sig = _sig("naukri_no_apply_button.html")
        decision = route_classification(JobClassification.MANUAL_REVIEW, sig)
        assert decision.status == AppStatus.MANUAL_REVIEW
        assert decision.failure_reason == FailureReason.APPLY_BUTTON_NOT_FOUND


class TestLoginRequired:
    def test_signals(self):
        assert _sig("naukri_login_required.html").requires_login

    def test_classified_unsupported_and_failed_with_reason(self):
        sig = _sig("naukri_login_required.html")
        c = classify_job(sig)
        assert c == JobClassification.UNSUPPORTED
        decision = route_classification(c, sig)
        assert decision.status == AppStatus.FAILED
        assert decision.failure_reason == FailureReason.LOGIN_REQUIRED


class TestVisibleRecruiterEmail:
    def test_visible_and_mailto_emails_found(self):
        sig = _sig("naukri_recruiter_email.html")
        emails = {f.email for f in sig.visible_emails}
        assert "priya.sharma@startupxyz.com" in emails   # mailto link
        assert "careers.hr@startupxyz.com" in emails     # visible JD text

    def test_hidden_and_script_emails_never_extracted(self):
        sig = _sig("naukri_recruiter_email.html")
        emails = {f.email for f in sig.visible_emails}
        assert "secret.hidden@startupxyz.com" not in emails   # inside <script>
        assert "internal-only@startupxyz.com" not in emails   # display:none
        assert "noreply@naukri.com" not in emails             # junk + platform domain

    def test_classified_as_outreach_candidate(self):
        sig = _sig("naukri_recruiter_email.html")
        assert classify_job(sig, outreach_mode=OutreachMode.DRAFT_ONLY) == \
            JobClassification.EMAIL_OUTREACH_CANDIDATE

    def test_outreach_off_falls_back_to_saved(self):
        sig = _sig("naukri_recruiter_email.html")
        c = classify_job(sig, outreach_mode=OutreachMode.OFF)
        assert c == JobClassification.EXTERNAL_ATS
        decision = route_classification(
            JobClassification.EMAIL_OUTREACH_CANDIDATE, sig,
            outreach_mode=OutreachMode.OFF)
        assert decision.status == AppStatus.SAVED

    def test_mailto_finding_is_preferred_first(self):
        sig = _sig("naukri_recruiter_email.html")
        assert sig.visible_emails[0].source == "mailto"
