"""No-AI job scorer — a drop-in replacement for LLMClient that scores jobs by
fuzzy skill/title overlap instead of calling an LLM.

Same public surface the pipeline relies on:
  - score_job(job_description) -> JobScore
  - answer_chatbot_question(question, choices) -> str
  - draft_outreach_email(job_title, company, job_url) -> str

Uses only the stdlib (difflib) so it needs no API key and no extra deps.
"""
import logging
import re
from difflib import SequenceMatcher

from core.cv_parser import CVData
from core.llm_client import JobScore

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9+#.]+")


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(_norm(text)))


def _skill_in_text(skill: str, text_tokens: set[str], text: str) -> bool:
    """True if a candidate skill appears in the job text (fuzzy)."""
    s = _norm(skill)
    if not s:
        return False
    if s in text:                      # substring (handles multi-word skills)
        return True
    s_tokens = _WORD_RE.findall(s)
    if s_tokens and all(t in text_tokens for t in s_tokens):
        return True
    # Fuzzy single-token match against each job token (catches minor variants).
    for t in text_tokens:
        if len(t) >= 4 and SequenceMatcher(None, s, t).ratio() >= 0.88:
            return True
    return False


def _extract_jd_skills(job_description: str) -> list[str]:
    """Pull the 'Key Skills: a, b, c' line the API parser appends, if present."""
    m = re.search(r"key skills\s*:\s*(.+)", job_description, re.IGNORECASE)
    if m:
        return [s.strip() for s in m.group(1).split(",") if s.strip()]
    return []


class FuzzyClient:
    """Scores jobs against the CV using fuzzy string matching — no LLM."""

    def __init__(self, cv_data: CVData):
        self._skills = [s for s in (cv_data.skills or []) if s.strip()]
        self._titles = [t for t in (cv_data.job_titles or []) if t.strip()]
        self._role = self._titles[0] if self._titles else "Software Engineer"
        self._exp_years = str(int(cv_data.experience_years)) if cv_data.experience_years else "3"
        self._name = cv_data.name or ""

    def score_job(self, job_description: str, retries: int = 3) -> JobScore:
        jd = _norm(job_description)
        jd_tokens = _tokens(job_description)
        if not jd:
            return JobScore(score=0, rationale="No job description to match against.",
                            matched_skills=[], missing_skills=[], recommendation="skip")

        # 1) Skill coverage — prefer the job's own listed skills as the target set.
        jd_skills = _extract_jd_skills(job_description)
        matched, missing = [], []

        if jd_skills:
            cand_tokens = _tokens(" ".join(self._skills))
            cand_text = _norm(" ".join(self._skills))
            for sk in jd_skills:
                (matched if _skill_in_text(sk, cand_tokens, cand_text) else missing).append(sk)
            coverage = len(matched) / max(len(jd_skills), 1)
        else:
            # Fall back to: how many of the candidate's skills show up in the JD.
            for sk in self._skills:
                (matched if _skill_in_text(sk, jd_tokens, jd) else missing).append(sk)
            coverage = len(matched) / max(len(self._skills), 1)

        # 2) Title alignment — best fuzzy ratio of any CV title vs the JD text.
        title_score = 0.0
        for t in self._titles:
            t_norm = _norm(t)
            if t_norm and t_norm in jd:
                title_score = 1.0
                break
            t_tokens = _WORD_RE.findall(t_norm)
            if t_tokens:
                hits = sum(1 for tok in t_tokens if tok in jd_tokens)
                title_score = max(title_score, hits / len(t_tokens))

        # 3) Blend: skills 70%, title 30%.
        score = round((coverage * 0.7 + title_score * 0.3) * 100)
        score = max(0, min(100, score))

        recommendation = "apply" if score >= 50 else "skip"
        rationale = (
            f"Fuzzy match: {len(matched)} skill(s) overlap, "
            f"title relevance {round(title_score * 100)}%. No AI used."
        )
        return JobScore(
            score=score,
            rationale=rationale,
            matched_skills=matched[:15],
            missing_skills=missing[:15],
            recommendation=recommendation,
        )

    # ── Apply-flow helpers (rule-based fallbacks; no LLM) ──────────────────────
    def answer_chatbot_question(self, question: str, choices: list | None = None) -> str:
        q = _norm(question)
        if choices:
            for c in choices:
                if _norm(c) in ("yes", "y"):
                    return c
            return choices[0]
        if any(w in q for w in ("year", "experience", "how long", "how many")):
            return self._exp_years
        if "notice" in q:
            return "30 days"
        if any(w in q for w in ("salary", "ctc", "expected", "package")):
            return "As per industry standards"
        return "Yes"

    def draft_outreach_email(self, job_title: str, company: str, job_url: str) -> str:
        top_skills = ", ".join(self._skills[:3]) if self._skills else "my relevant experience"
        name = self._name or "Candidate"
        return (
            f"Dear Hiring Team,\n\n"
            f"I am writing to express my interest in the {job_title} role at {company}. "
            f"With {self._exp_years}+ years of experience and a strong background in {top_skills}, "
            f"I believe I would be a great fit for this position.\n\n"
            f"I came across the opening here: {job_url}. I have attached my resume and would "
            f"welcome the opportunity to discuss how my skills align with your team's needs.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Best regards,\n{name}"
        )
