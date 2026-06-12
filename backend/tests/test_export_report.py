"""Export report: exact CSV schema, empty strings for missing values, all
jobs from the selected session."""
from api.models import Application, Session as SessionModel
from api.routes.reports import CSV_COLUMNS, _report_payload, application_csv_row
from core.statuses import AppStatus

REQUIRED = ["timestamp", "platform", "company", "company_logo_url", "job_title",
            "location", "experience_required", "salary", "confidence",
            "job_status", "posted_date", "openings", "applicants_count",
            "key_skills", "matched_skills", "missing_skills",
            "external_site_url", "about_company", "job_description", "job_url"]


def _session_with_jobs(db):
    sess = SessionModel(platform="naukri", mode="search_and_apply", status="completed")
    db.add(sess); db.commit()
    full = Application(
        session_id=sess.id, platform="naukri", job_title="QA Engineer",
        company="TechCorp", company_logo_url="https://img/logo.png",
        job_url="https://x/1", location="Gurugram", experience_required="3-6 Yrs",
        salary="12-18 LPA", score=84, status=AppStatus.APPLIED,
        recommendation="apply", posted_date="2 days ago", openings="3",
        applicants_count="120", key_skills=["Selenium", "Python"],
        matched_skills=["Selenium"], missing_skills=["Rust"],
        external_site_url="", about_company="A tech company.",
        job_description="Automate things.",
    )
    sparse = Application(  # queued row — everything optional missing
        session_id=sess.id, platform="naukri", job_title="Mystery Role",
        company="", job_url="https://x/2", status=AppStatus.QUEUED, score=0,
    )
    db.add_all([full, sparse]); db.commit()
    return sess, full, sparse


class TestCsvSchema:
    def test_columns_exactly_match_spec(self):
        assert CSV_COLUMNS == REQUIRED

    def test_full_row_values(self, db):
        sess, full, _ = _session_with_jobs(db)
        row = dict(zip(CSV_COLUMNS, application_csv_row(full)))
        assert row["platform"] == "naukri"
        assert row["company_logo_url"] == "https://img/logo.png"
        assert row["confidence"] == "84"
        assert row["job_status"] == "applied"
        assert row["key_skills"] == "Selenium, Python"
        assert row["matched_skills"] == "Selenium"
        assert row["missing_skills"] == "Rust"
        assert row["job_url"] == "https://x/1"

    def test_missing_values_are_empty_strings(self, db):
        sess, _, sparse = _session_with_jobs(db)
        row = dict(zip(CSV_COLUMNS, application_csv_row(sparse)))
        for col in ["company", "company_logo_url", "location", "experience_required",
                    "salary", "posted_date", "openings", "applicants_count",
                    "key_skills", "matched_skills", "missing_skills",
                    "external_site_url", "about_company", "job_description"]:
            assert row[col] == "", f"{col} should be empty string, got {row[col]!r}"
        # never scored → confidence blank, not 0
        assert row["confidence"] == ""
        assert row["job_status"] == "queued"

    def test_zero_score_with_recommendation_is_exported_as_zero(self, db):
        sess, full, _ = _session_with_jobs(db)
        full.score = 0
        full.recommendation = "skip"
        db.commit()
        row = dict(zip(CSV_COLUMNS, application_csv_row(full)))
        assert row["confidence"] == "0"

    def test_export_includes_all_session_jobs(self, db):
        sess, _, _ = _session_with_jobs(db)
        payload = _report_payload(sess.id, db)
        assert len(payload["_rows"]) == 2
        assert payload["totals"]["jobs"] == 2
