import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from openai import OpenAI


class CVParseError(Exception):
    pass


@dataclass
class CVData:
    raw_text: str
    name: str = ""
    email: str = ""
    phone: str = ""
    skills: list = field(default_factory=list)
    experience_years: float = 0.0
    job_titles: list = field(default_factory=list)
    education: list = field(default_factory=list)
    summary: str = ""


def _extract_raw_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages).strip()
    if len(text) < 200:
        raise CVParseError(
            f"Extracted only {len(text)} characters from CV. "
            "Please provide a text-based (non-scanned) PDF."
        )
    return text


def _extract_email(text: str) -> str:
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"[\+\(]?[0-9][0-9\s\-\(\)]{7,}[0-9]", text)
    return match.group(0).strip() if match else ""


def _extract_structured_fields(raw_text: str, client, model: str = "gpt-4o-mini") -> dict:
    system_prompt = """Extract structured information from this CV/resume. Return ONLY valid JSON with these keys:
{
  "name": "full name of candidate",
  "skills": ["skill1", "skill2", ...],
  "job_titles": ["most relevant job title 1", "job title 2"],
  "experience_years": <number>,
  "education": ["degree 1", "degree 2"],
  "summary": "2-3 sentence professional summary"
}

Rules:
- job_titles should be 2-4 searchable job titles that best match this candidate's profile
- skills should list technical and domain skills, max 20
- experience_years should be a number (e.g. 5.0)
- Return only the JSON, no extra text"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"CV TEXT:\n\n{raw_text[:8000]}"},
        ],
    )

    choice = response.choices[0]
    text = choice.message.content

    if not text:
        refusal = getattr(choice.message, "refusal", None)
        raise CVParseError(
            f"LLM returned empty response for CV fields. "
            f"Refusal: {refusal if refusal else 'None'}. "
            f"Finish reason: {choice.finish_reason}"
        )

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise CVParseError(f"LLM returned invalid JSON for CV fields: {e}\nResponse: {text}")


# ── No-AI (fuzzy) extraction ──────────────────────────────────────────────────

# Common tech/QA skills lexicon for keyword-based extraction (no LLM).
_SKILL_LEXICON = [
    "manual testing", "automation testing", "selenium", "selenium webdriver", "appium",
    "cypress", "playwright", "testng", "junit", "pytest", "cucumber", "bdd", "tdd",
    "api testing", "rest assured", "postman", "soapui", "jmeter", "load testing",
    "performance testing", "regression testing", "smoke testing", "sanity testing",
    "functional testing", "integration testing", "uat", "test cases", "test planning",
    "test execution", "defect tracking", "jira", "bugzilla", "qtest", "azure devops",
    "ci/cd", "jenkins", "git", "github", "gitlab", "docker", "kubernetes",
    "python", "java", "javascript", "typescript", "c#", "sql", "mysql", "postgresql",
    "mongodb", "rest api", "graphql", "agile", "scrum", "kanban", "aws", "azure", "gcp",
    "linux", "html", "css", "react", "angular", "node.js", "spring", "django",
    "data testing", "database testing", "mobile testing", "web testing",
]

_TITLE_PATTERNS = [
    r"\b(?:senior |sr\.? |lead |junior |jr\.? )?(?:qa|sdet|software|automation|test|quality)\s+"
    r"(?:engineer|analyst|tester|lead|architect|developer|assurance)\b",
    r"\bquality assurance\b",
    r"\bsoftware (?:development engineer in test|developer|engineer)\b",
]


def _extract_skills_fuzzy(raw_text: str) -> list[str]:
    text = raw_text.lower()
    found = []
    for skill in _SKILL_LEXICON:
        if skill in text and skill not in found:
            found.append(skill.title())
    return found[:20]


def _extract_titles_fuzzy(raw_text: str) -> list[str]:
    text = raw_text.lower()
    titles, seen = [], set()
    for pat in _TITLE_PATTERNS:
        for m in re.finditer(pat, text):
            t = " ".join(w.capitalize() for w in m.group(0).split())
            if t.lower() not in seen:
                seen.add(t.lower())
                titles.append(t)
    return titles[:4] or ["QA Engineer"]


def _extract_experience_fuzzy(raw_text: str) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", raw_text.lower())
    vals = [float(m) for m in matches if float(m) <= 50]
    return max(vals) if vals else 0.0


def _extract_name_fuzzy(raw_text: str) -> str:
    # First non-empty line that looks like a name (1-4 capitalized words, no digits/@).
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or "@" in line or any(ch.isdigit() for ch in line):
            continue
        words = line.split()
        if 1 <= len(words) <= 4 and all(w[:1].isupper() for w in words if w):
            return line
    return ""


def parse_cv_fuzzy(pdf_path: str) -> CVData:
    """Parse a CV without any LLM — regex/keyword heuristics only."""
    path = Path(pdf_path)
    if not path.exists():
        raise CVParseError(f"CV file not found: {pdf_path}")

    raw_text = _extract_raw_text(pdf_path)
    return CVData(
        raw_text=raw_text,
        name=_extract_name_fuzzy(raw_text),
        email=_extract_email(raw_text),
        phone=_extract_phone(raw_text),
        skills=_extract_skills_fuzzy(raw_text),
        experience_years=_extract_experience_fuzzy(raw_text),
        job_titles=_extract_titles_fuzzy(raw_text),
        education=[],
        summary="",
    )


def parse_cv(
    pdf_path: str,
    azure_endpoint: str,
    azure_api_key: str,
    azure_deployment_name: str = "gpt-4o-mini",
) -> CVData:
    path = Path(pdf_path)
    if not path.exists():
        raise CVParseError(f"CV file not found: {pdf_path}")

    raw_text = _extract_raw_text(pdf_path)
    email = _extract_email(raw_text)
    phone = _extract_phone(raw_text)

    client = OpenAI(
        base_url=azure_endpoint,
        api_key=azure_api_key,
    )
    model = azure_deployment_name

    fields = _extract_structured_fields(raw_text, client, model)

    return CVData(
        raw_text=raw_text,
        name=fields.get("name", ""),
        email=email or "",
        phone=phone or "",
        skills=fields.get("skills", []),
        experience_years=float(fields.get("experience_years", 0)),
        job_titles=fields.get("job_titles", []),
        education=fields.get("education", []),
        summary=fields.get("summary", ""),
    )
