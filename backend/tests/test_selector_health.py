"""Selector resilience: fallback lists validate against DOM snapshot fixtures,
and selector failures route jobs to manual review."""
from conftest import FIXTURES, load_fixture

from core.selector_health import (
    EXPECTATIONS, TEXT_EXPECTATIONS, html_matches_selector, run_selector_health_check,
    live_selector_incidents,
)
from core.selectors import SELECTORS


class TestHealthCheck:
    def test_all_selector_groups_pass_against_fixtures(self):
        report = run_selector_health_check()
        assert report.ok, f"broken selector groups: {report.broken}"

    def test_every_expectation_has_a_fixture(self):
        for _, _, fixture in EXPECTATIONS:
            assert (FIXTURES / fixture).exists(), f"missing fixture {fixture}"
        for _, fixture in TEXT_EXPECTATIONS:
            assert (FIXTURES / fixture).exists(), f"missing fixture {fixture}"

    def test_broken_selector_is_detected(self):
        # A selector that matches nothing must be reported as broken.
        html = load_fixture("naukri_internal_apply.html")
        assert not html_matches_selector(html, "button#totally-renamed-button")

    def test_matcher_handles_spaces_in_attribute_values(self):
        html = load_fixture("linkedin_external_apply.html")
        assert html_matches_selector(html, "button[aria-label*='Apply on company website']")

    def test_fallback_order_first_match_wins(self):
        html = load_fixture("naukri_internal_apply.html")
        matched = [s for s in SELECTORS["naukri"]["internal_apply_button"]
                   if html_matches_selector(html, s)]
        assert matched, "at least one fallback must match the snapshot"


class TestLiveIncidents:
    def test_counts_selector_failures_from_rows(self, db):
        from api.models import Application
        db.add(Application(platform="naukri", job_title="a", status="manual_review",
                           failure_reason="apply_button_not_found"))
        db.add(Application(platform="naukri", job_title="b", status="failed",
                           failure_reason="confirmation_missing"))
        db.add(Application(platform="naukri", job_title="c", status="skipped",
                           failure_reason="below_threshold"))  # not selector-related
        db.commit()
        counts = live_selector_incidents(db, hours=24)
        assert counts == {"apply_button_not_found": 1, "confirmation_missing": 1}
