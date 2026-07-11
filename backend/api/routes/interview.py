"""AI Mock Interview endpoints.

GET  /api/interview/defaults   · setup values auto-filled from CV profile + config
POST /api/interview/start      · LLM generates questions, creates a session
POST /api/interview/answer     · LLM evaluates one answer
POST /api/interview/finish     · closes the session, computes overall stats
GET  /api/interview/history    · past sessions + aggregate stats
"""
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Config as ConfigModel, CVProfile, InterviewSession, User
from core.llm_provider import (
    LLMConfigError, get_llm_settings, is_llm_configured, validate_llm_settings,
)

router = APIRouter()

PASS_SCORE = 6.0  # out of 10 — counts as a "successful" interview


# ── Schemas ───────────────────────────────────────────────────────────────────

class InterviewDefaults(BaseModel):
    role: str
    role_options: list[str]
    experience_years: float
    skills: list[str]


class StartRequest(BaseModel):
    role: str
    experience_level: str = ""
    interview_type: str = "technical"
    difficulty: str = "medium"
    skills: list[str] = []
    language: str = "en-US"
    duration_minutes: int = 30
    answer_mode: str = "voice"


class StartResponse(BaseModel):
    session_id: int
    questions: list[str]


class AnswerRequest(BaseModel):
    session_id: int
    question_index: int
    answer: str


class AnswerEvaluation(BaseModel):
    score: float
    feedback: str
    improvement: str


class FinishRequest(BaseModel):
    session_id: int
    terminated: bool = False
    reason: str = ""


class QAResult(BaseModel):
    question: str
    answer: str
    score: float
    feedback: str
    improvement: str


class FinishResponse(BaseModel):
    overall_score: float
    answered: int
    total_questions: int
    status: str
    verdict: str
    results: list[QAResult]


class HistoryItem(BaseModel):
    id: int
    role: str
    interview_type: str
    difficulty: str
    overall_score: float | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    interviews_taken: int
    avg_score: float
    success_rate: int
    best_streak: int
    recent: list[HistoryItem]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm_client(db: DBSession):
    from openai import OpenAI

    cfg = db.get(ConfigModel, 1)
    llm_settings = get_llm_settings(cfg) if cfg else None
    if llm_settings and llm_settings.provider == "fuzzy":
        raise HTTPException(400, "Mock interviews need an AI provider. Use non-fuzzy mode in Settings.")
    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    try:
        validate_llm_settings(llm_settings)
    except LLMConfigError as e:
        raise HTTPException(400, str(e))
    return OpenAI(base_url=llm_settings.base_url, api_key=llm_settings.api_key), llm_settings.model


def _llm_json(client, model: str, system_prompt: str, user_prompt: str, max_tokens: int = 900) -> dict:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _question_count(duration_minutes: int) -> int:
    if duration_minutes <= 15:
        return 5
    if duration_minutes <= 30:
        return 8
    return 10


