import json
import logging
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI, RateLimitError, APIError

from core.cv_parser import CVData


@dataclass
class JobScore:
    score: int
    rationale: str
    matched_skills: list = field(default_factory=list)
    missing_skills: list = field(default_factory=list)
    recommendation: str = "skip"


SCORING_RUBRIC = """You are a precise job-fit evaluator. Score how well a candidate's CV matches a job description on a scale of 0-100.

SCORING RUBRIC:
- Skills match (40 pts): How many required/preferred skills does the candidate have?
- Experience level (30 pts): Do years of experience and seniority match the role?
- Domain alignment (20 pts): Is the industry, function, and technology stack aligned?
- Education/certifications (10 pts): Are credentials and qualifications relevant?

Respond ONLY with valid JSON, no extra text:
{
  "score": <integer 0-100>,
  "rationale": "<1-2 sentence explanation>",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "recommendation": "apply" or "skip"
}"""

# Used when no CV is loaded — LLM extracts skills from the JD directly
CHATBOT_ANSWER_PROMPT = """You are helping a {role} candidate answer a Naukri job application chatbot.

Rules (follow strictly):
- For years-of-experience questions: give a number like "3" or "5" — plain integer, no units
- For location / relocation questions: always answer "Yes"
- For Yes/No questions about common {role} skills: answer "Yes"
- For notice-period questions: "30 days"
- For salary / CTC questions: "As per industry standards"
- For any other open-text question: one concise professional sentence

If choices are provided, respond with ONLY the exact text of the best matching choice.
If free text, respond with ONLY the answer — no explanation, no quotes, no punctuation."""

RUBRIC_NO_CV = """You are a job description analyser for a {role} candidate.

Given a job description, identify:
- matched_skills: core / standard skills listed in the JD that a typical {role} would already have
- missing_skills: specialised, niche, or advanced requirements that go beyond the standard {role} skill set
- score (0-100): how well this role fits a typical {role} (100 = perfect fit, 0 = completely unrelated)
- rationale: 1-2 sentence summary

Respond ONLY with valid JSON, no extra text:
{{
  "score": <integer 0-100>,
  "rationale": "<1-2 sentence explanation>",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "recommendation": "apply" or "skip"
}}"""


class LLMClient:
    def __init__(
        self,
        azure_endpoint: str,
        azure_api_key: str,
        cv_data: CVData,
        azure_deployment_name: str = "gpt-4o-mini",
    ):
        self._client = OpenAI(
            base_url=azure_endpoint,
            api_key=azure_api_key,
        )
        self._model = azure_deployment_name
        self._has_cv = bool(cv_data.raw_text)

        if self._has_cv:
            self._system_prompt = (
                f"{SCORING_RUBRIC}\n\nCANDIDATE CV:\n\n{cv_data.raw_text[:12000]}"
            )
        else:
            role = (cv_data.job_titles[0] if cv_data.job_titles else "Software Engineer")
            self._system_prompt = RUBRIC_NO_CV.format(role=role)

        self._role = cv_data.job_titles[0] if cv_data.job_titles else "Software Engineer"
        self._exp_years = str(int(cv_data.experience_years)) if cv_data.experience_years else "3"

    def answer_chatbot_question(self, question: str, choices: list | None = None) -> str:
        """Use LLM to answer a single Naukri chatbot question during apply."""
        system = CHATBOT_ANSWER_PROMPT.format(role=self._role, exp_years=self._exp_years)
        choices_text = ""
        if choices:
            choices_text = "\n\nAvailable choices (reply with EXACT text of one):\n" + "\n".join(f"- {c}" for c in choices)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=60,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Question: {question}{choices_text}"},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logging.getLogger(__name__).warning("Chatbot LLM answer failed: %s", e)
            # Sensible fallbacks
            q = question.lower()
            if choices:
                for c in choices:
                    if c.lower() in ("yes", "y"):
                        return c
                return choices[0]
            if any(w in q for w in ("year", "experience", "how long", "how many")):
                return self._exp_years
            if any(w in q for w in ("notice", "notice period")):
                return "30 days"
            if any(w in q for w in ("salary", "ctc", "expected", "package")):
                return "As per industry standards"
            return "Yes"

    def score_job(self, job_description: str, retries: int = 3) -> JobScore:
        for attempt in range(retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_completion_tokens=512,
                    messages=[
                        {"role": "system", "content": self._system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"JOB DESCRIPTION:\n\n{job_description[:4000]}\n\n"
                                "Score this candidate against the job description."
                            ),
                        },
                    ],
                )
                return self._parse_score(response.choices[0].message.content)
            except RateLimitError:
                if attempt == retries - 1:
                    raise
                time.sleep(60)
            except APIError:
                if attempt == retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))

        return JobScore(score=0, rationale="Failed to evaluate", recommendation="skip")

    def _parse_score(self, text: str) -> JobScore:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            return JobScore(
                score=int(data.get("score", 0)),
                rationale=data.get("rationale", ""),
                matched_skills=data.get("matched_skills", []),
                missing_skills=data.get("missing_skills", []),
                recommendation=data.get("recommendation", "skip"),
            )
        except (json.JSONDecodeError, ValueError):
            return JobScore(score=0, rationale=f"Parse error: {text[:100]}", recommendation="skip")
