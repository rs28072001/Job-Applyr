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
        max_completion_tokens=4096,
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
