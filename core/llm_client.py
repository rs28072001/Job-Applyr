import json
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
        self._cv_data = cv_data
        # System prompt includes rubric + full CV; sent with every request
        self._system_prompt = (
            f"{SCORING_RUBRIC}\n\nCANDIDATE CV:\n\n{cv_data.raw_text[:12000]}"
        )

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
