"""Email discovery only ever reads visible public content."""
from core.email_discovery import extract_visible_emails


def test_extracts_mailto_and_visible_text():
    html = """
    <body>
      <p>Send your CV to hr@acmecorp.in today.</p>
      <a href="mailto:recruiter@acmecorp.in?subject=Job">Email us</a>
    </body>"""
    emails = {f.email for f in extract_visible_emails(html)}
    assert emails == {"hr@acmecorp.in", "recruiter@acmecorp.in"}


def test_ignores_script_style_comments_and_hidden():
    html = """
    <head>
      <script>var a = "tracker@acmecorp.in";</script>
      <style>/* css-owner@acmecorp.in */</style>
    </head>
    <body>
      <!-- commented@acmecorp.in -->
      <div style="display:none">hidden@acmecorp.in</div>
      <div hidden>also-hidden@acmecorp.in</div>
      <p>visible@acmecorp.in</p>
    </body>"""
    emails = {f.email for f in extract_visible_emails(html)}
    assert emails == {"visible@acmecorp.in"}


def test_filters_junk_and_platform_addresses():
    html = """
    <body>
      <p>noreply@acmecorp.in support is automated.</p>
      <p>test@example.com is a placeholder.</p>
      <p>feedback@naukri.com and contact@linkedin.com are platform addresses.</p>
      <p>Real contact: talent@acmecorp.in</p>
    </body>"""
    emails = {f.email for f in extract_visible_emails(html)}
    assert emails == {"talent@acmecorp.in"}


def test_dedupes_and_records_source_url():
    html = '<a href="mailto:hr@x-co.dev">hr@x-co.dev</a>'
    findings = extract_visible_emails(html, source_url="https://jobs.example-board.dev/123")
    assert len(findings) == 1
    assert findings[0].source == "mailto"
    assert findings[0].source_url == "https://jobs.example-board.dev/123"


def test_empty_and_emailless_pages():
    assert extract_visible_emails("") == []
    assert extract_visible_emails("<body><p>No contacts here.</p></body>") == []