def _verdict(score: float) -> str:
    if score >= 8.5:
        return "Excellent — you are interview-ready for this role."
    if score >= 7:
        return "Strong performance. Polish the weaker answers and you're there."
    if score >= PASS_SCORE:
        return "Decent showing — review the feedback and retry the weak areas."
    if score >= 4:
        return "Needs work. Focus on the improvement tips and practice again."
    return "Keep practicing — go through the feedback carefully and retry."


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/interview/defaults", response_model=InterviewDefaults)
def interview_defaults(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    profile = (
        db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
    )
    cfg = db.get(ConfigModel, 1)

    role_options: list[str] = []
    if profile and profile.job_titles:
        role_options.extend(profile.job_titles)
    if cfg and cfg.keywords:
        role_options.extend(k for k in cfg.keywords if k not in role_options)

    return InterviewDefaults(
        role=role_options[0] if role_options else "",
        role_options=role_options[:10],
        experience_years=profile.experience_years if profile else 0.0,
        skills=(profile.skills or [])[:12] if profile else [],
    )


@router.post("/api/interview/start", response_model=StartResponse)
def start_interview(body: StartRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    if not body.role.strip():
        raise HTTPException(400, "Job role is required")

    client, model = _llm_client(db)
    n = _question_count(body.duration_minutes)

    system_prompt = f"""You are a senior interviewer conducting a {body.difficulty} {body.interview_type.replace('_', ' ')} interview for a {body.role} position.
Generate exactly {n} interview questions appropriate for a candidate with {body.experience_level or 'unspecified'} experience.
Questions must be spoken-friendly (they will be read aloud by text-to-speech): no code blocks, no markdown, one clear question each, ordered from warm-up to hardest.
{f"Focus especially on these skills: {', '.join(body.skills)}." if body.skills else ""}
Return ONLY a JSON object: {{"questions": ["...", "..."]}}"""

    try:
        result = _llm_json(client, model, system_prompt, f"Generate the {n} questions now.")
        questions = [str(q) for q in result.get("questions", [])][:n]
    except HTTPException:
        raise
    except Exception as e:
        print(f"Interview question generation error: {e}")
        raise HTTPException(500, f"Question generation failed: {e}")

    if not questions:
        raise HTTPException(500, "LLM returned no questions — try again")

    session = InterviewSession(
        role=body.role,
        interview_type=body.interview_type,
        difficulty=body.difficulty,
        skills=body.skills,
        language=body.language,
        duration_minutes=body.duration_minutes,
        answer_mode=body.answer_mode,
        questions=questions,
        answers=[],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return StartResponse(session_id=session.id, questions=questions)


@router.post("/api/interview/answer", response_model=AnswerEvaluation)
def evaluate_answer(body: AnswerRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    session = db.get(InterviewSession, body.session_id)
    if not session:
        raise HTTPException(404, "Interview session not found")
    if session.status != "in_progress":
        raise HTTPException(400, "Interview is already finished")
    if body.question_index < 0 or body.question_index >= len(session.questions or []):
        raise HTTPException(400, "Invalid question index")

    question = session.questions[body.question_index]
    answer = body.answer.strip()

    if not answer:
        evaluation = {"score": 0.0, "feedback": "No answer was given.", "improvement": "Attempt every question — even a partial answer scores better than silence."}
    else:
        client, model = _llm_client(db)
        system_prompt = f"""You are a strict but fair interviewer scoring one answer in a {session.difficulty} {session.interview_type.replace('_', ' ')} interview for a {session.role} role.
Score the candidate's answer from 0 to 10 (decimals allowed). Judge correctness, depth, structure, and relevance. A vague or off-topic answer scores below 4. The answer may come from speech-to-text, so ignore minor transcription noise and punctuation.
Return ONLY a JSON object: {{"score": <number>, "feedback": "<2-3 sentence assessment>", "improvement": "<one concrete tip to improve this answer>"}}"""
        user_prompt = f"Question: {question}\n\nCandidate's answer: {answer}"
        try:
            evaluation = _llm_json(client, model, system_prompt, user_prompt, max_tokens=400)
        except HTTPException:
            raise
        except Exception as e:
            print(f"Answer evaluation error: {e}")
            raise HTTPException(500, f"Answer evaluation failed: {e}")

    score = max(0.0, min(10.0, float(evaluation.get("score", 0))))
    record = {
        "question": question,
        "answer": answer,
        "score": score,
        "feedback": str(evaluation.get("feedback", "")),
        "improvement": str(evaluation.get("improvement", "")),
    }
    # Reassign the JSON column so SQLAlchemy detects the change
    session.answers = (session.answers or []) + [record]
    db.commit()

    return AnswerEvaluation(score=score, feedback=record["feedback"], improvement=record["improvement"])


@router.post("/api/interview/finish", response_model=FinishResponse)
def finish_interview(body: FinishRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    session = db.get(InterviewSession, body.session_id)
    if not session:
        raise HTTPException(404, "Interview session not found")

    answers = session.answers or []
    total = len(session.questions or [])
    # Unanswered questions count as 0 so leaving early doesn't inflate the score
    overall = round(sum(a["score"] for a in answers) / total, 1) if total else 0.0

    if session.status == "in_progress":
        session.status = "terminated" if body.terminated else "completed"
        session.termination_reason = body.reason if body.terminated else ""
        session.overall_score = overall
        session.completed_at = datetime.now(timezone.utc)
        db.commit()

    verdict = (
        "Interview terminated — leaving the interview screen counts as an incomplete attempt."
        if session.status == "terminated"
        else _verdict(session.overall_score or 0.0)
    )
    return FinishResponse(
        overall_score=session.overall_score or 0.0,
        answered=len(answers),
        total_questions=total,
        status=session.status,
        verdict=verdict,
        results=[QAResult(**a) for a in answers],
    )


@router.get("/api/interview/history", response_model=HistoryResponse)
def interview_history(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.status != "in_progress")
        .order_by(InterviewSession.id.desc())
        .all()
    )
    scores = [s.overall_score for s in sessions if s.overall_score is not None]
    passed_flags = [
        (s.overall_score or 0) >= PASS_SCORE and s.status == "completed" for s in sessions
    ]

    best_streak = streak = 0
    for passed in reversed(passed_flags):  # chronological order
        streak = streak + 1 if passed else 0
        best_streak = max(best_streak, streak)

    return HistoryResponse(
        interviews_taken=len(sessions),
        avg_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
        success_rate=round(100 * sum(passed_flags) / len(passed_flags)) if passed_flags else 0,
        best_streak=best_streak,
        recent=[HistoryItem.model_validate(s) for s in sessions[:6]],
    )
