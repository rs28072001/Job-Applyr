"""Easy Apply filtering: LinkedIn uses the platform filter, Naukri Easy Apply
means internal apply/chatbot only, and non-easy-apply jobs never auto-apply."""
from conftest import load_fixture

from core.job_classifier import classify_job, route_classification, AUTO_APPLY_CLASSIFICATIONS
from core.page_signals import signals_from_html
from core.statuses import AppStatus, FailureReason, JobClassification
from platforms.linkedin.search import build_search_url


class TestLinkedInEasyApplyFilter:
    def test_easy_apply_filter_on_by_default(self):
        url = build_search_url(["QA Engineer"], "Bengaluru")
        assert "f_LF=f_AL" in url, "LinkedIn platform Easy Apply filter must be applied"

    def test_easy_apply_filter_explicit_on(self):
        assert "f_LF=f_AL" in build_search_url(["QA"], "Pune", easy_apply_only=True)

    def test_filter_removed_only_when_disabled(self):
        assert "f_LF=f_AL" not in build_search_url(["QA"], "Pune", easy_apply_only=False)

    def test_keywords_and_location_encoded(self):
        url = build_search_url(["QA Engineer"], "New Delhi")
        assert "QA+Engineer" in url and "New+Delhi" in url

    def test_linkedin_easy_apply_page_classified_for_auto_apply(self):
        sig = signals_from_html(load_fixture("linkedin_easy_apply.html"), "linkedin")
        assert classify_job(sig) == JobClassification.PLATFORM_EASY_APPLY
        assert route_classification(JobClassification.PLATFORM_EASY_APPLY, sig).action == "proceed"

    def test_linkedin_external_page_never_auto_applied(self):
        sig = signals_from_html(load_fixture("linkedin_external_apply.html"), "linkedin")
        c = classify_job(sig)
        assert c == JobClassification.EXTERNAL_ATS
        assert c not in AUTO_APPLY_CLASSIFICATIONS
        decision = route_classification(c, sig, include_external_review=True)
        assert decision.action == "finalize"
        assert decision.status == AppStatus.SAVED   # auto-saved, never auto-driven


class TestNaukriEasyApplyMeansInternalOnly:
    def test_internal_apply_is_easy_apply(self):
        sig = signals_from_html(load_fixture("naukri_internal_apply.html"), "naukri")
        assert classify_job(sig) == JobClassification.PLATFORM_INTERNAL_APPLY

    def test_external_apply_is_not_easy_apply(self):
        sig = signals_from_html(load_fixture("naukri_external_apply.html"), "naukri")
        c = classify_job(sig)
        assert c == JobClassification.EXTERNAL_ATS
        assert c not in AUTO_APPLY_CLASSIFICATIONS

    def test_external_is_saved_automatically_not_silent_failure(self):
        sig = signals_from_html(load_fixture("naukri_external_apply.html"), "naukri")
        decision = route_classification(JobClassification.EXTERNAL_ATS, sig,
                                        include_external_review=True)
        assert decision.status == AppStatus.SAVED
        assert decision.failure_reason == FailureReason.EXTERNAL_SITE

    def test_external_skipped_with_visible_reason_when_review_disabled(self):
        sig = signals_from_html(load_fixture("naukri_external_apply.html"), "naukri")
        decision = route_classification(JobClassification.EXTERNAL_ATS, sig,
                                        include_external_review=False)
        assert decision.status == AppStatus.SKIPPED
        assert decision.failure_reason == FailureReason.EXTERNAL_SITE  # never silent
